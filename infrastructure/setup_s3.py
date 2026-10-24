#!/usr/bin/env python3
"""Optional S3-only foundation for a new bucket. The full pipeline runner is reproduction/clean_lab/clean_lab.py. Preview by default; --apply creates."""
import argparse
import hashlib
from pathlib import Path
import re
import sys

FILES = {
    'pos_sales_2026-08-24_to_2026-08-30.csv': ('pos', '84a27826113583e92512484381a9f32781cc8bbd1b93787d0bb551bc56d60471'),
    'ecommerce_orders.json': ('ecommerce', '874604830bfcb953e7c87fe514441b5be4f593811aeeaa55a825d56c587222d0'),
    'customer_extract.csv': ('customers', '55effa04eb7139a05ef54280b3f9a289e07c5e7df7447fdfe64d2728faca04f1'),
}
PREFIXES = ['landing/', 'raw/', 'trusted/', 'curated/', 'quarantine/',
            'athena-results/', 'reports/', 'landing/pos/', 'landing/ecommerce/', 'landing/customers/']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bucket', required=True, help='New globally unique bucket name')
    parser.add_argument('--expected-account', required=True, help='Your target 12-digit AWS account ID')
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).resolve().parents[1] / 'data')
    parser.add_argument('--apply', action='store_true', help='Create the NEW bucket and upload datasets')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]', args.bucket):
        parser.error('Use 3–63 lowercase letters, digits and hyphens; start/end with a letter or digit.')
    if not re.fullmatch(r'\d{12}', args.expected_account):
        parser.error('--expected-account must be 12 digits')

    # Check original bytes before making any AWS changes.
    for name, (_, expected) in FILES.items():
        path = args.data_dir / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Missing or modified instructor dataset: {path}. Restore the original file.')
    print('All three instructor dataset checksums match.')
    print(f'Target account: {args.expected_account}\nRegion: us-east-1\nBucket: {args.bucket}')
    print('Settings: SSE-S3; ACLs disabled; all public access blocked; versioning never enabled.')
    print('No bucket policy, lifecycle, Lambda, Glue or Athena resources are created.')
    for prefix in PREFIXES:
        print(f'Folder: {prefix}')
    for name, (prefix, _) in FILES.items():
        print(f'Upload: landing/{prefix}/{name}')
    if not args.apply:
        print('PREVIEW ONLY: no AWS calls or changes. Add --apply to deploy to a fresh bucket.')
        return

    import boto3
    from botocore.exceptions import ClientError
    session = boto3.Session(region_name='us-east-1')
    actual = session.client('sts').get_caller_identity()['Account']
    if actual != args.expected_account:
        raise RuntimeError(f'Account mismatch: signed into {actual}; expected {args.expected_account}. No changes made.')
    s3 = session.client('s3')
    # In us-east-1, CreateBucket on an owned bucket can succeed; explicitly guard it.
    for page in s3.get_paginator('list_buckets').paginate():
        if any(b['Name'] == args.bucket for b in page.get('Buckets', [])):
            raise RuntimeError('This bucket already belongs to your account. Stopping without changing it.')
    try:
        s3.head_bucket(Bucket=args.bucket)
    except ClientError as error:
        if str(error.response['Error']['Code']) not in ('404', 'NoSuchBucket', 'NotFound'):
            raise RuntimeError('Bucket availability cannot be confirmed (possibly taken or access denied). No changes made.') from error
    else:
        raise RuntimeError('Bucket already exists. Choose a different name. No changes made.')

    s3.create_bucket(Bucket=args.bucket, ObjectOwnership='BucketOwnerEnforced')
    s3.get_waiter('bucket_exists').wait(Bucket=args.bucket)
    owner = {'Bucket': args.bucket, 'ExpectedBucketOwner': actual}
    s3.put_public_access_block(**owner, PublicAccessBlockConfiguration={
        'BlockPublicAcls': True, 'IgnorePublicAcls': True,
        'BlockPublicPolicy': True, 'RestrictPublicBuckets': True})
    s3.put_bucket_encryption(**owner, ServerSideEncryptionConfiguration={
        'Rules': [{'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}]})
    # A fresh bucket has versioning disabled. Do not enable or suspend it.
    for key in PREFIXES:
        s3.put_object(**owner, Key=key, Body=b'', ServerSideEncryption='AES256')
    for name, (prefix, _) in FILES.items():
        s3.put_object(**owner, Key=f'landing/{prefix}/{name}',
                      Body=(args.data_dir / name).read_bytes(), ServerSideEncryption='AES256')

    assert s3.get_bucket_versioning(**owner).get('Status') is None, 'Unexpected versioning state'
    block = s3.get_public_access_block(**owner)['PublicAccessBlockConfiguration']
    assert all(block.get(k) is True for k in ('BlockPublicAcls', 'IgnorePublicAcls', 'BlockPublicPolicy', 'RestrictPublicBuckets'))
    assert s3.get_bucket_ownership_controls(**owner)['OwnershipControls']['Rules'][0]['ObjectOwnership'] == 'BucketOwnerEnforced'
    rules = s3.get_bucket_encryption(**owner)['ServerSideEncryptionConfiguration']['Rules']
    assert rules[0]['ApplyServerSideEncryptionByDefault']['SSEAlgorithm'] == 'AES256'
    for name, (prefix, expected) in FILES.items():
        response = s3.get_object(**owner, Key=f'landing/{prefix}/{name}')
        with response['Body'] as body:
            assert hashlib.sha256(body.read()).hexdigest() == expected, f'Upload checksum mismatch: {name}'
        print(f'Verified original bytes in S3: {name}')
    print('SUCCESS: S3 foundation created and settings/dataset bytes verified.')
    print('Save this output and screenshots as evidence; record the account, region and bucket in docs.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'STOPPED: {error}', file=sys.stderr)
        print('If creation already started, inspect the bucket for partial progress. Nothing is automatically deleted.', file=sys.stderr)
        sys.exit(1)
