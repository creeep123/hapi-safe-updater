#!/usr/bin/env python3
"""Offline Linux candidate plan compiler. No execution mode, SSH or subprocesses."""
import argparse
import json
import re
from urllib.parse import urlsplit


def evaluate_observations(evidence):
    """Validate normalized public-interface observations, NOT their provenance.

    The future isolated worker must collect these from the actual processes/APIs.
    Passing user-supplied JSON here never constitutes an actual Linux gate pass.
    """
    def need(ok, reason):
        if not ok:
            raise ValueError(reason)

    try:
        need(evidence['stages'] == ['isolation', 'hub', 'runner', 'codex', 'spawn',
              'message', 'provider', 'reply', 'complete', 'cleanup'], 'missing_or_reordered_stage')
        need(set(evidence['isolation']) == {'privateNetwork', 'credentialsIsolated',
              'resourceLimitsEnforced', 'productionPathsHidden'} and
              all(v is True for v in evidence['isolation'].values()), 'isolation_not_proven')
        need(evidence['apiStatuses'] == {'health': 200, 'auth': 200, 'spawn': 200,
              'message': 200}, 'api_stage_failed')
        for field in ('hubOrigin', 'providerOrigin'):
            url = urlsplit(evidence[field])
            need(url.scheme == 'http' and url.hostname == '127.0.0.1'
                 and url.port is not None and 1024 <= url.port <= 65535
                 and not url.username and not url.password and url.path in ('', '/')
                 and not url.query and not url.fragment, 'nonisolated_origin')
        need(evidence['hubOrigin'].rstrip('/') != evidence['providerOrigin'].rstrip('/'),
             'hub_and_provider_must_be_distinct')
        for key in ('machineId', 'sessionId', 'nonce'):
            need(isinstance(evidence[key], str) and 1 <= len(evidence[key]) <= 128, 'invalid_identity')
        need(evidence['machineId'] == evidence['sessionMachineId'] and
             evidence['sessionId'] == evidence['replySessionId'], 'identity_mismatch')
        need(all(evidence[k] is True for k in ('codexExecutableVerified', 'appServerInitialized',
             'webhookObserved', 'sessionActive')), 'real_runner_codex_chain_incomplete')
        need(type(evidence['providerRequests']) is int and evidence['providerRequests'] == 1
             and evidence['providerNonce'] == evidence['nonce']
             and evidence['providerAuthSeen'] is False
             and evidence['providerForwarded'] is False, 'provider_boundary_failed')
        need(type(evidence['userSeq']) is int and type(evidence['replySeq']) is int
             and 0 < evidence['userSeq'] < evidence['replySeq'], 'reply_order_invalid')
        need(evidence['replyRole'] == 'agent' and
             evidence['replyText'] == 'HSU_FAKE_PROVIDER_OK:' + evidence['nonce']
             and evidence['thinking'] is False, 'reply_or_completion_invalid')
        need(type(evidence['remainingProcesses']) is int and evidence['remainingProcesses'] == 0
             and type(evidence['remainingListeners']) is int and evidence['remainingListeners'] == 0
             and evidence['temporarySecretsRemoved'] is True, 'cleanup_incomplete')
    except (KeyError, TypeError, ValueError, AttributeError):
        return {'status': 'ASSERTIONS_FAIL', 'productionApproved': False}
    return {'status': 'ASSERTIONS_PASS_NOT_RUNTIME_ATTESTATION', 'productionApproved': False}


def make_plan(request):
    fields = {'runId', 'rootfs', 'artifactHashes', 'memoryMaxMiB',
              'cpuQuotaPercent', 'runtimeMaxSeconds', 'tasksMax'}
    if not isinstance(request, dict) or set(request) != fields:
        raise ValueError('invalid_plan_fields')
    run_id = request['runId']
    if not isinstance(run_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,31}', run_id):
        raise ValueError('invalid_run_id')
    if request['rootfs'] != '/var/tmp/hsu-linux-candidate-' + run_id + '/rootfs':
        raise ValueError('invalid_staging_root')
    hashes = request['artifactHashes']
    if (not isinstance(hashes, dict) or set(hashes) != {'hapi', 'codex', 'rollback'}
            or any(not isinstance(v, str) or not re.fullmatch(r'[0-9a-f]{64}', v)
                   for v in hashes.values())):
        raise ValueError('invalid_artifact_hashes')
    for key, low, high in [('memoryMaxMiB', 128, 1024), ('cpuQuotaPercent', 1, 25),
                           ('runtimeMaxSeconds', 30, 300), ('tasksMax', 16, 128)]:
        if type(request[key]) is not int or not low <= request[key] <= high:
            raise ValueError('invalid_resource_limit')
    return {
        'status': 'PLAN_ONLY_NOT_EXECUTION_READY',
        'unitName': 'hsu-linux-candidate-' + run_id,
        'artifactHashes': request['artifactHashes'],
        'unitProperties': {
            'RootDirectory': request['rootfs'], 'DynamicUser': 'yes',
            'PrivateNetwork': 'yes', 'PrivateDevices': 'yes',
            'PrivateTmp': 'yes', 'ProtectHome': 'yes', 'ProtectSystem': 'strict',
            'ProtectProc': 'invisible', 'ProcSubset': 'pid',
            'NoNewPrivileges': 'yes', 'CapabilityBoundingSet': '',
            'RestrictAddressFamilies': 'AF_UNIX AF_INET AF_INET6',
            'RestrictNamespaces': 'yes', 'RestrictSUIDSGID': 'yes',
            'LockPersonality': 'yes', 'UMask': '0077',
            'TemporaryFileSystem': '/work:rw,size=128M,mode=1777',
            'MemoryMax': str(request['memoryMaxMiB']) + 'M', 'MemorySwapMax': '0',
            'CPUQuota': str(request['cpuQuotaPercent']) + '%',
            'TasksMax': str(request['tasksMax']),
            'RuntimeMaxSec': str(request['runtimeMaxSeconds']),
            'TimeoutStopSec': '5', 'KillMode': 'control-group',
            'SendSIGKILL': 'yes', 'OOMPolicy': 'stop', 'Restart': 'no',
            'StandardInput': 'null', 'StandardOutput': 'null', 'StandardError': 'null',
        },
        'childEnvironment': {
            'HOME': '/work/home', 'CODEX_HOME': '/work/codex',
            'HAPI_HOME': '/work/hapi', 'TMPDIR': '/work/tmp',
            'PATH': '/opt/hsu/bin:/usr/bin:/bin',
            'NO_PROXY': '127.0.0.1,localhost',
        },
        'requiredBeforeExecution': [
            'separate_VM_authorization', 'reviewed_offline_minimal_rootfs',
            'artifact_hash_and_ELF_verification', 'rootfs_no_secrets_or_host_symlinks',
            'actual_memory_CPU_disk_headroom', 'systemd_property_support',
            'private_netns_mounts_and_cgroup_probes', 'full_stack_worker_and_evidence_collector',
        ],
        'workflow': [
            'isolation_probes_before_any_HAPI_or_Codex_process',
            'loopback_only_non_forwarding_fake_provider',
            'temporary_Hub_new_schema27_DB_and_ephemeral_auth',
            'temporary_Runner_registered_only_to_test_Hub',
            'real_Codex_app_server_authenticated_TCP_initialize',
            'Hub_spawn_webhook_active_session',
            'Hub_user_message_to_Runner_to_real_Codex_to_fake_provider',
            'exact_agent_reply_after_user_message_then_turn_complete',
            'provider_failure_no_false_success',
            'isolated_entire_cgroup_cleanup_and_no_remaining_listeners',
        ],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    args = parser.parse_args()
    try:
        with open(args.manifest) as source:
            request = json.load(source)
        print(json.dumps(make_plan(request), indent=2))
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({'status': 'REFUSED', 'reason': 'invalid_plan_input'}))
        raise SystemExit(1)
