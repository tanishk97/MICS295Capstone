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
- Workflow ready but needs configuration

## Next Steps (TODO)

### 4. AWS Infrastructure Setup ⏳
- [ ] Replace `<REPLACE_ME>` placeholders in deploy.yml:
  - STAGING_BUCKET name
  - ACCOUNT_ID 
- [ ] Create S3 buckets (staging + website)
- [ ] Apply bucket policy to website bucket
- [ ] Create IAM OIDC role using template
- [ ] Update GitHub repo settings if needed

### 5. Testing Phase ⏳
- [ ] Commit and push to trigger workflow
- [ ] Verify signed artifacts in staging bucket
- [ ] Create verify-promote workflow for manual deployment
- [ ] Test end-to-end trust verification

### 6. Optional Enhancements ⏳
- [ ] Deploy Lambda trust service for automatic verification
- [ ] Set up DynamoDB ledger for audit trail
- [ ] Configure S3 event triggers

## Key Files Modified
```
MICS295Capstone/
├── .github/workflows/deploy.yml (MODIFIED - main integration)
├── infra/
│   ├── iam-gha-oidc-role.json (NEW)
│   └── bucket-policy-website.json (NEW)
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
