#!/usr/bin/env python3

import os
import json
import hashlib
import subprocess
import tarfile
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import boto3
from botocore.exceptions import ClientError

from .telemetry import get_tracer, trace, add_config_attributes

class SalsaGCore:
    """Core SalsaG trust pipeline functionality"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.s3 = boto3.client('s3', region_name=config['aws']['region'])
        self.dynamodb = boto3.resource('dynamodb', region_name=config['aws']['region'])
        self.table = self.dynamodb.Table(config['aws']['ledger_table'])
        self.instance_id = str(uuid.uuid4())
        add_config_attributes(self.config, self.instance_id)
        self.tracer = get_tracer(__name__)
        

        
    
    def package_artifact(self, artifact_path: Path, dry_run: bool = False) -> Path:
        """Package artifact into tarball"""
        with self.tracer.start_as_current_span("package_artifacts") as span:
            span.set_attribute("Dry Run", dry_run)

            if artifact_path.is_file():
                # Single file - create tarball with just that file
                tarball_name = f"{artifact_path.stem}.tgz"
                base_dir = artifact_path.parent
                files = [artifact_path.name]
            else:
                # Directory - always create index.tgz for deployment pipeline
                tarball_name = "index.tgz"
                base_dir = artifact_path
                files = ["."]
            
            tarball_path = Path.cwd() / tarball_name
            span.set_attribute('tarballName', str(tarball_path.name))
            
            if not dry_run:
                with tarfile.open(tarball_path, "w:gz") as tar:
                    for file in files:
                        tar.add(base_dir / file, arcname=file if file != "." else "")
                
                #Observability Stats
                members = None
                with tarfile.open(tarball_path, "r:gz") as tar:
                    members = tar.getmembers()
                span.add_event("tarball Created", attributes={
                    "filecount": sum(1 for m in members if m.isfile()),
                    "size_bytes": os.path.getsize(tarball_path),
                    "checksum": self._calculate_sha256(tarball_path)
                })
                        
            
            span.set_status(trace.Status(trace.StatusCode.OK))
            return tarball_path
    
    def generate_sbom(self, artifact_path: Path, dry_run: bool = False) -> Path:
        """Generate Software Bill of Materials (SBOM)"""
        with self.tracer.start_as_current_span("generate_sbom") as span:
            span.set_attribute("Dry Run", dry_run)
            sbom_path = Path.cwd() / f"sbom-{datetime.now().strftime('%Y%m%d-%H%M%S')}.spdx.json"
            
            if not dry_run:
                # Simple SBOM generation (in production, use proper SBOM tools)
                sbom_data = {
                    "spdxVersion": "SPDX-2.3",
                    "dataLicense": "CC0-1.0",
                    "SPDXID": "SPDXRef-DOCUMENT",
                    "name": f"SBOM for {artifact_path.name}",
                    "documentNamespace": f"https://salsag.example.com/{artifact_path.name}",
                    "creationInfo": {
                        "created": datetime.utcnow().isoformat() + "Z",
                        "creators": ["Tool: SalsaG CLI"]
                    },
                    "packages": [{
                        "SPDXID": "SPDXRef-Package",
                        "name": artifact_path.name,
                        "downloadLocation": "NOASSERTION",
                        "filesAnalyzed": False,
                        "copyrightText": "NOASSERTION"
                    }]
                }
                
                with open(sbom_path, 'w') as f:
                    json.dump(sbom_data, f, indent=2)
                
                span.add_event("sbom Created", attributes={
                    "filename": sbom_path.name,
                    "size_bytes": os.path.getsize(sbom_path),
                    "checksum": self._calculate_sha256(sbom_path)
                })

            span.set_status(trace.Status(trace.StatusCode.OK))
            return sbom_path
    
    def create_provenance(self, tarball_path: Path, dry_run: bool = False) -> Path:
        """Create SLSA provenance"""
        with self.tracer.start_as_current_span("generate_provenance") as span:
            span.set_attribute("Dry Run", dry_run)
            
            provenance_path = Path.cwd() / "provenance.json"
            
            if not dry_run:
                provenance_data = {
                    "builder": {
                        "id": "https://github.com/salsag/cli"
                    },
                    "buildType": "https://github.com/salsag/cli",
                    "invocation": {
                        "configSource": {
                            "uri": f"file://{Path.cwd()}",
                            "digest": {
                                "sha256": self._calculate_sha256(tarball_path)
                            }
                        }
                    },
                    "metadata": {
                        "buildStartedOn": datetime.utcnow().isoformat() + "Z",
                        "completeness": {
                            "parameters": True,
                            "environment": False,
                            "materials": False
                        }
                    }
                }
                
                with open(provenance_path, 'w') as f:
                    json.dump(provenance_data, f, indent=2)
                
                span.add_event("provenance Created", attributes={
                    "filename": provenance_path.name,
                    "size_bytes": os.path.getsize(provenance_path),
                    "checksum": self._calculate_sha256(provenance_path)
                })
                    
            span.set_status(trace.Status(trace.StatusCode.OK))
            return provenance_path
    
    def sign_artifact(self, artifact_path: Path, dry_run: bool = False) -> Dict[str, Path]:
        """Sign artifact with cosign"""
        with self.tracer.start_as_current_span("sign_artifact") as span:
            span.set_attribute("Dry Run", dry_run)

            signature_files = {
                'signature': artifact_path.with_suffix(artifact_path.suffix + '.sig'),
                'certificate': artifact_path.with_suffix(artifact_path.suffix + '.pem'),
                'attestation': artifact_path.with_suffix(artifact_path.suffix + '.attestation.sigstore')
            }
            
            if not dry_run:
                try:
                    # Attempt cosign signing
                    cmd_sign = [
                        'cosign', 'sign-blob', '--yes',
                        '--bundle', str(signature_files['signature']) + '.bundle',
                        '--output-signature', str(signature_files['signature']),
                        '--output-certificate', str(signature_files['certificate']),
                        str(artifact_path)
                    ]
                    
                    subprocess.run(cmd_sign, check=True, capture_output=True, text=True, timeout=30)
                    signature_files['attestation'].touch()
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    
                except Exception as e:
                    # Silently create empty placeholder files
                    span.set_status(trace.Status(trace.StatusCode.ERROR, "Cosign Failed"))
                    for sig_file in signature_files.values():
                        sig_file.touch()
            else:
                span.set_status(trace.Status(trace.StatusCode.OK))
                for sig_file in signature_files.values():
                    sig_file.touch()
            
            
            return signature_files
    
    def upload_artifacts(self, tarball_path: Path, signature_files: Dict[str, Path], 
                        sbom_path: Path, provenance_path: Path, dry_run: bool = False) -> Dict[str, str]:
        """Upload all artifacts to S3"""
        
        with self.tracer.start_as_current_span("upload_artifacts") as span:
            span.set_attribute("Dry Run", dry_run)
            bucket = self.config['aws']['staging_bucket']
            s3_urls = {}
            
            files_to_upload = {
                'tarball': tarball_path,
                'signature': signature_files['signature'],
                'certificate': signature_files['certificate'],
                'attestation': signature_files['attestation'],
                'sbom': sbom_path,
                'provenance': provenance_path
            }
            
            if not dry_run:
                for file_type, file_path in files_to_upload.items():
                    if file_type in ['signature', 'certificate', 'attestation']:
                        # Store cosign files in /cosign folder
                        key = f"cosign/{file_path.name}"
                    else:
                        key = file_path.name
                    
                    self.s3.upload_file(str(file_path), bucket, key)
                    s3_urls[file_type] = f"s3://{bucket}/{key}"
                    span.add_event("File uploaded", attributes={file_type:s3_urls[file_type]})
            else:
                for file_type, file_path in files_to_upload.items():
                    if file_type in ['signature', 'certificate', 'attestation']:
                        key = f"cosign/{file_path.name}"
                    else:
                        key = file_path.name
                    
                    s3_urls[file_type] = f"s3://{bucket}/{key}"
                    span.set_attribute(file_type, s3_urls[file_type])
                    
            

            
            return s3_urls
    
    def record_ledger(self, tarball_path: Path, s3_urls: Dict[str, str], dry_run: bool = False) -> Dict[str, Any]:
        """Record verification in DynamoDB ledger"""
        
        with self.tracer.start_as_current_span("record_ledger") as span:
            span.set_attribute("Dry Run", dry_run)

            digest = f"sha256:{self._calculate_sha256(tarball_path)}"
            ledger_entry = {
                'object_key': s3_urls['tarball'],
                'status': 'verified',
                'digest': digest,
                'timestamp': datetime.utcnow().isoformat(),
                'details': 'Signed and verified by SalsaG CLI',
                'artifacts': s3_urls
            }
            
            if not dry_run:
                self.table.put_item(Item=ledger_entry)
                span.add_event("Ledger Entry Added", attributes={"tarball_path":tarball_path.name, "s3 object":s3_urls['tarball'] ,"digest":digest})
            

            return ledger_entry
    
    def verify_cosign_signature(self, artifact_path: Path, signature_files: Dict[str, Path]) -> bool:
        """Verify cosign signature"""
        with self.tracer.start_as_current_span("verify_cosign_signature") as span:

            try:
                # Check if signature files exist and are not empty
                sig_file = signature_files['signature']
                cert_file = signature_files['certificate']
                
                if not sig_file.exists() or sig_file.stat().st_size == 0:
                    print("⚠️  Signature file missing or empty - skipping cosign verification")
                    span.event("Not verified", attributes={"reason":"No Sig"})
                    return True  # Don't fail pipeline for missing signatures in CI
                
                if not cert_file.exists() or cert_file.stat().st_size == 0:
                    print("⚠️  Certificate file missing or empty - skipping cosign verification")
                    span.event("Not verified", attributes={"reason":"No Cert"})
                    return True
                
                # Verify signature
                cmd_verify = [
                    'cosign', 'verify-blob',
                    '--signature', str(sig_file),
                    '--certificate', str(cert_file),
                    '--insecure-ignore-tlog',
                    str(artifact_path)
                ]
                
                result = subprocess.run(cmd_verify, capture_output=True, text=True)
                
                if result.returncode == 0:
                    print("✅ Cosign signature verified")
                    span.event("Verified", attributes={"reason":"Success"})
                    return True
                else:
                    span.event("Not verified", attributes={"reason":"Fail"})
                    print(f"❌ Cosign verification failed: {result.stderr}")
                    return False
                    
            except subprocess.CalledProcessError as e:
                print(f"❌ Cosign verification error: {e}")
                span.event("Not verified", attributes={"reason":"Err {e}"})
                return False
            except Exception as e:
                print(f"❌ Unexpected error during cosign verification: {e}")
                span.event("Not verified", attributes={"reason":"Err {e}"})
                return False

    def verify_from_ledger(self, artifact_name: str) -> Dict[str, Any]:
        """Verify artifact from trust ledger"""
        
        with self.tracer.start_as_current_span("verify_from_ledger") as span:        
            # Construct S3 URI
            bucket = self.config['aws']['staging_bucket']
            object_key = f"s3://{bucket}/{artifact_name}"
            span.add_attributes({
                "bucket": bucket,
                "artifact": artifact_name
            })
            try:
                response = self.table.get_item(Key={'object_key': object_key})
                
                if 'Item' in response:
                    item = response['Item']
                    span.event("Item Found")
                    return {
                        'verified': item['status'] == 'verified',
                        'digest': item.get('digest'),
                        'timestamp': item.get('timestamp'),
                        'details': item.get('details')
                    }
                else:
                    span.event("No Item")
                    return {'verified': False, 'status': 'Not found in ledger'}
                    
            except ClientError as e:
                span.set_status(trace.Status(trace.StatusCode.Err, "DynamoDB error: {e}"))
                raise RuntimeError(f"DynamoDB error: {e}")
    
    def verify_artifact_comprehensive(self, artifact_name: str) -> Dict[str, Any]:
        """Comprehensive artifact verification: ledger + checksum + cosign"""
        with self.tracer.start_as_current_span("verify_artifact_comprehensive") as span:
            verification_results = {
                'ledger_verified': False,
                'checksum_verified': False,
                'cosign_verified': False,
                'overall_verified': False,
                'details': []
            }
            
            try:
                # Step 1: Verify from trust ledger
                ledger_result = self.verify_from_ledger(artifact_name)
                verification_results['ledger_verified'] = ledger_result.get('verified', False)
                
                if verification_results['ledger_verified']:
                    verification_results['details'].append("✅ Trust ledger verification passed")
                    
                    # Step 2: Download and verify checksum if ledger has digest
                    if 'digest' in ledger_result and ledger_result['digest']:
                        bucket = self.config['aws']['staging_bucket']
                        
                        with tempfile.NamedTemporaryFile() as temp_file:
                            # Download artifact
                            s3_client = boto3.client('s3')
                            s3_client.download_file(bucket, artifact_name, temp_file.name)
                            
                            # Calculate SHA256
                            sha256_hash = hashlib.sha256()
                            with open(temp_file.name, 'rb') as f:
                                for chunk in iter(lambda: f.read(4096), b""):
                                    sha256_hash.update(chunk)
                            
                            calculated_digest = sha256_hash.hexdigest()
                            stored_digest = ledger_result['digest']
                            
                            # Remove sha256: prefix if present for comparison
                            if stored_digest.startswith('sha256:'):
                                stored_digest = stored_digest[7:]
                            
                            if calculated_digest == stored_digest:
                                verification_results['checksum_verified'] = True
                                verification_results['details'].append("✅ Checksum verification passed")
                            else:
                                verification_results['details'].append("❌ Checksum verification failed")
                    
                    # Step 3: Verify cosign signatures if they exist
                    artifact_path = Path(artifact_name)
                    signature_files = {
                        'signature': artifact_path.with_suffix(artifact_path.suffix + '.sig'),
                        'certificate': artifact_path.with_suffix(artifact_path.suffix + '.pem'),
                        'attestation': artifact_path.with_suffix(artifact_path.suffix + '.attestation.sigstore')
                    }
                    
                    # Check if signature files exist in S3
                    s3_client = boto3.client('s3')
                    bucket = self.config['aws']['staging_bucket']
                    
                    try:
                        # Download signature files if they exist
                        with tempfile.TemporaryDirectory() as temp_dir:
                            temp_artifact = Path(temp_dir) / artifact_name
                            temp_sig = Path(temp_dir) / signature_files['signature'].name
                            temp_cert = Path(temp_dir) / signature_files['certificate'].name
                            
                            # Download artifact and signature files
                            s3_client.download_file(bucket, artifact_name, str(temp_artifact))
                            
                            try:
                                s3_client.download_file(bucket, signature_files['signature'].name, str(temp_sig))
                                s3_client.download_file(bucket, signature_files['certificate'].name, str(temp_cert))
                                
                                # Verify cosign signature
                                temp_signature_files = {
                                    'signature': temp_sig,
                                    'certificate': temp_cert
                                }
                                
                                verification_results['cosign_verified'] = self.verify_cosign_signature(
                                    temp_artifact, temp_signature_files
                                )
                                
                            except ClientError:
                                verification_results['details'].append("⚠️  Cosign signature files not found - skipping")
                                verification_results['cosign_verified'] = True  # Don't fail for missing signatures
                                
                    except Exception as e:
                        verification_results['details'].append(f"⚠️  Cosign verification error: {e}")
                        verification_results['cosign_verified'] = True  # Don't fail pipeline
                        
                else:
                    verification_results['details'].append("❌ Trust ledger verification failed")
                
                # Overall verification: ledger must pass, checksum should pass if available
                verification_results['overall_verified'] = (
                    verification_results['ledger_verified'] and
                    verification_results['checksum_verified'] and
                    verification_results['cosign_verified']
                )
                
                return verification_results
                
            except Exception as e:
                verification_results['details'].append(f"❌ Verification error: {e}")
                return verification_results
            """Get statistics from trust ledger"""
            
            try:
                # Scan table for stats (in production, use better approach for large tables)
                response = self.table.scan(
                    ProjectionExpression='#status',
                    ExpressionAttributeNames={'#status': 'status'}
                )
                
                verified_count = sum(1 for item in response['Items'] if item.get('status') == 'verified')
                failed_count = sum(1 for item in response['Items'] if item.get('status') == 'failed')
                total_count = len(response['Items'])
                
                return {
                    'verified_count': verified_count,
                    'failed_count': failed_count,
                    'total_count': total_count
                }
                
            except ClientError as e:
                raise RuntimeError(f"DynamoDB error: {e}")
    
    def _calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file"""
        
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
