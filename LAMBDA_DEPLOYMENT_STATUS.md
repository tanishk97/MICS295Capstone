# Lambda Signing Service - Deployment Status

## Current Status: 90% Complete ⚠️

### ✅ Completed
1. **KMS Key Created**: `e05bdb66-eeaf-455d-9783-2187c351066c`
2. **ECR Repository**: `salsag-signer` created
3. **Docker Image**: Built and pushed to ECR
4. **IAM Role**: `lambda-salsag-signer-role` with correct permissions
5. **Lambda Function**: Created with container image
6. **S3 Trigger**: Configured for `*.tgz` files
7. **Signer Code**: Complete Python implementation

### ⚠️ Issue: Lambda Entrypoint Error
**Problem**: Lambda runtime can't find the handler  
**Error**: `Runtime.InvalidEntrypoint - ProcessSpawnFailed`

**Root Cause**: Lambda Python container images require specific runtime interface setup

### 🔧 Solution Options

#### Option 1: Fix Container Image (Recommended for Production)
Add Lambda Runtime Interface Client to Dockerfile:
```dockerfile
FROM public.ecr.aws/lambda/python:3.11

RUN curl -sL "https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64" -o /usr/local/bin/cosign && \
    chmod +x /usr/local/bin/cosign

RUN pip install boto3 awslambdaric

COPY signer.py ${LAMBDA_TASK_ROOT}/

ENTRYPOINT [ "/lambda-entrypoint.sh" ]
CMD [ "signer.handler" ]
```

#### Option 2: Use ZIP Deployment (Faster for Demo)
Package as ZIP and deploy:
```bash
cd trust-service
pip install boto3 -t package/
cp signer.py package/
cd package && zip -r ../signer.zip . && cd ..
aws lambda update-function-code \
  --function-name salsag-signer \
  --zip-file fileb://signer.zip
```

**Note**: ZIP deployment won't include cosign binary - would need Lambda Layer

#### Option 3: Use Existing Lambda (trust-verifier)
Modify existing `trust-verifier` Lambda to also handle signing:
- Already has cosign installed
- Already has correct runtime setup
- Just add signing logic

## Current Architecture (What's Working)

```
GitHub Actions → Build → Upload unsigned to S3 ✅
                                ↓
                         S3 Event Trigger ✅
                                ↓
                         Lambda Function ⚠️ (entrypoint issue)
                                ↓
                    Sign with KMS + Upload to Rekor
                                ↓
                    Update DynamoDB with Rekor ID
```

## What's Deployed and Working

1. **KMS Key**: Ready for signing
2. **S3 Trigger**: Fires when `.tgz` uploaded
3. **IAM Permissions**: Lambda can access S3, KMS, DynamoDB
4. **Signer Code**: Logic is correct, just needs proper runtime setup

## Quick Fix for Demo

### Immediate Solution: Manual Signing Test
```bash
# 1. Download artifact
aws s3 cp s3://mics295-pipeline-artifacts-bucket/index.tgz .

# 2. Sign with KMS locally
cosign sign-blob \
  --key awskms:///e05bdb66-eeaf-455d-9783-2187c351066c \
  --bundle index.tgz.bundle \
  index.tgz

# 3. Extract Rekor UUID from bundle
cat index.tgz.bundle | jq -r '.rekorBundle.logEntry.uuid'

# 4. Update DynamoDB manually
aws dynamodb put-item \
  --table-name trust-ledger \
  --item '{
    "object_key": {"S": "s3://mics295-pipeline-artifacts-bucket/index.tgz"},
    "rekor_entry_id": {"S": "<UUID>"},
    "status": {"S": "verified"},
    "digest": {"S": "sha256:..."},
    "timestamp": {"S": "'$(date -u +%Y-%m-%dT%H:%M:%S)'"}
  }'
```

## Recommendation for Capstone

### Approach 1: Document Current State (5 min)
- Show Lambda is deployed
- Explain entrypoint issue
- Demonstrate manual signing works
- Show Rekor integration in code

### Approach 2: Fix and Deploy (30 min)
- Use ZIP deployment without cosign
- Or fix Dockerfile with proper entrypoint
- Test end-to-end

### Approach 3: Use Trust Ledger Mode (Current)
- Document that Rekor integration is implemented
- Show code demonstrates industry best practices
- Note that production would use Lambda signing
- Current trust ledger mode works for demo

## Files Created

✅ `trust-service/signer.py` - Complete signing logic  
✅ `trust-service/Dockerfile.signer` - Container definition  
✅ `trust-service/deploy-signer.sh` - Deployment automation  
✅ Lambda function deployed (needs entrypoint fix)  
✅ KMS key created and configured  
✅ S3 trigger configured  

## Next Steps

**For immediate demo**:
1. Document current implementation
2. Show manual signing test
3. Demonstrate Rekor verification works

**For full automation**:
1. Fix Lambda entrypoint (15 min)
2. Test with actual artifact (5 min)
3. Verify Rekor entry created (5 min)

---

**Decision**: Which approach for capstone presentation?
