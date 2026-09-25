import importlib.util
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
import os
import json
import sys
import io
from contextlib import redirect_stdout


IMAGE = 'sha256:' + 'a' * 64
CID = 'b' * 64


def worker_records(failure=False):
    return [
        {'stage': 'isolation', 'passed': True, 'architecture': 'aarch64', 'memoryMax': 1073741824,
         'artifactHashes': {'hapi': 'c'*64, 'codex': 'd'*64}},
        {'stage': 'versions', 'passed': True, 'hapi': '0.30.7', 'codex': '0.154.0'},
        {'stage': 'hub', 'passed': True, 'health': 200, 'auth': 200, 'unauthCompanion': 401},
        {'stage': 'runner', 'passed': True, 'activeMachines': 1},
        {'stage': 'models', 'passed': True, 'count': 6, 'providerRequests': 0},
        {'stage': 'spawn', 'passed': True, 'webhook': True, 'authenticatedCodexTCP': True},
        {'stage': 'message', 'passed': True},
        {'stage': 'reply', 'passed': True, 'providerRequests': 1, 'failurePropagated': failure,
         'exactReply': not failure, 'thinking': False},
        {'stage': 'result', 'status': 'ARM_WORKER_CHAIN_COMPLETE', 'protocol': 2,
         'productionApproved': False, 'vmSystemdVerified': False, 'rollbackVerified': False,
         'memoryPeakBytes': 818905088}]


def encoded(records):
    return ('\n'.join(json.dumps(r) for r in records)+'\n').encode()


class SimulatedDocker:
    """Docker API/CLI boundary double; never starts a process or talks to Docker."""
    def __init__(self, fault=None):
        self.fault = fault
        self.container = None
        self.created = self.started = self.removed = 0
        self.admissions = 0

    def run(self, *args):
        command = args[0]
        if command == 'info':
            return json.dumps({'Architecture': 'aarch64', 'MemTotal': 2053644288}).encode()
        if command == 'ps':
            if '--filter' in args:
                return CID.encode() if self.container else b''
            self.admissions += 1
            return b'other' if self.fault == 'late_workload' and self.admissions >= 2 else b''
        if command == 'create':
            self.created += 1
            name = args[args.index('--name') + 1]
            label = args[args.index('--label') + 1].split('=', 1)
            self.container = {'Id': CID, 'Name': '/'+name, 'Image': IMAGE, 'Mounts': [],
                'Config': {'Labels': {label[0]: label[1]}, 'Env': [
                    'PATH=/usr/local/bin:/usr/bin:/bin', 'HOME=/work', 'LANG=C.UTF-8']},
                'HostConfig': {'NetworkMode': 'none', 'ReadonlyRootfs': True},
                'State': {'ExitCode': 0, 'OOMKilled': False, 'Running': False}}
            if self.fault == 'proxy_env':
                self.container['Config']['Env'].append('HTTP_PROXY=synthetic-secret')
            if self.fault == 'wrong_owner':
                self.container['Config']['Labels'][label[0]] = 'another-owner'
            if self.fault == 'create_timeout':
                raise RuntimeError('synthetic-timeout-secret')
            if self.fault == 'create_unknown_absent':
                self.container = None
                raise RuntimeError('synthetic-timeout-secret')
            if self.fault == 'create_interrupt':
                raise KeyboardInterrupt()
            return CID.encode()
        if command == 'inspect':
            return json.dumps([self.container]).encode()
        if command == 'rm':
            if self.fault == 'cleanup_failure':
                raise RuntimeError('synthetic-cleanup-secret')
            if self.fault == 'cleanup_lies':
                return CID.encode()
            assert args[-1] == CID
            self.removed += 1
            self.container = None
            return CID.encode()
        raise AssertionError('unexpected Docker operation: '+command)

    def collect(self, container_id):
        assert container_id == CID
        self.started += 1
        if self.fault in ('success', 'cleanup_failure', 'cleanup_lies'):
            return encoded(worker_records())
        if self.fault == 'malformed_output':
            return b'{"status":"ARM_CONTAINER_PARTIAL_PASS","token":"synthetic-secret"}\n'
        raise RuntimeError('synthetic-attach-secret')


def module():
    spec = importlib.util.spec_from_file_location('arm_gate', Path(__file__).parents[1] / 'bin/verify-arm-container.py')
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


class ContainerBoundaryTests(unittest.TestCase):
    def test_script_entrypoint_exits_zero_without_catching_its_own_system_exit(self):
        import ast
        gate = module()
        source = Path(gate.__file__).read_text()
        entry = ast.Module(body=[ast.parse(source).body[-1]], type_ignores=[])
        namespace = {**gate.__dict__, '__name__': '__main__'}
        output = io.StringIO()
        with patch.object(gate, 'host', return_value=0), \
                patch.object(sys, 'argv', ['gate', '--image', IMAGE]), redirect_stdout(output):
            with self.assertRaises(SystemExit) as stopped:
                exec(compile(entry, '<entrypoint-only>', 'exec'), namespace)
        self.assertEqual(stopped.exception.code, 0)
        self.assertEqual(output.getvalue(), '')  # No spurious FAIL from the entrypoint.

    def test_cli_main_preserves_success_failure_and_one_terminal_record(self):
        gate = module()
        for code in (0, 1):
            def transaction(*_args):
                gate.emit('host_result', status='ARM_CONTAINER_PARTIAL_PASS' if code == 0 else 'FAIL')
                return code
            output = io.StringIO()
            with patch.object(gate, 'host', side_effect=transaction), redirect_stdout(output):
                self.assertEqual(gate.main(['--image', IMAGE]), code)
            self.assertEqual(len(output.getvalue().splitlines()), 1)
            self.assertEqual(json.loads(output.getvalue())['status'],
                             'ARM_CONTAINER_PARTIAL_PASS' if code == 0 else 'FAIL')
        output = io.StringIO()
        with patch.object(gate, 'host', side_effect=KeyboardInterrupt()), redirect_stdout(output):
            self.assertEqual(gate.main(['--image', IMAGE]), 1)
        self.assertEqual(len(output.getvalue().splitlines()), 1)
        self.assertEqual(json.loads(output.getvalue())['status'], 'FAIL')

    def test_unknown_absent_create_is_reported_unconfirmed_not_clean(self):
        gate = module()
        client = SimulatedDocker('create_unknown_absent')
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(gate.run_host_transaction(client, IMAGE), 1)
        record = json.loads(output.getvalue())
        self.assertFalse(record['cleanupVerified'])
        self.assertEqual(record['phase'], 'cleanup')
        self.assertRegex(record['residualContainer'], '^hsu-arm-test-[0-9a-f]{12}$')
        self.assertEqual(client.started, 0)

    def test_attach_timeout_cleanup_failure_and_lying_rm_cannot_pass(self):
        gate = module()
        for fault in ('attach_timeout', 'cleanup_failure', 'cleanup_lies'):
            client = SimulatedDocker(fault)
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(gate.run_host_transaction(client, IMAGE), 1)
            record = json.loads(output.getvalue())
            self.assertEqual(record['status'], 'FAIL')
            self.assertNotIn('secret', output.getvalue())
            self.assertEqual(record['cleanupVerified'], fault == 'attach_timeout')

    def test_bounded_command_reaps_its_own_child_on_timeout(self):
        gate = module()
        original = gate.subprocess.Popen
        children = []
        def launch(*args, **kwargs):
            child = original(*args, **kwargs)
            children.append(child)
            return child
        with patch.object(gate.subprocess, 'Popen', side_effect=launch):
            with self.assertRaisesRegex(RuntimeError, 'docker_command_timeout'):
                gate.bounded_command([sys.executable, '-c', 'import time; time.sleep(3)'],
                                     {'PATH': '/usr/bin:/bin'}, timeout=.1)
        self.assertIsNotNone(children[0].poll())
        self.assertTrue(children[0].stdout.closed)

    def test_only_complete_ordered_mode_bound_whitelisted_evidence_is_accepted(self):
        gate = module()
        for mode in (False, True):
            result = gate.validate_worker_output(encoded(worker_records(mode)), mode)
            self.assertEqual(result['modelCount'], 6)
        import copy
        invalid = []
        records = worker_records()
        invalid.extend([records[:-1], records[::-1], records+records[-1:]])
        extra = copy.deepcopy(records)
        extra[0]['token'] = 'synthetic-secret'
        invalid.append(extra)
        nested = copy.deepcopy(records)
        nested[0]['artifactHashes']['token'] = 'synthetic-secret'
        invalid.append(nested)
        stale = copy.deepcopy(records)
        stale[-1]['status'] = 'ARM_CONTAINER_PARTIAL_PASS'
        invalid.append(stale)
        boolean_count = copy.deepcopy(records)
        boolean_count[4]['count'] = True
        invalid.append(boolean_count)
        invalid.append(worker_records(True))
        for records in invalid:
            with self.assertRaises((RuntimeError, ValueError)):
                gate.validate_worker_output(encoded(records), False)
        with self.assertRaises((RuntimeError, ValueError)):
            gate.validate_worker_output(b'x'*16385, False)

    def test_pass_is_emitted_only_after_verified_cleanup(self):
        gate = module()
        for fault, expected in (('success', 0), ('cleanup_failure', 1), ('malformed_output', 1)):
            client = SimulatedDocker(fault)
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(gate.run_host_transaction(client, IMAGE), expected)
            record = json.loads(output.getvalue())  # Exactly one terminal result.
            self.assertNotIn('secret', output.getvalue())
            if expected == 0:
                self.assertIsNone(client.container)
                self.assertTrue(record['cleanupVerified'])
                self.assertEqual(record['status'], 'ARM_CONTAINER_PARTIAL_PASS')
            else:
                self.assertNotIn('PASS', record['status'])

    def test_uncertain_create_or_interrupt_cleans_only_owned_container(self):
        gate = module()
        for fault in ('create_timeout', 'create_interrupt'):
            client = SimulatedDocker(fault)
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(gate.run_host_transaction(client, IMAGE), 1)
            self.assertEqual(client.removed, 1)
            self.assertEqual(client.started, 0)
            self.assertNotIn('secret', output.getvalue())
            self.assertNotIn('PARTIAL_PASS', output.getvalue())

    def test_late_workload_or_proxy_env_never_starts_candidate(self):
        gate = module()
        for fault in ('late_workload', 'proxy_env'):
            client = SimulatedDocker(fault)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(gate.run_host_transaction(client, IMAGE), 1)
            self.assertEqual(client.started, 0)
            self.assertEqual(client.removed, 1)

    def test_cleanup_refuses_foreign_owner_and_reports_unconfirmed(self):
        gate = module()
        client = SimulatedDocker('wrong_owner')
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(gate.run_host_transaction(client, IMAGE), 1)
        self.assertEqual(client.removed, 0)
        self.assertFalse(json.loads(output.getvalue())['cleanupVerified'])

    def test_bounded_command_timeout_output_limit_and_nonzero_are_redacted(self):
        gate = module()
        environment = {'PATH': '/usr/bin:/bin'}
        self.assertEqual(gate.bounded_command([sys.executable, '-c', 'print("ok")'], environment, 2, 100), b'ok\n')
        cases = [('import time; time.sleep(3)', .1, 100, 'docker_command_timeout'),
                 ('print("synthetic-secret"*100)', 2, 100, 'docker_output_limit'),
                 ('import sys; print("synthetic-secret"); sys.exit(1)', 2, 100, 'docker_command_failed')]
        for code, timeout, limit, reason in cases:
            with self.assertRaisesRegex(RuntimeError, '^'+reason+'$'):
                gate.bounded_command([sys.executable, '-c', code], environment, timeout, limit)

    def test_docker_client_uses_empty_config_and_clean_environment(self):
        gate = module()
        with patch.dict(os.environ, {'DOCKER_CONTEXT': 'remote', 'DOCKER_CONFIG': '/synthetic-account',
                        'HTTP_PROXY': 'synthetic-proxy-secret', 'OPENAI_API_KEY': 'synthetic-key'}), \
                patch('shutil.which', return_value='/usr/local/bin/docker'):
            with gate.isolated_docker('/Users/test') as client:
                self.assertEqual(client.prefix[0], '/usr/local/bin/docker')
                config = Path(client.prefix[client.prefix.index('--config') + 1])
                self.assertEqual(json.loads((config/'config.json').read_text()), {})
                self.assertEqual(set(client.env), {'PATH', 'HOME', 'LANG'})
                self.assertNotIn('synthetic', json.dumps(client.env))
                self.assertEqual(client.prefix[-2:], ['--host', 'unix:///Users/test/.colima/default/docker.sock'])
                self.assertEqual(config.stat().st_mode & 0o777, 0o700)
            self.assertFalse(config.exists())

    def test_container_environment_rejects_proxy_before_start(self):
        gate = module()
        self.assertTrue(gate.safe_container_env(['PATH=/usr/local/bin:/usr/bin:/bin',
                                              'HOME=/work', 'LANG=C.UTF-8']))
        for entry in ('HTTP_PROXY=synthetic-secret', 'HOME=https://secret', 'OPENAI_API_KEY=synthetic',
                      'PATH=/untrusted/bin', 'LANG=synthetic-token'):
            self.assertFalse(gate.safe_container_env([entry]))

    def test_lease_refuses_competing_launcher_and_releases_after_failure(self):
        gate = module()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'gate.lock'
            with self.assertRaisesRegex(RuntimeError, 'synthetic_failure'):
                with gate.exclusive_lease(path):
                    with self.assertRaisesRegex(RuntimeError, 'launcher_busy'):
                        with gate.exclusive_lease(path):
                            self.fail('two launchers acquired the lease')
                    raise RuntimeError('synthetic_failure')
            with gate.exclusive_lease(path):
                self.assertTrue(path.is_file())

    def test_lease_rejects_symlink_or_public_file(self):
        gate = module()
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / 'target'
            target.write_text('synthetic')
            link = Path(root) / 'gate.lock'
            link.symlink_to(target)
            with self.assertRaises((RuntimeError, OSError)):
                with gate.exclusive_lease(link):
                    self.fail('accepted symlink')
            with self.assertRaises(RuntimeError):
                with gate.exclusive_lease(target):
                    self.fail('accepted world-readable lease')

    def test_daemon_selection_cannot_follow_remote_context(self):
        gate = module()
        self.assertEqual(gate.docker_prefix('/Users/test'),
            ['docker', '--host', 'unix:///Users/test/.colima/default/docker.sock'])
        for invalid in ('/', '/home/test', 'ssh://vm', '/Users/test/../elsewhere'):
            with self.assertRaises(ValueError):
                gate.docker_prefix(invalid)

    def test_reply_requires_exact_agent_message_after_matching_user(self):
        gate = module()
        user = {'seq': 2, 'localId': 'request-1', 'content': {'role': 'user'}}
        reply = {'seq': 3, 'content': {'role': 'agent', 'content': {'type': 'codex',
                    'data': {'type': 'message', 'message': 'HSU_ARM_OK:abc123'}}}}
        self.assertTrue(gate.has_reply([user, reply], 'request-1', 'abc123'))
        self.assertFalse(gate.has_reply([reply], 'request-1', 'abc123'))
        self.assertFalse(gate.has_reply([user, {**reply, 'seq': 1}], 'request-1', 'abc123'))
        self.assertFalse(gate.has_reply([user, reply], 'request-1', 'different'))
        self.assertFalse(gate.has_reply([user, {**reply, 'content': {'role': 'agent',
             'content': {'type': 'codex', 'data': {'type': 'error', 'message': 'HSU_ARM_OK:abc123'}}}}],
             'request-1', 'abc123'))

    def test_fixture_rejects_auth_wrong_nonce_model_and_repeated_calls(self):
        gate = module()
        import http.server
        import json
        import threading
        import urllib.request
        import urllib.error
        state = {'requests': 0, 'accepted': 0, 'rejected': 0}
        with http.server.ThreadingHTTPServer(('127.0.0.1', 0), gate.fixture_handler('abc123', state)) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            def post(body, auth=False):
                req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/v1/responses',
                    json.dumps(body).encode(), {'Content-Type': 'application/json',
                    **({'Authorization': 'synthetic-test'} if auth else {})})
                try:
                    with urllib.request.urlopen(req) as response:
                        return response.status, response.read()
                except urllib.error.HTTPError as error:
                    return error.code, error.read()
            valid = {'model': 'local-fixture', 'input': [{'content': 'abc123'}], 'stream': True}
            self.assertEqual(post(valid, True)[0], 400)
            self.assertEqual(post({**valid, 'model': 'wrong'})[0], 400)
            self.assertEqual(post({**valid, 'input': []})[0], 400)
            status, body = post(valid)
            self.assertEqual(status, 200)
            self.assertIn(b'HSU_ARM_OK:abc123', body)
            self.assertEqual(post(valid)[0], 400)
            server.shutdown()
            thread.join()
        self.assertEqual(state['accepted'], 1)
        self.assertEqual(state['rejected'], 4)

    def test_launch_is_offline_unmounted_and_bounded(self):
        gate = module()
        args = gate.container_args('sha256:' + 'a' * 64, 'hsu-arm-test-123')
        self.assertEqual(args[args.index('--network') + 1], 'none')
        self.assertEqual(args[args.index('--memory') + 1], '1g')
        self.assertEqual(args[args.index('--memory-swap') + 1], '1g')
        self.assertIn('--read-only', args)
        self.assertIn('no-new-privileges', args)
        self.assertIn('65534:65534', args)
        for forbidden in ('--privileged', '--mount', '-v', '--volume', '--env-file', '--publish'):
            self.assertNotIn(forbidden, args)
        for bad in ('latest', 'example:tag', 'sha256:' + 'x' * 64):
            with self.assertRaises(ValueError):
                gate.container_args(bad, 'hsu-arm-test-123')


if __name__ == '__main__':
    unittest.main()
