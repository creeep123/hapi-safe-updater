import importlib.util
from pathlib import Path
import unittest


def module():
    spec = importlib.util.spec_from_file_location('arm_gate', Path(__file__).parents[1] / 'bin/verify-arm-container.py')
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


class ContainerBoundaryTests(unittest.TestCase):
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
