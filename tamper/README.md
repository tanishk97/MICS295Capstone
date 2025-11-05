# Tampered Artifacts for Testing

This folder contains tampered artifacts for manual negative testing.

## Usage

### Test Tampering Detection in Pipeline

1. **Trigger pipeline** (push to main branch)
2. **Wait for manual approval stage**
3. **Upload tampered artifact**:
   ```bash
   aws s3 cp tamper/index.tgz s3://mics295-pipeline-artifacts-bucket/index.tgz
   ```
4. **Approve pipeline**
5. **Verify deployment fails** with "Checksum verification failed"

### Test Standalone Verifier

1. **Upload tampered artifact**:
   ```bash
   aws s3 cp tamper/index.tgz s3://mics295-pipeline-artifacts-bucket/index.tgz
   ```
2. **Run verifier**:
   ```bash
   aws codebuild start-build \
     --project-name salsag-artifact-verifier \
     --environment-variables-override name=ARTIFACT_KEY,value=index.tgz
   ```
3. **Verify build fails** with "Checksum verification failed"

## Expected Results

- ❌ Verification should FAIL
- ❌ Deployment should be BLOCKED
- ✅ Logs should show: "❌ Checksum verification failed"

## Restore Clean Artifact

To restore the original artifact after testing:
```bash
# Trigger a new pipeline run by pushing a change
git commit --allow-empty -m "Restore clean artifact"
git push
```
