# Lambda Signing Service Implementation Plan

## Overview
Create a Lambda function that signs artifacts with cosign using AWS KMS, uploads to Rekor, and records in trust ledger - enabling full Rekor integration without OIDC requirements.

## Architecture

### Current Flow (Trust Ledger Only)
```
GitHub Actions → Build → Upload to S3 → Record in DynamoDB (no Rekor)
```

### New Flow (Lambda Signing Service)
```
GitHub Actions → Build → Upload unsigned to S3 → 
S3 Event → Lambda → Sign with KMS → Upload to Rekor → 
Update DynamoDB with Rekor ID → Verified artifact ready
```

## Components

### 1. Lambda Function
**Purpose**: Sign artifacts using AWS KMS and record in Rekor

**Trigger**: S3 event on artifact upload to staging bucket

**Process**:
1. Download artifact from S3
2. Sign with AWS KMS key (cosign supports KMS)
3. Upload signature to Rekor transparency log
4. Extract Rekor entry UUID
5. Update DynamoDB with Rekor entry ID
6. Upload signatures back to S3

### 2. AWS KMS Key
**Purpose**: Signing key for cosign (replaces OIDC)

**Type**: Asymmetric key pair (RSA or ECDSA)

**Usage**: cosign can sign with KMS directly

### 3. S3 Event Notification
**Trigger**: When `.tgz` files uploaded to staging bucket

**Target**: Lambda function

**Filter**: `*.tgz` (not signature files)

## Implementation Steps

### Phase 1: Create KMS Key
```bash
aws kms create-key \
  --key-usage SIGN_VERIFY \
  --key-spec ECC_NIST_P256 \
  --description "SalsaG artifact signing key"
```

### Phase 2: Lambda Function
**File**: `trust-service/signer.py`

```python
import boto3
import json
import subprocess
import tempfile
from pathlib import Path

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
kms_key_id = os.environ['KMS_KEY_ID']
ledger_table = os.environ['LEDGER_TABLE']

def handler(event, context):
    # Parse S3 event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    
    # Download artifact
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / Path(key).name
        s3.download_file(bucket, key, str(artifact_path))
        
        # Sign with KMS
        rekor_uuid = sign_with_kms(artifact_path, kms_key_id)
        
        # Update DynamoDB
        update_ledger(bucket, key, rekor_uuid)
        
        # Upload signatures to S3
        upload_signatures(bucket, artifact_path)
    
    return {'statusCode': 200, 'rekor_uuid': rekor_uuid}
```

### Phase 3: Update SalsaG CLI
**Changes**:
- Remove signing from `salsaG start` command
- Upload unsigned artifact to S3
- Wait for Lambda to sign (or poll DynamoDB for Rekor ID)
- Verification remains the same

### Phase 4: S3 Event Configuration
```bash
aws s3api put-bucket-notification-configuration \
  --bucket mics295-pipeline-artifacts-bucket \
  --notification-configuration '{
    "LambdaFunctionConfigurations": [{
      "LambdaFunctionArn": "arn:aws:lambda:...:function:salsag-signer",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {"FilterRules": [{"Name": "suffix", "Value": ".tgz"}]}
      }
    }]
  }'
```

## Detailed Implementation

### Lambda Function (trust-service/signer.py)
```python
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

KMS_KEY_ID = os.environ['KMS_KEY_ID']
LEDGER_TABLE = os.environ['LEDGER_TABLE']
REKOR_URL = "https://rekor.sigstore.dev"

def handler(event, context):
    """Sign artifact with KMS and record in Rekor"""
    
    try:
        # Parse S3 event
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        
        print(f"Processing artifact: s3://{bucket}/{key}")
        
        # Skip if already a signature file
        if key.endswith(('.sig', '.pem', '.bundle')):
            return {'statusCode': 200, 'message': 'Skipped signature file'}
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            artifact_path = tmpdir / Path(key).name
            
            # Download artifact
            print(f"Downloading {key}...")
            s3.download_file(bucket, key, str(artifact_path))
            
            # Calculate SHA256
            sha256 = calculate_sha256(artifact_path)
            print(f"Artifact SHA256: {sha256}")
            
            # Sign with KMS
            print(f"Signing with KMS key {KMS_KEY_ID}...")
            sig_path, cert_path, bundle_path = sign_with_kms(artifact_path, KMS_KEY_ID)
            
            # Extract Rekor UUID from bundle
            rekor_uuid = extract_rekor_uuid(bundle_path)
            print(f"Rekor entry UUID: {rekor_uuid}")
            
            # Upload signatures to S3
            upload_signatures(bucket, key, sig_path, cert_path, bundle_path)
            
            # Update DynamoDB with Rekor entry
            update_ledger(bucket, key, sha256, rekor_uuid)
            
        return {
            'statusCode': 200,
            'artifact': key,
            'rekor_uuid': rekor_uuid,
            'sha256': sha256
        }
        
    except Exception as e:
        print(f"Error: {e}")
        return {'statusCode': 500, 'error': str(e)}

def sign_with_kms(artifact_path, kms_key_id):
    """Sign artifact using AWS KMS key"""
    
    sig_path = artifact_path.with_suffix(artifact_path.suffix + '.sig')
    cert_path = artifact_path.with_suffix(artifact_path.suffix + '.pem')
    bundle_path = artifact_path.with_suffix(artifact_path.suffix + '.bundle')
    
    # Cosign with KMS
    cmd = [
        'cosign', 'sign-blob',
        '--key', f'awskms:///{kms_key_id}',
        '--bundle', str(bundle_path),
        '--output-signature', str(sig_path),
        '--output-certificate', str(cert_path),
        '--yes',
        str(artifact_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    return sig_path, cert_path, bundle_path

def extract_rekor_uuid(bundle_path):
    """Extract Rekor UUID from cosign bundle"""
    
    with open(bundle_path, 'r') as f:
        bundle = json.load(f)
    
    # Extract UUID from bundle
    rekor_bundle = bundle.get('rekorBundle', {})
    log_entry = rekor_bundle.get('logEntry', {})
    uuid = log_entry.get('uuid') or log_entry.get('logID')
    
    if not uuid:
        # Fallback: search Rekor by hash
        raise Exception("Could not extract Rekor UUID from bundle")
    
    return uuid

def upload_signatures(bucket, artifact_key, sig_path, cert_path, bundle_path):
    """Upload signature files to S3"""
    
    base_key = Path(artifact_key).stem
    
    s3.upload_file(str(sig_path), bucket, f"cosign/{base_key}.sig")
    s3.upload_file(str(cert_path), bucket, f"cosign/{base_key}.pem")
    s3.upload_file(str(bundle_path), bucket, f"cosign/{base_key}.bundle")
    
    print(f"Uploaded signatures to s3://{bucket}/cosign/")

def update_ledger(bucket, key, sha256, rekor_uuid):
    """Update DynamoDB trust ledger with Rekor entry"""
    
    table = dynamodb.Table(LEDGER_TABLE)
    
    table.put_item(Item={
        'object_key': f"s3://{bucket}/{key}",
        'status': 'verified',
        'digest': f"sha256:{sha256}",
        'rekor_entry_id': rekor_uuid,
        'rekor_verified': True,
        'timestamp': datetime.utcnow().isoformat(),
        'details': 'Signed by Lambda with KMS and recorded in Rekor',
        'signing_method': 'aws-kms'
    })
    
    print(f"Updated trust ledger with Rekor entry {rekor_uuid}")

def calculate_sha256(file_path):
    """Calculate SHA256 hash of file"""
    
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()
```

### Lambda Dockerfile
```dockerfile
FROM public.ecr.aws/lambda/python:3.11

# Install cosign
RUN curl -sL "https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64" -o /usr/local/bin/cosign && \
    chmod +x /usr/local/bin/cosign

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy function code
COPY signer.py ${LAMBDA_TASK_ROOT}

CMD ["signer.handler"]
```

### Lambda IAM Policy
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::mics295-pipeline-artifacts-bucket/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "kms:Sign",
        "kms:GetPublicKey"
      ],
      "Resource": "arn:aws:kms:*:*:key/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/trust-ledger"
    }
  ]
}
```

## Deployment Steps

### 1. Create KMS Key
```bash
KMS_KEY_ID=$(aws kms create-key \
  --key-usage SIGN_VERIFY \
  --key-spec ECC_NIST_P256 \
  --description "SalsaG artifact signing key" \
  --region us-east-1 \
  --query 'KeyMetadata.KeyId' \
  --output text)

echo "KMS Key ID: $KMS_KEY_ID"
```

### 2. Build and Deploy Lambda
```bash
cd trust-service
docker build -t salsag-signer .
aws ecr create-repository --repository-name salsag-signer
docker tag salsag-signer:latest <account>.dkr.ecr.us-east-1.amazonaws.com/salsag-signer:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/salsag-signer:latest

aws lambda create-function \
  --function-name salsag-signer \
  --package-type Image \
  --code ImageUri=<account>.dkr.ecr.us-east-1.amazonaws.com/salsag-signer:latest \
  --role arn:aws:iam::<account>:role/lambda-salsag-signer-role \
  --environment Variables={KMS_KEY_ID=$KMS_KEY_ID,LEDGER_TABLE=trust-ledger} \
  --timeout 60 \
  --memory-size 512
```

### 3. Configure S3 Event
```bash
aws lambda add-permission \
  --function-name salsag-signer \
  --statement-id s3-trigger \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn arn:aws:s3:::mics295-pipeline-artifacts-bucket

aws s3api put-bucket-notification-configuration \
  --bucket mics295-pipeline-artifacts-bucket \
  --notification-configuration file://s3-event-config.json
```

### 4. Update SalsaG CLI
Remove signing step, just upload artifact:
```python
# In salsag/core.py - simplify start command
def start_unsigned(self, artifact_path):
    tarball = self.package_artifact(artifact_path)
    sbom = self.generate_sbom(artifact_path)
    provenance = self.create_provenance(tarball)
    
    # Upload unsigned - Lambda will sign
    self.upload_artifacts_unsigned(tarball, sbom, provenance)
    
    # Wait for Lambda to sign and record
    self.wait_for_signing(tarball.name)
```

## Testing

### Test Flow
```bash
# 1. Upload artifact
salsaG start --artifact ./dist --config salsag.yml

# 2. Lambda automatically signs (check CloudWatch logs)
aws logs tail /aws/lambda/salsag-signer --follow

# 3. Verify Rekor entry created
salsaG verify --artifact index.tgz --config salsag.yml

# 4. Check DynamoDB for Rekor UUID
aws dynamodb get-item \
  --table-name trust-ledger \
  --key '{"object_key":{"S":"s3://mics295-pipeline-artifacts-bucket/index.tgz"}}'
```

## Benefits

✅ Full Rekor integration without OIDC  
✅ Centralized signing with KMS  
✅ Automatic signing on artifact upload  
✅ Works with CodeBuild IAM roles  
✅ Cryptographic proof via Rekor  
✅ Immutable audit trail  

## Timeline

- **Phase 1**: Create KMS key and Lambda function (1-2 hours)
- **Phase 2**: Configure S3 events and IAM (30 min)
- **Phase 3**: Update SalsaG CLI (30 min)
- **Phase 4**: Testing and validation (1 hour)

**Total**: 3-4 hours

---

**Ready to implement?**
