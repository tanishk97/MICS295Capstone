# SalsaGate Project Checkpoint

## Current Status: Production-Ready with Keyless Signing

**Last Updated**: November 9, 2025

---

## Architecture Overview

### Core Components
1. **GitHub Actions** - CI pipeline (builds, packages)
2. **CodeBuild Signer** - Keyless signing service (Sigstore)
3. **CodeBuild Verifier** - Standalone verification service
4. **DynamoDB Trust Ledger** - Central verification registry
5. **CodePipeline** - CD pipeline with manual approval gate
6. **CodeBuild Deploy** - Verification + deployment

### Key Design Decisions

**✅ Sigstore Keyless Signing** (Nov 9, 2025)
- **Why**: Eliminate cloud vendor dependency, achieve cloud-agnostic design
- **How**: `COSIGN_EXPERIMENTAL=1` + OIDC identity from CodeBuild
- **Benefit**: No key management, automatic rotation, public transparency

**✅ Trust Ledger as Single Source of Truth**
- **Why**: Fast verification (<2s vs 40s crypto verification)
- **Schema**: object_key, digest, rekor_entry_id, status, timestamp, signing_method
- **Benefit**: Fail-safe design, complete audit trail

**✅ Checksum Validation**
- **Why**: Detect artifact tampering after signing
- **How**: Compare actual SHA256 vs stored digest in ledger
- **Benefit**: Blocks tampered artifacts (validated in negative tests)

**❌ EventBridge Auto-Signing Disabled**
- **Why**: Prevented tampering detection (re-signed tampered artifacts)
- **Solution**: Signing only via GitHub Actions workflow invocation

---

## AWS Resources

### S3 Buckets
- `mics295-pipeline-artifacts-bucket` - Staging (signed artifacts)
- `mics295-capstone-website-bucket` - Production website

### DynamoDB
- `trust-ledger` - Verification registry
  - Primary Key: `object_key` (S3 URI)
  - Attributes: digest, rekor_entry_id, status, timestamp, signing_method

### CodeBuild Projects
- `codebuild-Mics295Pipeline-*` - GitHub Actions runner
- `salsag-artifact-signer` - Keyless signing service
- `salsag-artifact-verifier` - Standalone verifier
- `DeployBuild` - Deploy with verification

### CodePipeline
- `mics295-pipeline` - 3 stages: Source, ManualApproval, Deploy

---

## File Structure

```
MICS295Capstone/
├── .github/workflows/
│   └── deploy-salsag-cli.yml          # Main CI/CD workflow
├── trust-service/
│   ├── buildspec-signer.yml           # Keyless signing (COSIGN_EXPERIMENTAL=1)
│   ├── buildspec-verifier.yml         # Standalone verifier
│   ├── deploy-codebuild-signer.sh     # Signer deployment
│   └── deploy-verifier.sh             # Verifier deployment
├── salsag-cli/                        # SalsaG CLI tool
│   └── salsag/
│       ├── cli.py                     # Commands: start, verify
│       ├── core.py                    # Verification logic (checksum validation)
│       └── rekor_client.py            # Rekor API integration
├── tamper/                            # Negative test artifacts
│   ├── index.tgz                      # Tampered artifact
│   └── README.md                      # Testing instructions
├── buildspec.yml                      # Deploy verification buildspec
├── salsag.yml                         # SalsaG configuration
├── index.html                         # Application
├── README.md                          # Project overview
├── TECHNICAL_DOCUMENTATION.md         # Complete technical docs
├── E2E_TEST_SUCCESS.md               # Test validation results
└── PROJECT_CHECKPOINT.md             # This file
```

---

## Configuration

### salsag.yml
```yaml
aws:
  region: us-east-1
  staging_bucket: mics295-pipeline-artifacts-bucket
  ledger_table: trust-ledger

skip_signing: true  # Signing delegated to CodeBuild service

artifacts:
  compression: "gzip"
  include_sbom: true
  include_provenance: true
```

### Environment Variables
- `COSIGN_EXPERIMENTAL=1` - Enables keyless signing in signer buildspec

---

## Workflow

### 1. Developer Push
```bash
git push origin main
```

### 2. GitHub Actions (CI)
- Builds application
- Packages as `index.tgz`
- Uploads to S3 staging bucket
- **Invokes CodeBuild signer**
- Triggers CodePipeline

### 3. Keyless Signing (CodeBuild)
```bash
COSIGN_EXPERIMENTAL=1 cosign sign-blob \
  --bundle artifact.tgz.bundle \
  --yes \
  artifact.tgz
```
- Signs with OIDC identity (no keys)
- Uploads to Rekor transparency log
- Extracts Rekor log index from bundle
- Records in DynamoDB trust ledger

### 4. Manual Approval (CodePipeline)
- Human gate before production
- Opportunity for negative testing (tamper artifact)

### 5. Verification & Deploy (CodeBuild)
```bash
salsaG verify --artifact index.tgz --config salsag.yml
```
- Checks trust ledger (artifact exists, status=verified)
- Validates checksum (actual SHA256 vs ledger digest)
- If passed: Deploy to production
- If failed: Block deployment

---

## Testing Results

### Positive Test ✅
- **Date**: Nov 9, 2025
- **Rekor Log Index**: 686027146
- **Digest**: sha256:bd506670225a157bcc69757e600b037250ffb9e431532f8ee426e7685507461b
- **Result**: Deployment succeeded
- **Verification**: Trust ledger + checksum passed

### Negative Test ✅
- **Date**: Nov 9, 2025
- **Scenario**: Artifact tampered during manual approval
- **Result**: Deployment blocked
- **Error**: "❌ Checksum verification failed"
- **Validation**: System correctly detected tampering

---

## Key Learnings

### What Worked
1. **Keyless signing** - Eliminated key management complexity
2. **Trust ledger** - Fast, reliable verification
3. **Checksum validation** - Effective tamper detection
4. **Manual approval gate** - Enables negative testing

### What Didn't Work
1. **Lambda signing service** - Runtime.InvalidEntrypoint errors (pivoted to CodeBuild)
2. **EventBridge auto-signing** - Re-signed tampered artifacts (disabled)
3. **Rekor UUID verification** - Bundle uses log index, not UUID (fixed)

### Security Gaps Fixed
1. **Missing checksum validation** - Added SHA256 comparison in verifier
2. **Auto re-signing on tamper** - Disabled EventBridge rule
3. **Cosign warning message** - Removed for keyless signing

---

## Dependencies

### Python Packages (salsag-cli)
- boto3 - AWS SDK
- click - CLI framework
- rich - Terminal formatting
- requests - Rekor API calls

### External Services
- **Sigstore Rekor** - https://rekor.sigstore.dev
- **Sigstore Fulcio** - Certificate authority for keyless signing

### AWS Services
- S3, DynamoDB, CodeBuild, CodePipeline, CloudWatch Logs

---

## Deployment Commands

### Initial Setup
```bash
# Create buckets
aws s3 mb s3://mics295-pipeline-artifacts-bucket
aws s3 mb s3://mics295-capstone-website-bucket

# Create trust ledger
aws dynamodb create-table \
  --table-name trust-ledger \
  --attribute-definitions AttributeName=object_key,AttributeType=S \
  --key-schema AttributeName=object_key,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# Deploy services
cd trust-service
./deploy-codebuild-signer.sh
./deploy-verifier.sh
```

### Trigger Pipeline
```bash
# Update code
echo "test" >> index.html
git add index.html
git commit -m "Test"
git push

# Monitor
gh run watch
aws codepipeline get-pipeline-state --name mics295-pipeline
```

### Manual Signing
```bash
aws codebuild start-build \
  --project-name salsag-artifact-signer \
  --environment-variables-override name=ARTIFACT_KEY,value=index.tgz
```

### Manual Verification
```bash
aws codebuild start-build \
  --project-name salsag-artifact-verifier \
  --environment-variables-override name=ARTIFACT_KEY,value=index.tgz
```

---

## Monitoring

### Check Trust Ledger
```bash
aws dynamodb scan --table-name trust-ledger
```

### Verify in Rekor
```bash
curl "https://rekor.sigstore.dev/api/v1/log/entries?logIndex=686027146"
```

### View Logs
```bash
# Signer
aws logs tail /aws/codebuild/salsag-artifact-signer --follow

# Verifier
aws logs tail /aws/codebuild/salsag-artifact-verifier --follow

# Deploy
aws logs tail /aws/codebuild/DeployBuild --follow
```

---

## Known Issues

### None Currently

All major issues resolved:
- ✅ Lambda signing → Replaced with CodeBuild
- ✅ EventBridge re-signing → Disabled
- ✅ Missing checksum validation → Added
- ✅ Cloud vendor dependency → Removed (keyless)

---

## Future Enhancements

### Potential Improvements
1. **Full Rekor verification** - Query Rekor API in deploy stage (currently only ledger + checksum)
2. **SBOM validation** - Check for vulnerable dependencies before deployment
3. **Multi-environment** - Dev, staging, prod pipelines
4. **Notifications** - Slack/email on verification failures
5. **Dashboard** - Visualize trust ledger and verification history

### Not Planned
- Lambda signing service (CodeBuild is more reliable)
- EventBridge auto-signing (defeats tampering detection)

---

## Contact

**Project**: UC Berkeley MICS Capstone (Cyber295)  
**Repository**: https://github.com/tanishk97/MICS295Capstone  
**Status**: Production-ready, fully tested, documented
