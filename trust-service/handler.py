import os, json, hashlib, tempfile, subprocess, boto3
from datetime import datetime

S3 = boto3.client("s3")
DDB = boto3.resource("dynamodb")
TABLE = os.getenv("LEDGER_TABLE", "trust-ledger")
ISSUER = os.getenv("OIDC_ISSUER", "https://token.actions.githubusercontent.com")
WEBSITE_BUCKET = os.getenv("WEBSITE_BUCKET", "")

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()

def cosign_verify_sig(file_path, cert_path, sig_path):
    cmd = [
        "cosign", "verify-blob",
        "--certificate-oidc-issuer", ISSUER,
        "--certificate-identity-regexp", "https://github.com/.+",
        "--signature", sig_path,
        "--certificate", cert_path,
        file_path
    ]
    return run(cmd)

def cosign_verify_att(file_path, att_path):
    cmd = [
        "cosign", "verify-blob-attestation",
        "--type", "slsaprovenance",
        "--certificate-oidc-issuer", ISSUER,
        "--certificate-identity-regexp", "https://github.com/.+",
        "--bundle", att_path,
        file_path
    ]
    return run(cmd)

def run(cmd):
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        return True, out
    except subprocess.CalledProcessError as e:
        return False, e.output

def tag_object(bucket, key, tags):
    S3.put_object_tagging(Bucket=bucket, Key=key,
        Tagging={"TagSet": [{"Key": k, "Value": v} for k, v in tags.items()]})

def put_ledger(uri, status, details, digest=None):
    if not TABLE: return
    item = {
        "object_key": uri,
        "status": status,
        "details": details[:3000],
        "timestamp": datetime.utcnow().isoformat(),
    }
    if digest:
        item["digest"] = digest
    DDB.Table(TABLE).put_item(Item=item)

def promote_to_website(staging_bucket, key):
    """Automatically promote verified artifacts to website bucket"""
    if not WEBSITE_BUCKET:
        return False
    
    try:
        S3.copy_object(
            CopySource={'Bucket': staging_bucket, 'Key': key},
            Bucket=WEBSITE_BUCKET,
            Key=key,
            TaggingDirective='REPLACE',
            Tagging='trust=verified'
        )
        return True
    except Exception as e:
        print(f"Failed to promote {key}: {e}")
        return False

def handler(event, context):
    try:
        # Handle S3 event or direct invocation
        if "Records" in event:
            rec = event["Records"][0]
            bucket = rec["s3"]["bucket"]["name"]
            key = rec["s3"]["object"]["key"]
        else:
            bucket = event["bucket"]
            key = event["key"]

        # Only process .tgz files
        if not key.endswith('.tgz'):
            return {"message": "Skipped non-tarball file", "key": key}

        base = key.rsplit("/", 1)[-1]
        sig_key = base + ".sig"
        pem_key = base + ".pem"
        att_key = base + ".attestation.sigstore"

        with tempfile.TemporaryDirectory() as d:
            # Download all required files
            f = os.path.join(d, base)
            s = os.path.join(d, sig_key)
            p = os.path.join(d, pem_key)
            a = os.path.join(d, att_key)
            
            S3.download_file(bucket, key, f)
            S3.download_file(bucket, sig_key, s)
            S3.download_file(bucket, pem_key, p)
            S3.download_file(bucket, att_key, a)
            
            # Calculate digest
            digest = sha256(f)
            
            # Verify signature and attestation
            ok1, out1 = cosign_verify_sig(f, p, s)
            ok2, out2 = cosign_verify_att(f, a)

        uri = f"s3://{bucket}/{key}"
        
        if ok1 and ok2:
            # Tag as verified
            tag_object(bucket, key, {"trust": "verified", "digest": digest})
            
            # Log success
            put_ledger(uri, "verified", out1 + "\n" + out2, digest)
            
            # Auto-promote to website if configured
            promoted = False
            if WEBSITE_BUCKET:
                promoted = promote_to_website(bucket, key)
            
            return {
                "verified": True,
                "digest": digest,
                "promoted": promoted,
                "uri": uri
            }
        else:
            # Log failure
            error_details = (out1 if not ok1 else "") + (out2 if not ok2 else "")
            put_ledger(uri, "failed", error_details)
            
            return {
                "verified": False,
                "error": "Verification failed",
                "details": error_details,
                "uri": uri
            }
            
    except Exception as e:
        error_msg = f"Lambda execution failed: {str(e)}"
        print(error_msg)
        return {
            "verified": False,
            "error": error_msg
        }
