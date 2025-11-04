# Sprint 1 Test Results - Rekor Integration

## Test Execution

**Date**: November 3, 2025  
**Commit**: 3edeb93 - "Respect skip_signing config to avoid OIDC timeout in CI"  
**Workflow Run**: 19056685350

## Findings

### Issue Discovered: skip_signing Not Respected
**Problem**: The `skip_signing: true` config was not being used in `sign_artifact()` method, causing cosign to attempt OIDC authentication and timeout after 30 seconds in CI environment.

**Root Cause**: CodeBuild runners use IAM roles, not OIDC. Cosign was trying to authenticate with GitHub OIDC which isn't available/needed in CodeBuild context.

**Fix Applied**: Updated `sign_artifact()` to check `skip_signing` config and skip cosign entirely when true.

### Current Behavior

#### With skip_signing: true (CI Environment)
```
✅ Artifact packaged
✅ SBOM generated
✅ Provenance created
✅ Artifact signed (placeholder files created)
✅ Uploaded to S3
✅ Recorded in ledger
```

**DynamoDB Entry**:
- `object_key`: s3://mics295-pipeline-artifacts-bucket/index.tgz
- `rekor_entry_id`: None (expected - signing skipped)
- `status`: verified
- `timestamp`: 2025-11-04T03:21:34.095497

#### With skip_signing: false (Local/OIDC Environment)
- Would create actual cosign signatures
- Would upload to Rekor transparency log
- Would extract and store Rekor entry UUID
- Would enable full cryptographic verification

## Architecture Decision

### Current Approach: Trust Ledger Only in CI
**Pros**:
- Fast (no OIDC authentication delays)
- Works with CodeBuild IAM roles
- Simple CI pipeline

**Cons**:
- No Rekor entries from CI builds
- Trust ledger is single source of truth (not cryptographically proven)
- Can't demonstrate Rekor verification in automated pipeline

### Alternative Approaches

#### Option 1: Separate Signing Step
```
1. CI builds artifact (no signing)
2. Upload to S3
3. Lambda function signs with AWS KMS
4. Lambda uploads to Rekor
5. Lambda records in trust ledger with Rekor ID
```

**Pros**: Centralized signing, Rekor entries, no OIDC needed  
**Cons**: More complex, requires Lambda + KMS setup

#### Option 2: Local Signing, CI Verification
```
1. Developer signs locally with cosign (creates Rekor entry)
2. Upload signed artifact to S3
3. CI verifies against Rekor
4. Deploy if verification passes
```

**Pros**: Full Rekor integration, cryptographic proof  
**Cons**: Manual signing step, not fully automated

#### Option 3: GitHub Actions OIDC (Not CodeBuild)
```
1. Run on GitHub-hosted runners (not CodeBuild)
2. Use GitHub OIDC for cosign
3. Automatic Rekor entries
4. Full automation
```

**Pros**: Full automation, Rekor integration  
**Cons**: Loses CodeBuild integration, different architecture

## Recommendation

For **demonstration/capstone purposes**, implement **Option 1** (Lambda signing) to show:
- Rekor transparency log integration
- Cryptographic verification
- Automated pipeline with Rekor entries
- Industry best practices

For **production use**, current approach (trust ledger only) is acceptable if:
- You trust your AWS infrastructure
- You have other compensating controls
- Performance > cryptographic proof

## Sprint 1 Status

### ✅ Completed
- RekorClient module with full API integration
- Rekor UUID extraction from cosign bundles
- DynamoDB schema updated with rekor_entry_id field
- Verification logic checks Rekor when entry ID present
- skip_signing config properly respected

### ⚠️ Limitation
- CI environment doesn't create Rekor entries (by design with skip_signing)
- Can't test full Rekor verification in automated pipeline
- Need alternative signing approach for Rekor integration

### 🔄 Next Steps
1. **Option A**: Implement Lambda signing service (Sprint 2)
2. **Option B**: Create manual test with local signing
3. **Option C**: Document current approach as "trust ledger mode"

## Test Verification

### What Works
✅ Pipeline completes successfully  
✅ Artifacts uploaded to S3  
✅ DynamoDB entries created  
✅ skip_signing config respected  
✅ No OIDC timeout issues  

### What Needs Testing
⏳ Rekor entry creation (requires OIDC or alternative signing)  
⏳ Rekor verification (requires Rekor entries to exist)  
⏳ Tampered artifact detection via Rekor  
⏳ Fallback to cosign verification  

## Conclusion

Sprint 1 implementation is **technically correct** but **functionally limited** in CI environment due to OIDC authentication requirements. 

**Recommendation**: Proceed with Sprint 2 to implement Lambda-based signing service for full Rekor integration, OR document current approach as "trust ledger mode" for capstone demonstration.

---

**Decision Needed**: Which approach to take for Sprint 2?
