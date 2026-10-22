"""Read and test the deployed filter. Does not publish events or start jobs.

Run in CloudShell: python3 test_glue_failure_pattern.py
The user ran this logic in AWS on October 22, 2026: all seven cases passed.
"""
import json
import uuid
from datetime import datetime, timezone

import boto3


def main():
    client = boto3.client('events', region_name='us-east-1')
    rule = client.describe_rule(Name='thornquist-glue-job-failures')
    jobs = ['thornquist-customer-ingestion', 'thornquist-sales-etl']
    checks = [(job, state, state != 'SUCCEEDED')
              for job in jobs
              for state in ['FAILED', 'TIMEOUT', 'SUCCEEDED']]
    checks.append(('unrelated-job', 'FAILED', False))
    failures = 0
    for job, state, expected in checks:
        event = {
            'version': '0', 'id': str(uuid.uuid4()),
            'account': '470551642447', 'source': 'aws.glue',
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
