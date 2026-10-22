"""Manual catalog helper; the deployed sales ETL reads the original JSON array.
Usage: python3 ingestion/convert_ecommerce_ndjson.py --bucket BUCKET
Reads Raw JSON and writes only its separate NDJSON catalog representation.
"""
import argparse
import json
import boto3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bucket', required=True)
    args = parser.parse_args()
    s3 = boto3.client('s3', region_name='us-east-1')
    response = s3.get_object(Bucket=args.bucket, Key='raw/ecommerce/ecommerce_orders.json')
    orders = json.loads(response['Body'].read().decode('utf-8-sig'))
    if not isinstance(orders, list) or not all(isinstance(o, dict) for o in orders):
        raise ValueError('Expected an array of order objects')
    body = ''.join(json.dumps(o, ensure_ascii=False) + '\n' for o in orders).encode('utf-8')
    s3.put_object(Bucket=args.bucket, Key='raw/ecommerce_ndjson/ecommerce_orders.ndjson',
                  Body=body, ContentType='application/x-ndjson', ServerSideEncryption='AES256')
    print(f'Orders converted: {len(orders)}')


if __name__ == '__main__':
    main()
