"""Read and test the deployed EventBridge filter. Does not publish events or start jobs.

From the repository root: python3 monitoring/test_glue_failure_pattern.py
We ran these seven cases in AWS on 22 October 2026; all passed.
"""
import argparse
import json
import uuid
from datetime import datetime, timezone

import boto3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-account', default='470551642447',
                        help='AWS account containing the deployed rule (default: original project account)')
    parser.add_argument('--rule-name', default='thornquist-glue-job-failures',
                        help='Name of the deployed EventBridge rule')
    args = parser.parse_args()
    actual = boto3.client('sts', region_name='us-east-1').get_caller_identity()['Account']
    if actual != args.expected_account:
        parser.error(f'Account mismatch: signed into {actual}, expected {args.expected_account}.')

    client = boto3.client('events', region_name='us-east-1')
    rule = client.describe_rule(Name=args.rule_name)
    if rule.get('State') not in ('ENABLED', 'ENABLED_WITH_ALL_CLOUDTRAIL_MANAGEMENT_EVENTS'):
        raise RuntimeError(f"Rule {args.rule_name} is not enabled: {rule.get('State')}")
    if not rule.get('EventPattern'):
        raise RuntimeError(f'Rule {args.rule_name} has no saved event pattern')
    jobs = ['thornquist-customer-ingestion', 'thornquist-sales-etl']
    checks = [(job, state, state != 'SUCCEEDED')
              for job in jobs
              for state in ['FAILED', 'TIMEOUT', 'SUCCEEDED']]
    checks.append(('unrelated-job', 'FAILED', False))
    failures = 0
    for job, state, expected in checks:
        event = {
            'version': '0', 'id': str(uuid.uuid4()),
            'account': actual, 'source': 'aws.glue',
            'time': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'region': 'us-east-1', 'resources': [],
            'detail-type': 'Glue Job State Change',
            'detail': {'jobName': job, 'state': state},
        }
        matched = client.test_event_pattern(
            EventPattern=rule['EventPattern'], Event=json.dumps(event)
        )['Result']
        passed = matched == expected
        failures += not passed
        print(f"{'PASS' if passed else 'FAIL'}: {job} / {state} / matched={matched}")
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
