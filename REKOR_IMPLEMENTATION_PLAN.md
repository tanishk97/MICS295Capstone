# Rekor-Based Verification Implementation Plan

## Overview
Upgrade SalsaG trust pipeline from DynamoDB-only verification to cryptographic verification using Rekor transparency log, with DynamoDB as performance cache.

## Current State Analysis

### Existing Flow
1. **Sign Phase** (GitHub Actions):
   - cosign signs artifact → Creates signature in Rekor
   - Upload artifact + signatures to S3
   - Record "verified" status in DynamoDB (no Rekor reference)

2. **Verify Phase** (CodeBuild Deploy):
   - Query DynamoDB for artifact_key
   - If found → Deploy
   - If not found → Block

### Problems
- DynamoDB is trusted source (no cryptographic proof)
- No link between DynamoDB entry and actual Rekor signature
- Vulnerable to DynamoDB compromise
- Not using Rekor transparency log for verification

## Target Architecture

### New Flow
1. **Sign Phase** (GitHub Actions):
   - cosign signs artifact → Rekor entry created
   - **Extract Rekor entry ID/UUID from cosign output**
   - Upload artifact + signatures to S3
   - Record in DynamoDB: artifact_key, sha256, **rekor_entry_id**, timestamp

2. **Verify Phase** (CodeBuild Deploy):
   - Query DynamoDB for artifact_key
   - If found:
     - **Verify Rekor entry exists and matches artifact SHA256**
     - **Validate signature cryptographically via Rekor**
   - If not found or Rekor verification fails:
     - **Fallback: Full cosign verification**
   - Deploy only if verification passes

### Trust Model
- **Primary Trust**: Rekor transparency log (cryptographic proof)
- **Secondary**: DynamoDB (performance cache + audit trail)
- **Fallback**: Direct cosign verification (if cache miss)

## Implementation Steps

### Phase 1: Update Signing Process (salsag/pipeline.py)

#### 1.1 Extract Rekor Entry ID from Cosign
**File**: `salsag-cli/salsag/pipeline.py`

**Changes**:
```python
def sign_artifact(self, artifact_path):
    """Sign artifact and extract Rekor entry ID"""
    
    # Current: cosign sign-blob (output to files)
    # New: Capture cosign output to extract Rekor UUID
    
    result = subprocess.run(
        ['cosign', 'sign-blob', ...],
        capture_output=True,
        text=True
    )
    
    # Parse output for Rekor entry:
    # "tlog entry created with index: 123456789"
    # OR query Rekor API with signature
    
    rekor_entry_id = extract_rekor_id(result.stdout)
    return rekor_entry_id
```

**Alternative**: Query Rekor API after signing
```python
def get_rekor_entry_for_signature(signature_file, artifact_sha256):
    """Query Rekor API to find entry for our signature"""
    # POST to https://rekor.sigstore.dev/api/v1/index/retrieve
    # Search by artifact SHA256
    # Return entry UUID
```

#### 1.2 Update DynamoDB Schema
**Changes**:
- Add `rekor_entry_id` field (String)
- Add `rekor_log_index` field (Number, optional)
- Keep existing fields for backward compatibility

#### 1.3 Update record_in_ledger()
```python
def record_in_ledger(self, artifact_key, sha256, rekor_entry_id):
    self.dynamodb.put_item(
        TableName=self.ledger_table,
        Item={
            'artifact_key': {'S': artifact_key},
            'sha256_digest': {'S': sha256},
            'rekor_entry_id': {'S': rekor_entry_id},  # NEW
            'verification_status': {'S': 'verified'},
            'timestamp': {'S': timestamp},
            'metadata': {'M': {
                'rekor_verified': {'BOOL': True}  # NEW
            }}
        }
    )
```

### Phase 2: Implement Rekor Verification (salsag/verifier.py)

#### 2.1 Create Rekor Client Module
**New File**: `salsag-cli/salsag/rekor_client.py`

**Functions**:
```python
class RekorClient:
    def __init__(self, rekor_url="https://rekor.sigstore.dev"):
        self.rekor_url = rekor_url
    
    def get_entry(self, entry_id):
        """Fetch Rekor entry by UUID"""
        # GET /api/v1/log/entries/{entryUUID}
        # Returns: entry with signature, public key, artifact hash
    
    def verify_entry(self, entry_id, expected_sha256):
        """Verify Rekor entry matches expected artifact"""
        entry = self.get_entry(entry_id)
        # Extract artifact hash from entry
        # Compare with expected_sha256
        # Verify signature in entry
        return entry['body']['spec']['data']['hash'] == expected_sha256
    
    def search_by_hash(self, sha256):
        """Search Rekor for entries matching artifact hash"""
        # POST /api/v1/index/retrieve
        # Returns: list of entry UUIDs
```

#### 2.2 Update Verifier Class
**File**: `salsag-cli/salsag/verifier.py`

**Changes**:
```python
from .rekor_client import RekorClient

class Verifier:
    def __init__(self, config):
        self.config = config
        self.dynamodb = boto3.client('dynamodb')
        self.s3 = boto3.client('s3')
        self.rekor = RekorClient()  # NEW
    
    def verify_artifact(self, artifact_key):
        """Verify artifact using Rekor + DynamoDB cache"""
        
        # Step 1: Check DynamoDB cache
        ledger_entry = self._get_ledger_entry(artifact_key)
        
        if ledger_entry:
            rekor_entry_id = ledger_entry.get('rekor_entry_id')
            expected_sha256 = ledger_entry.get('sha256_digest')
            
            if rekor_entry_id:
                # Step 2: Verify against Rekor
                try:
                    if self.rekor.verify_entry(rekor_entry_id, expected_sha256):
                        return VerificationResult(
                            status='verified',
                            method='rekor',
                            rekor_entry_id=rekor_entry_id
                        )
                except RekorError as e:
                    # Rekor verification failed, try fallback
                    pass
        
        # Step 3: Fallback - Full cosign verification
        return self._cosign_verify_fallback(artifact_key)
    
    def _cosign_verify_fallback(self, artifact_key):
        """Full cryptographic verification using cosign"""
        # Download artifact + signatures from S3
        # Run: cosign verify-blob --signature ... --certificate ...
        # If successful, update DynamoDB with Rekor entry
```

### Phase 3: Update CLI Commands

#### 3.1 Update `salsaG start` Command
**File**: `salsag-cli/salsag/cli.py`

**Changes**:
- After signing, extract Rekor entry ID
- Pass Rekor entry ID to record_in_ledger()
- Display Rekor entry ID in output

#### 3.2 Update `salsaG verify` Command
**Changes**:
- Use new Rekor-based verification
- Display verification method (rekor/cosign/cache)
- Show Rekor entry ID in output

#### 3.3 Add `salsaG rekor` Command (Optional)
**New command for debugging**:
```bash
salsaG rekor --artifact index.tgz
# Shows: Rekor entry ID, log index, timestamp, signature details
```

### Phase 4: Update BuildSpec for Deploy

#### 4.1 Update buildspec.yml
**File**: `buildspec.yml`

**Changes**:
```yaml
pre_build:
  commands:
    - echo "🔍 Verifying index.tgz with SalsaG (Rekor-based)..."
    - |
      if salsaG verify --artifact index.tgz --config salsag.yml; then
        echo "✅ Rekor verification PASSED - proceeding with deployment"
      else
        echo "❌ Rekor verification FAILED - stopping deployment"
        exit 1
      fi
```

**No changes needed** - verification logic is internal to SalsaG CLI

### Phase 5: Testing & Validation

#### 5.1 Unit Tests
**New File**: `salsag-cli/tests/test_rekor_client.py`
- Test Rekor API calls
- Test entry verification
- Test error handling

**New File**: `salsag-cli/tests/test_rekor_verification.py`
- Test end-to-end Rekor verification
- Test cache hit/miss scenarios
- Test fallback to cosign

#### 5.2 Integration Tests
1. **Happy Path**: Sign → Record → Verify via Rekor
2. **Cache Hit**: Verify using DynamoDB + Rekor
3. **Cache Miss**: Verify using cosign fallback
4. **Tampered Artifact**: Verification fails
5. **Invalid Rekor Entry**: Falls back to cosign

#### 5.3 Manual Testing
```bash
# Test 1: Sign and verify new artifact
salsaG start --artifact ./dist --config salsag.yml
salsaG verify --artifact index.tgz --config salsag.yml

# Test 2: Check Rekor entry directly
curl https://rekor.sigstore.dev/api/v1/log/entries/{uuid}

# Test 3: Verify via pipeline
aws codepipeline start-pipeline-execution --name mics295-pipeline
```

## Implementation Order

### Sprint 1: Core Rekor Integration (2-3 hours)
1. ✅ Create `rekor_client.py` with basic API calls
2. ✅ Update `pipeline.py` to extract Rekor entry ID
3. ✅ Update DynamoDB schema (add rekor_entry_id field)
4. ✅ Update `record_in_ledger()` to store Rekor ID

### Sprint 2: Verification Logic (2-3 hours)
5. ✅ Implement Rekor verification in `verifier.py`
6. ✅ Add fallback to cosign verification
7. ✅ Update CLI commands to use new verification
8. ✅ Add error handling and logging

### Sprint 3: Testing & Documentation (1-2 hours)
9. ✅ Write unit tests
10. ✅ Integration testing
11. ✅ Update README with Rekor details
12. ✅ Update PROJECT_MEMORY.md

## Technical Details

### Rekor API Endpoints
- **Base URL**: https://rekor.sigstore.dev
- **Get Entry**: `GET /api/v1/log/entries/{entryUUID}`
- **Search by Hash**: `POST /api/v1/index/retrieve`
- **Get Log Info**: `GET /api/v1/log`

### Rekor Entry Structure
```json
{
  "body": {
    "spec": {
      "signature": {
        "content": "base64-signature",
        "publicKey": {
          "content": "base64-cert"
        }
      },
      "data": {
        "hash": {
          "algorithm": "sha256",
          "value": "abc123..."
        }
      }
    }
  },
  "logIndex": 123456789,
  "logID": "...",
  "integratedTime": 1699000000
}
```

### Extracting Rekor Entry from Cosign Output
**Option 1**: Parse cosign stdout
```
tlog entry created with index: 123456789
```

**Option 2**: Query Rekor API with artifact SHA256
```bash
curl -X POST https://rekor.sigstore.dev/api/v1/index/retrieve \
  -H "Content-Type: application/json" \
  -d '{"hash":"sha256:abc123..."}'
```

**Option 3**: Parse .sigstore bundle (if using cosign v2+)
```json
{
  "rekorBundle": {
    "logEntry": {
      "logIndex": "123456789",
      "logID": "..."
    }
  }
}
```

## Dependencies

### Python Packages
```txt
# Add to salsag-cli/requirements.txt
requests>=2.31.0  # For Rekor API calls
```

### System Dependencies
- cosign (already installed)
- curl (for manual testing)

## Backward Compatibility

### Migration Strategy
1. **Phase 1**: Add Rekor fields to new entries (old entries still work)
2. **Phase 2**: Backfill Rekor IDs for existing entries (optional)
3. **Phase 3**: Require Rekor verification for all new deployments

### Handling Old Entries
```python
if 'rekor_entry_id' not in ledger_entry:
    # Old entry without Rekor ID
    # Option 1: Search Rekor by SHA256
    # Option 2: Fall back to cosign verification
    # Option 3: Require re-signing
```

## Security Considerations

### Threat Model
- **Compromised DynamoDB**: Rekor verification catches tampering
- **Compromised S3**: Rekor verification catches modified artifacts
- **Compromised Rekor**: Fallback to cosign verification
- **Network Issues**: Fallback to cosign verification

### Defense in Depth
1. **Layer 1**: Rekor transparency log (public, immutable)
2. **Layer 2**: DynamoDB cache (fast, auditable)
3. **Layer 3**: Cosign verification (cryptographic proof)
4. **Layer 4**: S3 signatures (backup verification)

## Performance Impact

### Expected Timings
- **Current (DynamoDB only)**: ~2 seconds
- **New (DynamoDB + Rekor)**: ~5-8 seconds
  - DynamoDB lookup: 0.5s
  - Rekor API call: 2-5s
  - Signature verification: 2-3s
- **Fallback (Full cosign)**: ~40 seconds

### Optimization
- Cache Rekor responses locally (optional)
- Parallel verification (DynamoDB + Rekor)
- Skip Rekor for recent entries (trust window)

## Success Criteria

### Functional
- ✅ Artifacts signed with Rekor entry ID recorded
- ✅ Verification checks Rekor transparency log
- ✅ Fallback to cosign works when Rekor unavailable
- ✅ Tampered artifacts detected and blocked

### Non-Functional
- ✅ Verification completes in <10 seconds (90th percentile)
- ✅ Zero false positives (legitimate artifacts pass)
- ✅ Zero false negatives (tampered artifacts blocked)
- ✅ Backward compatible with existing entries

### Documentation
- ✅ README updated with Rekor details
- ✅ Architecture diagrams include Rekor
- ✅ Troubleshooting guide for Rekor issues

## Rollout Plan

### Phase 1: Development (This Session)
- Implement core Rekor integration
- Basic testing in dev environment

### Phase 2: Testing (Next Session)
- Comprehensive integration tests
- Performance benchmarking
- Security validation

### Phase 3: Deployment
- Deploy to GitHub Actions workflow
- Monitor first few pipeline runs
- Validate Rekor entries in transparency log

### Phase 4: Documentation & Demo
- Update all documentation
- Create demo showing Rekor verification
- Prepare capstone presentation materials

## Open Questions

1. **Rekor Entry Extraction**: Which method is most reliable?
   - Parse cosign output
   - Query Rekor API by hash
   - Use .sigstore bundle

2. **Fallback Strategy**: When to use cosign fallback?
   - Always (defense in depth)
   - Only on Rekor failure
   - Never (strict Rekor-only)

3. **Cache Invalidation**: How long to trust DynamoDB cache?
   - Always verify Rekor (slower, more secure)
   - Trust cache for N minutes (faster, less secure)
   - Configurable per environment

4. **Backward Compatibility**: How to handle old entries?
   - Require re-signing
   - Search Rekor by SHA256
   - Allow without Rekor (degraded security)

## Next Steps

1. Review and approve this plan
2. Start Sprint 1: Core Rekor Integration
3. Implement and test incrementally
4. Update documentation as we go

---

**Ready to proceed?** Let me know if you want to adjust anything in the plan before we start implementation.
