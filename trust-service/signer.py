#!/usr/bin/env python3

import os
import json
import boto3
import subprocess
import tempfile
import hashlib
from pathlib import Path
from datetime import datetime

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

KMS_KEY_ID = os.environ.get('KMS_KEY_ID')
LEDGER_TABLE = os.environ.get('LEDGER_TABLE', 'trust-ledger')

def handler(event, context):
    """Sign artifact with KMS and record in Rekor"""
    
    try:
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        print(f"🔐 Processing artifact: s3://{bucket}/{key}")
        
        # Skip signature files
        if key.endswith(('.sig', '.pem', '.bundle', '.json')) or 'cosign/' in key:
            print("⏭️  Skipping signature/metadata file")
            return {'statusCode': 200, 'message': 'Skipped'}
        
        # Skip if not a tarball
        if not key.endswith('.tgz'):
            print("⏭️  Not a tarball, skipping")
            return {'statusCode': 200, 'message': 'Not a tarball'}
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            artifact_path = tmpdir / Path(key).name
            
            # Download artifact
            print(f"📥 Downloading {key}...")
            s3.download_file(bucket, key, str(artifact_path))
            
            # Calculate SHA256
            sha256 = calculate_sha256(artifact_path)
            print(f"🔢 SHA256: {sha256}")
            
            # Sign with KMS
            print(f"✍️  Signing with KMS...")
            sig_path, cert_path, bundle_path = sign_with_kms(artifact_path, KMS_KEY_ID)
            
            # Extract Rekor UUID
            rekor_uuid = extract_rekor_uuid(bundle_path)
            print(f"📋 Rekor UUID: {rekor_uuid}")
            
            # Upload signatures
            upload_signatures(bucket, key, sig_path, cert_path, bundle_path)
            
            # Update ledger
            update_ledger(bucket, key, sha256, rekor_uuid)
            
        print("✅ Signing complete!")
        return {
            'statusCode': 200,
            'artifact': key,
            'rekor_uuid': rekor_uuid,
            'sha256': sha256
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {'statusCode': 500, 'error': str(e)}

def sign_with_kms(artifact_path, kms_key_id):
    """Sign with AWS KMS"""
    
    sig_path = artifact_path.with_suffix(artifact_path.suffix + '.sig')
    cert_path = artifact_path.with_suffix(artifact_path.suffix + '.pem')
    bundle_path = artifact_path.with_suffix(artifact_path.suffix + '.bundle')
    
    cmd = [
        'cosign', 'sign-blob',
        '--key', f'awskms:///{kms_key_id}',
        '--bundle', str(bundle_path),
        '--output-signature', str(sig_path),
        '--output-certificate', str(cert_path),
        '--yes',
        str(artifact_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
    print(f"Cosign output: {result.stdout}")
    
    return sig_path, cert_path, bundle_path

def extract_rekor_uuid(bundle_path):
    """Extract Rekor UUID from bundle"""
    
    with open(bundle_path, 'r') as f:
        bundle = json.load(f)
    
    rekor_bundle = bundle.get('rekorBundle', {})
    log_entry = rekor_bundle.get('logEntry', {})
    uuid = log_entry.get('uuid') or log_entry.get('logID')
    
    if not uuid:
        raise Exception("No Rekor UUID in bundle")
    
    return uuid

def upload_signatures(bucket, artifact_key, sig_path, cert_path, bundle_path):
    """Upload signatures to S3"""
    
    base_name = Path(artifact_key).name
    
    s3.upload_file(str(sig_path), bucket, f"cosign/{base_name}.sig")
    s3.upload_file(str(cert_path), bucket, f"cosign/{base_name}.pem")
    s3.upload_file(str(bundle_path), bucket, f"cosign/{base_name}.bundle")
    
    print(f"📤 Uploaded signatures to cosign/")

def update_ledger(bucket, key, sha256, rekor_uuid):
    """Update DynamoDB"""
    
    table = dynamodb.Table(LEDGER_TABLE)
    
    table.put_item(Item={
        'object_key': f"s3://{bucket}/{key}",
        'status': 'verified',
        'digest': f"sha256:{sha256}",
        'rekor_entry_id': rekor_uuid,
        'rekor_verified': True,
        'timestamp': datetime.utcnow().isoformat(),
        'details': 'Signed by Lambda with KMS',
        'signing_method': 'aws-kms'
    })
    
    print(f"💾 Updated ledger with Rekor entry")

def calculate_sha256(file_path):
    """Calculate SHA256"""
    
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()
