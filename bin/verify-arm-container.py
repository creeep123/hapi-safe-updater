#!/usr/bin/env python3
"""Local ARM Docker partial gate. Never a VM or production acceptance launcher."""
import re
import http.server
import json
import argparse
import hashlib
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
from contextlib import contextmanager
import fcntl
import stat
import tempfile
import selectors
import shutil

OWNER_LABEL = 'io.hapi.safe-updater.arm-test-owner'
WORKER_PROTOCOL = 2
CLEAN_PATH = '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin'


def bounded_command(args, env, timeout=20, limit=65536):
    """Docker CLI boundary: bounded memory/time; no stderr or arbitrary exception text."""
    process = subprocess.Popen(args, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + timeout
    output = bytearray()
    try:
        with selectors.DefaultSelector() as poller:
            poller.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = deadline - time.monotonic()
                require(remaining > 0, 'docker_command_timeout')
                if not poller.select(min(remaining, .2)):
                    continue
                chunk = os.read(process.stdout.fileno(), min(8192, limit + 1 - len(output)))
                if not chunk:
                    break
                output.extend(chunk)
                require(len(output) <= limit, 'docker_output_limit')
        try:
            code = process.wait(timeout=max(.01, deadline-time.monotonic()))
        except subprocess.TimeoutExpired:
            raise RuntimeError('docker_command_timeout') from None
        require(code == 0, 'docker_command_failed')
        return bytes(output)
    finally:
        with termination_scope(cleaning=True):
            try:
                if process.poll() is None:
                    try:
                        process.terminate()
                    except ProcessLookupError:
                        pass
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        try:
                            process.kill()
                        except ProcessLookupError:
                            pass
                        process.wait(timeout=2)
            finally:
                process.stdout.close()


class DockerClient:
    def __init__(self, prefix, env):
        self.prefix, self.env = prefix, env

    def run(self, *args):
        return bounded_command([*self.prefix, *args], self.env)

    def collect(self, container_id):
        return bounded_command([*self.prefix, 'start', '--attach', container_id],
                               self.env, timeout=240, limit=16384)


@contextmanager
def isolated_docker(home):
    endpoint = docker_prefix(home)[1:]
    binary = shutil.which('docker', path=CLEAN_PATH)
    require(binary is not None and os.path.isabs(binary), 'docker_binary_missing')
    with tempfile.TemporaryDirectory(prefix='hsu-arm-docker-config-') as directory:
        config = Path(directory)
        (config/'config.json').write_text('{}')
        os.chmod(config/'config.json', 0o600)
        yield DockerClient([binary, '--config', str(config), *endpoint],
                           {'PATH': CLEAN_PATH, 'HOME': str(config), 'LANG': 'C.UTF-8'})


def safe_container_env(entries):
    patterns = {'PATH': r'/usr/local/bin:/usr/bin:/bin', 'HOME': r'/work', 'LANG': r'C.UTF-8',
                'GPG_KEY': r'[0-9A-F]{40}', 'PYTHON_VERSION': r'3\.12\.[0-9]{1,2}',
                'PYTHON_SHA256': r'[0-9a-f]{64}'}
    if not isinstance(entries, list) or len(entries) > len(patterns):
        return False
    seen = set()
    for entry in entries:
        if not isinstance(entry, str) or '=' not in entry:
            return False
        key, value = entry.split('=', 1)
        if key in seen or key not in patterns or re.fullmatch(patterns[key], value) is None:
            return False
        seen.add(key)
    return {'PATH', 'HOME', 'LANG'} <= seen


@contextmanager
def exclusive_lease(path):
    """Per-user cooperating-launcher lease; never unlink a held/stable lock inode."""
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        metadata = os.fstat(fd)
        require(stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.getuid()
                and stat.S_IMODE(metadata.st_mode) == 0o600 and metadata.st_nlink == 1,
                'unsafe_lease_file')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('launcher_busy') from None
        yield
    finally:
        os.close(fd)


def has_reply(messages, local_id, nonce):
    seqs = [m['seq'] for m in messages if m.get('localId') == local_id
            and m.get('content', {}).get('role') == 'user' and type(m.get('seq')) is int]
    if not seqs:
        return False
    for message in messages:
        content = message.get('content', {})
        item = content.get('content', {})
        if not isinstance(item, dict) or not isinstance(item.get('data', {}), dict):
            continue
        data = item.get('data', {})
        if (content.get('role') == 'agent' and type(message.get('seq')) is int
                and message['seq'] > max(seqs) and item.get('type') == 'codex'
                and data.get('type') == 'message' and data.get('message') == 'HSU_ARM_OK:' + nonce):
            return True
    return False


def fixture_handler(nonce, state, fail=False):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            self.send_error(404)

        def do_POST(self):
            state['requests'] += 1
            self.connection.settimeout(5)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 2_000_000:
                    raise ValueError()
                body = json.loads(self.rfile.read(length))
                valid = (self.path == '/v1/responses' and not self.headers.get('Authorization')
                         and body.get('model') == 'local-fixture' and body.get('stream') is True
                         and nonce in json.dumps(body.get('input')) and state['accepted'] == 0)
            except (ValueError, OSError, AttributeError):
                valid = False
            if not valid or fail:
                state['rejected'] += 1
                self.send_error(400)
                return
            state['accepted'] += 1
            text = 'HSU_ARM_OK:' + nonce
            item = {'id': 'msg_fixture', 'type': 'message', 'role': 'assistant',
                    'status': 'completed', 'content': [{'type': 'output_text', 'text': text,
                                                      'annotations': []}]}
            response = {'id': 'resp_fixture', 'object': 'response', 'status': 'completed',
                        'output': [item], 'usage': {'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2}}
            events = [
                {'type': 'response.created', 'response': {**response, 'status': 'in_progress', 'output': []}},
                {'type': 'response.output_item.added', 'output_index': 0,
                 'item': {**item, 'status': 'in_progress', 'content': []}},
                {'type': 'response.output_text.delta', 'item_id': 'msg_fixture', 'output_index': 0,
                 'content_index': 0, 'delta': text},
                {'type': 'response.output_item.done', 'output_index': 0, 'item': item},
                {'type': 'response.completed', 'response': response}]
            data = ''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    return Handler


def container_args(image, name):
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise ValueError('immutable_image_required')
    if not re.fullmatch(r'hsu-arm-test-[a-z0-9-]{1,40}', name):
        raise ValueError('dedicated_name_required')
    return ['create', '--name', name, '--pull', 'never', '--platform', 'linux/arm64',
            '--env', 'PATH=/usr/local/bin:/usr/bin:/bin', '--env', 'HOME=/work', '--env', 'LANG=C.UTF-8',
            '--network', 'none', '--read-only', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--memory', '1g',
            '--memory-swap', '1g', '--cpus', '0.75', '--pids-limit', '128',
            '--user', '65534:65534', '--tmpfs', '/work:rw,nosuid,nodev,size=192m,mode=1777',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=32m,mode=1777',
            '--log-driver', 'none', '--entrypoint', '/usr/bin/timeout',
            image, '--signal=TERM', '--kill-after=5s', '240s',
            '/usr/local/bin/python3', '-B', '/opt/gate/verify-arm-container.py', '--worker']


def docker_prefix(home):
    # Explicit local Colima socket: ignore Docker's current (possibly remote) context.
    if not re.fullmatch(r'/Users/[A-Za-z0-9_.-]+', home) or Path(home).name in ('.', '..'):
        raise ValueError('local_mac_home_required')
    return ['docker', '--host', 'unix://' + home + '/.colima/default/docker.sock']


def require(ok, stage):
    if not ok:
        raise RuntimeError(stage)


def emit(stage, **fields):
    print(json.dumps({'stage': stage, **fields}), flush=True)


def validate_worker_output(raw, fail_provider):
    """No raw worker field is forwarded; require a complete, versioned transcript."""
    require(isinstance(raw, bytes) and len(raw) <= 16384, 'worker_output_limit')
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate_evidence_key')
            result[key] = value
        return result
    records = [json.loads(line, object_pairs_hook=unique_object) for line in raw.splitlines()]
    shapes = [
        {'stage': 'isolation', 'passed': True, 'architecture': 'aarch64', 'memoryMax': 1073741824,
         'artifactHashes': None},
        {'stage': 'versions', 'passed': True, 'hapi': '0.30.7', 'codex': '0.154.0'},
        {'stage': 'hub', 'passed': True, 'health': 200, 'auth': 200, 'unauthCompanion': 401},
        {'stage': 'runner', 'passed': True, 'activeMachines': 1},
        {'stage': 'models', 'passed': True, 'count': None, 'providerRequests': 0},
        {'stage': 'spawn', 'passed': True, 'webhook': True, 'authenticatedCodexTCP': True},
        {'stage': 'message', 'passed': True},
        {'stage': 'reply', 'passed': True, 'providerRequests': 1, 'failurePropagated': fail_provider,
         'exactReply': not fail_provider, 'thinking': False},
        {'stage': 'result', 'status': 'ARM_WORKER_CHAIN_COMPLETE', 'protocol': WORKER_PROTOCOL,
         'productionApproved': False, 'vmSystemdVerified': False, 'rollbackVerified': False,
         'memoryPeakBytes': None}]
    require(len(records) == len(shapes), 'evidence_stages')
    for record, shape in zip(records, shapes):
        require(isinstance(record, dict) and set(record) == set(shape), 'evidence_fields')
        for key, expected in shape.items():
            if expected is not None:
                require(type(record[key]) is type(expected) and record[key] == expected, 'evidence_value')
    hashes = records[0]['artifactHashes']
    require(isinstance(hashes, dict) and set(hashes) == {'hapi', 'codex'}
            and all(isinstance(v, str) and re.fullmatch(r'[0-9a-f]{64}', v) for v in hashes.values()),
            'evidence_hashes')
    count, peak = records[4]['count'], records[-1]['memoryPeakBytes']
    require(type(count) is int and 1 <= count <= 10000, 'evidence_model_count')
    require(type(peak) is int and 0 < peak <= 1073741824, 'evidence_memory')
    return {'providerFailureTest': fail_provider, 'modelCount': count, 'memoryPeakBytes': peak,
            'artifactHashes': {'hapi': hashes['hapi'], 'codex': hashes['codex']}}


def worker(fail_provider=False):
    """Only invoked in the constrained container; no host/default settings lookup."""
    stage = 'isolation'
    children = []
    server = None
    state = {'requests': 0, 'accepted': 0, 'rejected': 0}
    try:
        require(sys.platform == 'linux' and os.uname().machine == 'aarch64'
                and os.getuid() == 65534 and Path('/.dockerenv').exists(), stage)
        require(socket.if_nameindex() == [(1, 'lo')], stage)
        status = Path('/proc/self/status').read_text()
        require(re.search(r'CapEff:\s+0+\n', status) and re.search(r'NoNewPrivs:\s+1\n', status), stage)
        cap = Path('/sys/fs/cgroup/memory.max').read_text().strip()
        require(cap != 'max' and int(cap) <= 1073741824, stage)
        require(Path('/sys/fs/cgroup/memory.swap.max').read_text().strip() == '0', stage)
        cpu = Path('/sys/fs/cgroup/cpu.max').read_text().split()
        require(cpu[0] != 'max' and int(cpu[0]) / int(cpu[1]) <= .75, stage)
        pids = Path('/sys/fs/cgroup/pids.max').read_text().strip()
        require(pids != 'max' and int(pids) <= 128, stage)
        for path in ('/Users', '/home/moses', '/var/run/docker.sock', '/root/.codex', '/root/.hapi'):
            try:
                require(not Path(path).exists(), stage)
            except PermissionError:
                pass
        allowed_env = {'PATH', 'HOSTNAME', 'HOME', 'LANG', 'GPG_KEY', 'PYTHON_VERSION',
                       'PYTHON_SHA256', 'LC_CTYPE'}
        require(set(os.environ) <= allowed_env, stage)
        # Only documentation-reserved IP; netns must reject outbound attempts.
        with socket.socket() as probe:
            probe.settimeout(.5)
            try:
                probe.connect(('192.0.2.1', 443))
            except OSError:
                pass
            else:
                raise RuntimeError('network_escape')
        hashes = json.loads(Path('/opt/gate/artifacts.json').read_text())
        require(isinstance(hashes, dict) and set(hashes) == {'hapi', 'codex'}
                and all(isinstance(v, str) and re.fullmatch(r'[0-9a-f]{64}', v) for v in hashes.values()),
                'artifact_manifest')
        for name in ('hapi', 'codex'):
            binary = Path('/opt/gate/' + ('bin/codex' if name == 'codex' else name))
            with binary.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            require(actual == hashes[name], 'artifact_hash')
        emit(stage, passed=True, architecture='aarch64', memoryMax=int(cap), artifactHashes=hashes)
        root = Path('/work/run')
        root.mkdir(mode=0o700)
        for part in ('home', 'hapi', 'codex', 'project', 'tmp'):
            (root / part).mkdir(mode=0o700)
        env = {'HOME': str(root/'home'), 'HAPI_HOME': str(root/'hapi'),
               'CODEX_HOME': str(root/'codex'), 'TMPDIR': str(root/'tmp'),
               'PATH': '/opt/gate:/opt/gate/bin:/opt/gate/codex-path:/usr/local/bin:/usr/bin:/bin', 'LANG': 'C.UTF-8',
               'NO_PROXY': '127.0.0.1,localhost'}
        for name in ('hapi', 'codex'):
            version = subprocess.run(['/opt/gate/'+('bin/codex' if name == 'codex' else name), '--version'], env=env,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15)
            require(version.returncode == 0, name+'_version')
            require((b'0.30.7' if name == 'hapi' else b'0.154.0') in version.stdout, name+'_version')
        emit('versions', passed=True, hapi='0.30.7', codex='0.154.0')
        nonce = secrets.token_hex(12)
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), fixture_handler(nonce, state, fail_provider))
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        config = f'''model = "local-fixture"
model_provider = "local_fixture"
approval_policy = "never"
sandbox_mode = "read-only"
cli_auth_credentials_store = "file"
web_search = "disabled"
check_for_update_on_startup = false
[features]
responses_websockets = false
responses_websockets_v2 = false
[model_providers.local_fixture]
name = "Offline fixture"
base_url = "http://127.0.0.1:{server.server_port}/v1"
wire_api = "responses"
requires_openai_auth = false
request_max_retries = 0
stream_max_retries = 0
supports_websockets = false
'''
        (root/'codex/config.toml').write_text(config)
        with socket.socket() as free:
            free.bind(('127.0.0.1', 0))
            port = free.getsockname()[1]
        origin = f'http://127.0.0.1:{port}'
        access = secrets.token_urlsafe(32)
        env.update(CLI_API_TOKEN=access, HAPI_API_URL=origin, HAPI_PUBLIC_URL=origin,
                   HAPI_LISTEN_HOST='127.0.0.1', HAPI_LISTEN_PORT=str(port),
                   DB_PATH=str(root/'test.db'), HAPI_IOS_PUSH='off',
                   TELEGRAM_NOTIFICATION='false', SERVERCHAN_NOTIFICATION='false')

        def launch(args):
            process = subprocess.Popen(['/opt/gate/hapi', *args], cwd=root/'project', env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True)
            children.append(process)
            return process

        def request(path, body=None, auth=None, timeout=5):
            req = urllib.request.Request(origin+path, None if body is None else json.dumps(body).encode(),
                {'Content-Type': 'application/json', **({'Authorization': 'Bearer '+auth} if auth else {})})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    raw = response.read(4_000_000)
                    return response.status, json.loads(raw) if raw else {}
            except urllib.error.HTTPError as error:
                return error.code, {}

        def until(check, seconds=30):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                require(all(p.poll() is None for p in children), stage+'_process_exit')
                try:
                    value = check()
                    if value:
                        return value
                except (OSError, ValueError):
                    pass
                time.sleep(.5)
            raise RuntimeError(stage+'_timeout')

        stage = 'hub'
        launch(['hub'])
        until(lambda: request('/health')[0] == 200)
        require(request('/companion/sessions')[0] == 401, 'unauth_companion')
        code, payload = request('/api/auth', {'accessToken': access})
        require(code == 200 and payload.get('token'), 'auth')
        jwt = payload['token']
        emit(stage, passed=True, health=200, auth=200, unauthCompanion=401)
        stage = 'runner'
        launch(['runner', 'start-sync', '--workspace-root', str(root/'project')])
        def machine():
            code, page = request('/api/machines', auth=jwt)
            matches = [m for m in page.get('machines', []) if m.get('active') is True]
            return matches[0]['id'] if code == 200 and len(matches) == 1 else None
        machine_id = until(machine)
        emit(stage, passed=True, activeMachines=1)
        stage = 'models'
        code, models = request('/api/machines/'+machine_id+'/codex-models', auth=jwt, timeout=40)
        require(code == 200 and models.get('success') is True and models.get('models'), stage)
        require(state['requests'] == 0, 'models_must_not_generate')
        emit(stage, passed=True, count=len(models['models']), providerRequests=0)
        stage = 'spawn'
        code, spawned = request('/api/machines/'+machine_id+'/spawn', {
            'directory': str(root/'project'), 'agent': 'codex', 'model': 'local-fixture',
            'permissionMode': 'read-only', 'sessionType': 'simple', 'startingMode': 'remote'}, jwt, 60)
        session_id = spawned.get('sessionId') or spawned.get('id')
        require(code == 200 and isinstance(session_id, str) and spawned.get('type') != 'error', stage)
        def session():
            code, body = request('/api/sessions/'+session_id, auth=jwt)
            require(code == 200, 'session_http')
            return body.get('session', body)
        until(lambda: session().get('active') is True)
        require(session().get('metadata', {}).get('machineId') == machine_id, 'session_machine_identity')
        # Actual process flags, never values/tokens, establish authenticated TCP selection.
        codex_tcp = False
        for proc in Path('/proc').glob('[0-9]*'):
            try:
                args = (proc/'cmdline').read_bytes().split(b'\0')
                if args[0] == b'/opt/gate/bin/codex' and b'app-server' in args:
                    codex_tcp = (b'--ws-auth' in args and b'capability-token' in args
                                 and any(a.startswith(b'ws://127.0.0.1:') for a in args))
            except OSError:
                pass
        require(codex_tcp, 'real_codex_authenticated_tcp')
        emit(stage, passed=True, webhook=True, authenticatedCodexTCP=True)
        stage = 'message'
        local_id = 'arm-test-' + nonce
        code, payload = request('/api/sessions/'+session_id+'/messages', {
            'text': 'No tools. Reply with the fixture text. Test nonce: '+nonce, 'localId': local_id}, jwt)
        require(code == 200 and payload.get('ok') is True, stage)
        emit(stage, passed=True)
        stage = 'reply'
        def completed():
            code, page = request('/api/sessions/'+session_id+'/messages?limit=100', auth=jwt)
            require(code == 200, 'messages_http')
            messages = page.get('messages', [])
            reply = has_reply(messages, local_id, nonce)
            if fail_provider:
                errors = [m for m in messages if m.get('content', {}).get('role') == 'agent'
                          and 'Codex error:' in json.dumps(m.get('content', {}))]
                return state['rejected'] > 0 and errors and not reply and session().get('thinking') is not True
            return reply and session().get('thinking') is not True
        until(completed, 60)
        require(state['requests'] == 1, 'provider_request_count')
        require(state['accepted'] == (0 if fail_provider else 1), 'provider_accept_count')
        emit(stage, passed=True, providerRequests=state['requests'], failurePropagated=fail_provider,
             exactReply=not fail_provider, thinking=False)
        emit('result', status='ARM_WORKER_CHAIN_COMPLETE', protocol=WORKER_PROTOCOL, productionApproved=False,
             vmSystemdVerified=False, rollbackVerified=False,
             memoryPeakBytes=int(Path('/sys/fs/cgroup/memory.peak').read_text()))
        return 0
    except Exception:
        emit('result', status='FAIL', failedStage=stage,
             reason='worker_gate_failed',
             providerRequests=state['requests'], productionApproved=False)
        return 1
    finally:
        for process in reversed(children):
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=4)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        if server:
            server.shutdown()


@contextmanager
def termination_scope(cleaning=False):
    """SIGTERM unwinds normally; a second signal cannot interrupt owned cleanup."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = {}
    def interrupted(_number, _frame):
        raise KeyboardInterrupt()
    try:
        for number in (signal.SIGTERM, signal.SIGINT):
            previous[number] = signal.signal(number, signal.SIG_IGN if cleaning else interrupted)
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def inspect_owned(client, name, owner, image):
    ids = client.run('ps', '-a', '-q', '--no-trunc', '--filter', 'name=^/'+name+'$').decode().split()
    require(len(ids) <= 1 and all(re.fullmatch(r'[0-9a-f]{64}', cid) for cid in ids), 'container_identity')
    if not ids:
        return None
    result = json.loads(client.run('inspect', ids[0]))
    require(isinstance(result, list) and len(result) == 1, 'container_identity')
    container = result[0]
    require(container.get('Id') == ids[0] and container.get('Name') == '/'+name
            and container.get('Image') == image
            and container.get('Config', {}).get('Labels', {}).get(OWNER_LABEL) == owner,
            'container_ownership_mismatch')
    return container


def cleanup_owned(client, name, owner, image, acknowledged):
    """Unknown create results are inspected, never assumed absent or globally pruned."""
    removed = False
    for attempt in range(2):
        try:
            container = inspect_owned(client, name, owner, image)
            if container is None:
                # A timed-out create may still complete later. Don't certify absence.
                return acknowledged or removed
            client.run('rm', '-f', container['Id'])
            removed = True
            if inspect_owned(client, name, owner, image) is None:
                return True
        except Exception:
            pass
        if attempt == 0:
            time.sleep(.1)
    return False


def run_host_transaction(client, image, fail_provider=False):
    """Public orchestration seam; client is the Docker boundary, not a fake Hub."""
    name = 'hsu-arm-test-' + secrets.token_hex(6)
    owner = secrets.token_hex(16)
    args = container_args(image, name)
    args[1:1] = ['--label', OWNER_LABEL+'='+owner]
    if fail_provider:
        args.append('--fail-provider')
    attempted = acknowledged = False
    cleanup_verified = True
    summary = None
    phase = 'preflight'
    try:
        info = json.loads(client.run('info', '--format', '{{json .}}'))
        require(info.get('Architecture') == 'aarch64' and type(info.get('MemTotal')) is int
                and info['MemTotal'] >= 2_000_000_000, 'daemon_resource_floor')
        require(not client.run('ps', '-q').strip(), 'other_containers_running_defer')
        phase = 'create'
        attempted = True
        created_id = client.run(*args).decode().strip()
        require(re.fullmatch(r'[0-9a-f]{64}', created_id), 'create_identity')
        acknowledged = True
        phase = 'inspect'
        config = inspect_owned(client, name, owner, image)
        require(config is not None and config['Id'] == created_id, 'created_identity')
        require(not config['Mounts'] and config['HostConfig']['NetworkMode'] == 'none'
                and config['HostConfig']['ReadonlyRootfs'] is True, 'docker_config_mismatch')
        require(safe_container_env(config['Config'].get('Env')), 'container_environment')
        # Point-in-time only: unrelated Docker clients do not participate in our lock.
        require(not client.run('ps', '-q').strip(), 'other_containers_running_defer')
        phase = 'start'
        output = client.collect(created_id)
        phase = 'evidence'
        summary = validate_worker_output(output, fail_provider)
        phase = 'exit'
        end = inspect_owned(client, name, owner, image)['State']
        require(type(end['ExitCode']) is int and end['ExitCode'] == 0
                and end['OOMKilled'] is False and end['Running'] is False, 'container_gate_failed')
    except BaseException:
        # Includes user interruption and SIGTERM. Never interpolate Docker/worker text.
        summary = None
    finally:
        with termination_scope(cleaning=True):
            if attempted:
                cleanup_verified = cleanup_owned(client, name, owner, image, acknowledged)
    if summary is not None and cleanup_verified:
        emit('host_result', status='ARM_CONTAINER_PARTIAL_PASS', protocol=WORKER_PROTOCOL,
             cleanupVerified=True, productionApproved=False, vmSystemdVerified=False,
             rollbackVerified=False, **summary)
        return 0
    fields = {'status': 'FAIL', 'phase': phase if cleanup_verified else 'cleanup', 'cleanupVerified': cleanup_verified,
              'productionApproved': False}
    if not cleanup_verified:
        # Non-sensitive generated identifiers for exact manual follow-up; not credentials.
        fields.update(residualContainer=name, ownershipLabel=owner,
                      cleanupAction='inspect_exact_name_and_owner_before_removal')
    emit('host_result', **fields)
    return 1


def host(image, fail_provider=False):
    require(sys.platform == 'darwin', 'local_mac_host_required')
    # Stable lock is per local user/socket, independent of cwd or checkout.
    lease = Path('/private/tmp') / ('hsu-arm-colima-'+str(os.getuid())+'.lock')
    with termination_scope(), exclusive_lease(lease), isolated_docker(str(Path.home())) as client:
        return run_host_transaction(client, image, fail_provider)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--image')
    parser.add_argument('--fail-provider', action='store_true')
    options = parser.parse_args()
    if options.worker:
        sys.exit(worker(options.fail_provider))
    try:
        sys.exit(host(options.image, options.fail_provider))
    except BaseException:
        emit('host_result', status='FAIL', phase='host_preflight_or_cleanup', productionApproved=False)
        sys.exit(1)
