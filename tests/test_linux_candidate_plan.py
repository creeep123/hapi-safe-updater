import importlib.util
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('linux_plan',
    Path(__file__).parents[1] / 'bin' / 'plan-linux-candidate.py')
plan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plan)


def request():
    return {'runId': 'review-001', 'rootfs': '/var/tmp/hsu-linux-candidate-review-001/rootfs',
            'artifactHashes': {'hapi': 'a' * 64, 'codex': 'b' * 64, 'rollback': 'c' * 64},
            'memoryMaxMiB': 512, 'cpuQuotaPercent': 25,
            'runtimeMaxSeconds': 180, 'tasksMax': 64}


def observations():
    return {'stages': ['isolation', 'hub', 'runner', 'codex', 'spawn', 'message',
                       'provider', 'reply', 'complete', 'cleanup'],
            'isolation': {'privateNetwork': True, 'credentialsIsolated': True,
                          'resourceLimitsEnforced': True, 'productionPathsHidden': True},
            'apiStatuses': {'health': 200, 'auth': 200, 'spawn': 200, 'message': 200},
            'hubOrigin': 'http://127.0.0.1:32101',
            'providerOrigin': 'http://127.0.0.1:32102',
            'machineId': 'test-machine', 'sessionMachineId': 'test-machine',
            'sessionId': 'test-session', 'replySessionId': 'test-session',
            'codexExecutableVerified': True, 'appServerInitialized': True,
            'webhookObserved': True, 'sessionActive': True, 'thinking': False,
            'nonce': 'review-nonce', 'providerNonce': 'review-nonce',
            'userSeq': 4, 'replySeq': 5, 'replyRole': 'agent',
            'replyText': 'HSU_FAKE_PROVIDER_OK:review-nonce',
            'providerRequests': 1, 'providerAuthSeen': False,
            'providerForwarded': False, 'remainingProcesses': 0,
            'remainingListeners': 0, 'temporarySecretsRemoved': True}


class LinuxPlanTests(unittest.TestCase):
    def test_plan_is_offline_private_and_explicitly_not_execution_ready(self):
        result = plan.make_plan(request())
        self.assertEqual(result['status'], 'PLAN_ONLY_NOT_EXECUTION_READY')
        unit = result['unitProperties']
        self.assertEqual(unit['PrivateNetwork'], 'yes')
        self.assertEqual(unit['RootDirectory'], request()['rootfs'])
        self.assertEqual(unit['MemoryMax'], '512M')
        self.assertEqual(unit['MemorySwapMax'], '0')
        self.assertEqual(unit['KillMode'], 'control-group')
        self.assertNotIn('executeCommand', result)

    def test_production_paths_unknown_fields_and_bad_limits_are_refused(self):
        bad = [
            {'rootfs': '/'}, {'rootfs': '/home/moses/.hapi'},
            {'rootfs': '/var/tmp/hsu-linux-candidate-review-001/../rootfs'},
            {'runId': 'x;reboot'}, {'memoryMaxMiB': 0}, {'memoryMaxMiB': 999999},
            {'cpuQuotaPercent': 101}, {'tasksMax': True}, {'runtimeMaxSeconds': 0},
            {'Environment': {'CLI_API_TOKEN': 'synthetic'}},
            {'artifactHashes': {'hapi': 'a' * 64}},
        ]
        for change in bad:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    plan.make_plan({**request(), **change})

    def test_full_chain_observations_are_not_called_runtime_attestation(self):
        result = plan.evaluate_observations(observations())
        self.assertEqual(result['status'], 'ASSERTIONS_PASS_NOT_RUNTIME_ATTESTATION')
        self.assertFalse(result['productionApproved'])

    def test_incomplete_forged_wrong_route_or_unclean_chain_is_rejected(self):
        changes = [
            {'stages': ['hub', 'runner', 'reply']},
            {'isolation': {}},
            {'isolation': {**observations()['isolation'], 'privateNetwork': False}},
            {'apiStatuses': {'health': 200}},
            {'hubOrigin': 'https://production.example'},
            {'providerOrigin': 'http://localhost:32102'},
            {'hubOrigin': 'http://user:password@127.0.0.1:32101'},
            {'providerOrigin': 'http://127.0.0.1:32101'},
            {'sessionMachineId': 'different-machine'},
            {'replySessionId': 'different-session'},
            {'codexExecutableVerified': False}, {'appServerInitialized': False},
            {'webhookObserved': False}, {'sessionActive': False},
            {'providerRequests': 0}, {'providerRequests': 2}, {'providerRequests': True},
            {'providerNonce': 'wrong'}, {'providerAuthSeen': True},
            {'providerForwarded': True}, {'replyRole': 'user'},
            {'replySeq': 3}, {'userSeq': True}, {'replyText': 'unrelated reply'},
            {'thinking': True}, {'remainingProcesses': 1},
            {'remainingListeners': 1}, {'temporarySecretsRemoved': False},
        ]
        for change in changes:
            with self.subTest(change=change):
                self.assertEqual(plan.evaluate_observations({**observations(), **change})['status'],
                                 'ASSERTIONS_FAIL')
        self.assertEqual(plan.evaluate_observations({})['status'], 'ASSERTIONS_FAIL')

    def test_plan_does_not_export_caller_environment_or_accept_credentials(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {'CLI_API_TOKEN': 'synthetic-secret',
                                     'SSH_AUTH_SOCK': '/synthetic/socket'}):
            result = plan.make_plan(request())
            self.assertNotIn('CLI_API_TOKEN', result['childEnvironment'])
            self.assertNotIn('SSH_AUTH_SOCK', result['childEnvironment'])
            self.assertNotIn('synthetic-secret', str(result))


if __name__ == '__main__':
    unittest.main()
