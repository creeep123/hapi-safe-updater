import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    'local_provider', Path(__file__).parents[1] / 'bin' / 'verify-local-codex-provider.py')
provider = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(provider)


class LocalProviderTests(unittest.TestCase):
    def test_child_environment_does_not_inherit_accounts_or_proxies(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {
            'OPENAI_API_KEY': 'synthetic-account-canary',
            'CLI_API_TOKEN': 'synthetic-hapi-canary',
            'HTTPS_PROXY': 'http://127.0.0.1:1',
            'CODEX_HOME': '/not-the-test-home',
        }):
            env = provider.isolated_env(Path(td))
            self.assertNotIn('OPENAI_API_KEY', env)
            self.assertNotIn('CLI_API_TOKEN', env)
            self.assertEqual(env['HTTPS_PROXY'], 'http://127.0.0.1:9')
            self.assertEqual(env['NO_PROXY'], '127.0.0.1,localhost')
            self.assertEqual(Path(env['CODEX_HOME']).parent, Path(td).resolve())
            self.assertEqual(Path(env['HOME']), Path(td).resolve())

    @unittest.skipUnless(os.environ.get('HSU_RUN_LOCAL_CODEX_TEST') == '1', 'explicit local opt-in')
    def test_real_codex_receives_fake_provider_reply_without_external_access(self):
        result = provider.run_local_check(Path(os.environ['HSU_TEST_CODEX_BIN']))
        self.assertEqual(result['reply'], 'HSU_LOCAL_PROVIDER_OK')
        self.assertEqual(result['provider_requests'], 1)
        self.assertTrue(result['isolation_passed'])
        self.assertTrue(result['cleanup_passed'])

    @unittest.skipUnless(os.environ.get('HSU_RUN_LOCAL_CODEX_TEST') == '1', 'explicit local opt-in')
    def test_provider_failure_is_not_reported_as_a_successful_reply(self):
        result = provider.run_local_check(Path(os.environ['HSU_TEST_CODEX_BIN']), fail_provider=True)
        self.assertTrue(result['provider_failure_rejected'])
        self.assertEqual(result['provider_requests'], 1)
        self.assertNotIn('reply', result)
        self.assertTrue(result['cleanup_passed'])

    def test_linux_cannot_accidentally_run_the_mac_adapter(self):
        with patch.object(provider.sys, 'platform', 'linux'):
            with self.assertRaisesRegex(RuntimeError, 'unsupported_isolation_platform_no_fallback'):
                provider.run_local_check('/nonexistent/codex')

    @unittest.skipUnless(provider.sys.platform == 'darwin', 'macOS isolation')
    def test_timeout_reaps_only_the_test_process(self):
        with tempfile.TemporaryDirectory(dir='/private/tmp') as td:
            root = Path(td).resolve()
            (root / 'tmp').mkdir()
            code = 'import os,pathlib,time;pathlib.Path("test.pid").write_text(str(os.getpid()));time.sleep(60)'
            with self.assertRaisesRegex(RuntimeError, 'isolated_process_timeout'):
                provider.guarded_run([provider.sys.executable, '-c', code],
                    provider.sandbox_profile(root, 9), root, 1)
            pid = int((root / 'test.pid').read_text())
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)


if __name__ == '__main__':
    unittest.main()
