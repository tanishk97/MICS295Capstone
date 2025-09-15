# SalsaGate Trust Pipeline Integration - Session Context

## Project Goal
Integrate SalsaGate trust pipeline (cryptographic attestation using Sigstore cosign) into the existing MICS295Capstone CI/CD pipeline to demonstrate supply chain security.

## Repository Structure
- **Application Repo**: `/MICS295Capstone/` - Contains actual website (`index.html`) and deployment logic
- **Trust Pipeline Repo**: `/SalsaGate/` - Contains reference implementation and templates

## Completed Steps

### 1. Analysis Phase ✅
- Examined SalsaGate trust pipeline architecture
- Identified key components: build-attest → verify-promote → deploy
- Analyzed existing MICS295Capstone deployment workflow

### 2. Integration Phase ✅
- **Modified**: `.github/workflows/deploy.yml` - Integrated trust pipeline into existing CI/CD
- **Created**: `infra/iam-gha-oidc-role.json` - IAM role template for GitHub OIDC
- **Created**: `infra/bucket-policy-website.json` - S3 bucket policy for zero-trust deployment

### 3. Workflow Integration Details ✅
**Added to existing deploy.yml:**
- SBOM generation using anchore/sbom-action
- SLSA provenance creation
- Cosign blob signing with GitHub OIDC
- Attestation bundle creation
- Upload signed artifacts to staging bucket
- Maintained backward compatibility with existing CodePipeline

## Current State
- Trust pipeline integrated into main deployment workflow
- Templates created for AWS infrastructure
- **Workflow executed successfully** - signed artifacts in staging bucket
- **Lambda function deployed** - automatic verification active
- **DynamoDB table created** - audit trail operational
- **S3 triggers configured** - end-to-end automation working

## Completed Steps (Updated)

### 4. Workflow Execution ✅
- **Tested**: GitHub Actions workflow ran successfully
- **Generated**: Signed artifacts with commit SHA in staging bucket:
  - `site-<sha>.tgz` (website tarball)
  - `site-<sha>.tgz.sig` (cryptographic signature)
  - `site-<sha>.tgz.pem` (certificate)
  - `site-<sha>.tgz.attestation.sigstore` (SLSA attestation)
  - `sbom-<sha>.spdx.json` (software bill of materials)
  - `provenance.json` (build metadata)

### 5. Lambda Trust Service ✅
- **Created**: `trust-service/handler.py` - Automatic verification function
- **Created**: `trust-service/Dockerfile` - Container with cosign binary
- **Created**: `trust-service/requirements.txt` - Python dependencies
- **Built**: Container image using EC2 (avoided Mac Docker compatibility issues)
- **Deployed**: Lambda function from ECR container image
- **Fixed**: Architecture mismatch and missing file handling errors
- **Added**: Comprehensive event logging for debugging

### 6. DynamoDB Audit Trail ✅
- **Created**: `trust-ledger` table with partition key `object_key` (String)
- **Schema**: Records verification status, timestamp, digest, and cosign output
- **Billing**: Pay-per-request mode for cost efficiency
- **Integration**: Lambda logs all verification attempts automatically

### 7. S3 Event Configuration ✅
- **Trigger**: S3 event notification on staging bucket uploads
- **Filter**: Prefix `site-`, suffix `.tgz` (only triggers on tarballs)
- **Target**: Lambda function for automatic verification
- **Behavior**: Graceful handling when signature files not yet available
- **Generated**: Signed artifacts with commit SHA in staging bucket:
  - `site-<sha>.tgz` (website tarball)
  - `site-<sha>.tgz.sig` (cryptographic signature)
  - `site-<sha>.tgz.pem` (certificate)
  - `site-<sha>.tgz.attestation.sigstore` (SLSA attestation)
  - `sbom-<sha>.spdx.json` (software bill of materials)
  - `provenance.json` (build metadata)

### 5. Lambda Trust Service ✅
- **Created**: `trust-service/handler.py` - Automatic verification function
- **Created**: `trust-service/Dockerfile` - Container with cosign binary
- **Created**: `trust-service/requirements.txt` - Python dependencies
- **Features**: Auto-verification, DynamoDB audit trail, optional auto-promotion

## Next Steps (TODO)

### 6. Lambda Deployment ⏳
- [ ] Build container image: `docker build -t trust-verifier .`
- [ ] Push to ECR (Elastic Container Registry)
- [ ] Deploy Lambda function from container image
- [ ] Set environment variables (LEDGER_TABLE, WEBSITE_BUCKET)
- [ ] Create DynamoDB table for audit trail
- [ ] Configure S3 trigger on staging bucket

### 7. Infrastructure Completion ⏳
- [ ] Create website S3 bucket with zero-trust policy
- [ ] Test automatic verification on artifact upload
- [ ] Verify end-to-end tamper detection

### 8. Manual Verification Testing ⏳
- [ ] Create verify-promote workflow for manual deployment
- [ ] Test manual verification and promotion process

## Key Files Modified
```
MICS295Capstone/
├── .github/workflows/deploy.yml (MODIFIED - main integration)
├── infra/
│   ├── iam-gha-oidc-role.json (NEW)
│   └── bucket-policy-website.json (NEW)
├── trust-service/ (NEW)
│   ├── handler.py (NEW - Lambda verification function)
│   ├── Dockerfile (NEW - Container with cosign)
│   └── requirements.txt (NEW)
└── SESSION_CONTEXT.md (NEW - this file)
```

## Architecture Flow
1. **Push to main** → GitHub Actions workflow triggers
2. **Build** → Creates `dist/` with `index.html`, packages as tarball
3. **Attest** → Generates SBOM, SLSA provenance, signs with cosign
4. **Upload** → Signed artifacts to staging bucket
5. **Legacy** → Maintains existing CodePipeline trigger
6. **Manual** → Verify-promote workflow for production deployment

## Security Features Implemented
- Zero-trust deployment (bucket policy denies unverified uploads)
- Cryptographic signatures via Sigstore cosign
- SLSA provenance attestations
- SBOM for dependency tracking
- GitHub OIDC (no long-lived credentials)
- Immutable audit trail capability

## Current Blockers
- Need actual AWS account ID and bucket names to complete setup
- Requires AWS infrastructure provisioning before testing
