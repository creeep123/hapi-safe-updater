#!/usr/bin/env python3
"""Local-only provider seam; never a production or VM gate launcher."""
from pathlib import Path
import argparse
import http.server
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import threading


def isolated_env(root):
    root = Path(root).resolve()
    return {'HOME': str(root), 'CODEX_HOME': str(root / 'codex'),
            'HAPI_HOME': str(root / 'hapi'), 'TMPDIR': str(root / 'tmp'),
            'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'LANG': 'en_US.UTF-8',
            # Explicit dead proxy suppresses macOS system-proxy discovery.
            # Loopback provider bypasses it; the sandbox forbids port 9 anyway.
            'HTTP_PROXY': 'http://127.0.0.1:9', 'HTTPS_PROXY': 'http://127.0.0.1:9',
            'ALL_PROXY': 'http://127.0.0.1:9',
            'http_proxy': 'http://127.0.0.1:9', 'https_proxy': 'http://127.0.0.1:9',
            'all_proxy': 'http://127.0.0.1:9',
            'NO_PROXY': '127.0.0.1,localhost', 'no_proxy': '127.0.0.1,localhost'}


def sandbox_profile(root, port):
    # macOS only. No unguarded fallback on Linux or unavailable sandbox-exec.
    return f'''(version 1)
(allow default)
(deny network*)
(allow network-outbound (remote ip "localhost:{port}"))
(allow network-bind (local ip "localhost:*"))
(deny file-read* (subpath "/Users") (subpath "/etc/codex")
 (subpath "/Library/Application Support/Codex"))
(deny file-write*)
(allow file-read* file-write* (subpath {json.dumps(str(root))}))
(allow file-write* (literal "/dev/null"))
(deny mach-lookup (global-name "com.apple.securityd"))
'''


def guarded_run(command, profile, root, timeout):
    proc = subprocess.Popen(['/usr/bin/sandbox-exec', '-p', profile, *command],
        cwd=root, env=isolated_env(root), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return proc.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        raise RuntimeError('isolated_process_timeout') from None
    finally:
        # Only the newly created test process group; never name-based killing.
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=3)
        proc.stdout.close()
        proc.stderr.close()


def run_local_check(codex_binary, fail_provider=False, timeout=30):
    if sys.platform != 'darwin' or not Path('/usr/bin/sandbox-exec').is_file():
        raise RuntimeError('unsupported_isolation_platform_no_fallback')
    codex_binary = Path(codex_binary).resolve(strict=True)
    if not codex_binary.is_file() or not os.access(codex_binary, os.X_OK):
        raise RuntimeError('invalid_codex_executable')
    state = {'requests': 0, 'invalid': False}
    nonce = secrets.token_hex(16)

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Never log request bodies/headers.

        def do_GET(self):
            self.send_error(404)

        def do_POST(self):
            state['requests'] += 1
            length = int(self.headers.get('Content-Length', '0'))
            if self.path != '/v1/responses' or not 0 < length < 2_000_000:
                state['invalid'] = True
                self.send_error(400)
                return
            raw = self.rfile.read(length)
            valid = nonce.encode() in raw and not self.headers.get('Authorization')
            if not valid or state['requests'] > 1 or fail_provider:
                state['invalid'] = not valid
                self.send_error(400)
                return
            item = {'id': 'msg_local', 'type': 'message', 'role': 'assistant',
                    'status': 'completed', 'content': [{'type': 'output_text',
                    'text': 'HSU_LOCAL_PROVIDER_OK', 'annotations': []}]}
            response = {'id': 'resp_local', 'object': 'response',
                        'status': 'completed', 'output': [item],
                        'usage': {'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2}}
            events = [
                {'type': 'response.created', 'response': {**response, 'status': 'in_progress', 'output': []}},
                {'type': 'response.output_item.added', 'output_index': 0,
                 'item': {**item, 'status': 'in_progress', 'content': []}},
                {'type': 'response.output_text.delta', 'item_id': 'msg_local',
                 'output_index': 0, 'content_index': 0, 'delta': 'HSU_LOCAL_PROVIDER_OK'},
                {'type': 'response.output_item.done', 'output_index': 0, 'item': item},
                {'type': 'response.completed', 'response': response},
            ]
            body = ''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with tempfile.TemporaryDirectory(prefix='hsu-local-provider-', dir='/private/tmp') as td:
        root = Path(td).resolve()
        for name in ('codex', 'tmp', 'work', 'hapi'):
            (root / name).mkdir(mode=0o700)
        with http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler) as server:
            server.daemon_threads = True
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            port = server.server_port
            profile = sandbox_profile(root, port)
            try:
                # Prove denial using synthetic endpoints and this public source file,
                # not by attempting to read any actual production credentials.
                with socket.socket() as forbidden:
                    forbidden.bind(('127.0.0.1', 0)); forbidden.listen()
                    probe = """import socket,sys
s=socket.create_connection(('127.0.0.1',int(sys.argv[1])),2);s.close()
try: socket.create_connection(('127.0.0.1',int(sys.argv[2])),1)
except PermissionError: pass
else: sys.exit(2)
try: open(sys.argv[3]).read(1)
except PermissionError: pass
else: sys.exit(3)
"""
                    code, _, _ = guarded_run([sys.executable, '-c', probe, str(port),
                        str(forbidden.getsockname()[1]), str(Path(__file__).resolve())], profile, root, 10)
                    if code != 0:
                        raise RuntimeError('isolation_probe_failed_no_codex_started')
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
name = "Local test fixture"
base_url = "http://127.0.0.1:{port}/v1"
wire_api = "responses"
requires_openai_auth = false
request_max_retries = 0
stream_max_retries = 0
supports_websockets = false
'''
                (root / 'codex' / 'config.toml').write_text(config)
                try:
                    code, stdout, _ = guarded_run([str(codex_binary), 'exec', '--json',
                        '--ephemeral', '--skip-git-repo-check', '--cd', str(root / 'work'),
                        'Reply with the fixture response only. No tools. Test nonce: '+nonce],
                        profile, root, timeout)
                except RuntimeError:
                    raise RuntimeError('isolated_codex_timeout_requests_'+str(state['requests'])) from None
                if state['invalid']:
                    raise RuntimeError('provider_request_invalid')
                if fail_provider:
                    if code == 0 or state['requests'] != 1:
                        raise RuntimeError('failure_not_propagated')
                    result = {'provider_failure_rejected': True}
                else:
                    items = []
                    for line in stdout.splitlines():
                        try:
                            items.append(json.loads(line))
                        except ValueError:
                            continue
                    replies = [x.get('item', {}).get('text') for x in items
                               if x.get('type') == 'item.completed'
                               and x.get('item', {}).get('type') == 'agent_message']
                    if code != 0 or replies != ['HSU_LOCAL_PROVIDER_OK'] or state['requests'] != 1:
                        raise RuntimeError('real_codex_reply_gate_failed_exit_'+str(code)+'_requests_'+str(state['requests']))
                    result = {'reply': replies[0]}
            finally:
                server.shutdown()
                server_thread.join(timeout=3)
        result.update(provider_requests=state['requests'], isolation_passed=True)
    result['cleanup_passed'] = not root.exists() and not server_thread.is_alive()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-binary', required=True)
    parser.add_argument('--fail-provider', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(run_local_check(args.codex_binary, args.fail_provider)))
    except Exception as exc:
        # Stable error codes only: no subprocess stderr, auth or response dumps.
        print(json.dumps({'ok': False, 'errorType': type(exc).__name__,
                          'stage': str(exc) if isinstance(exc, RuntimeError) else 'local_gate_failed'}))
        sys.exit(1)
