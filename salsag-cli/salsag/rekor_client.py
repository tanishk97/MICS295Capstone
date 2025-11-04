#!/usr/bin/env python3

import json
import base64
import hashlib
from typing import Optional, Dict, Any, List
import requests
from requests.exceptions import RequestException, Timeout


class RekorError(Exception):
    """Rekor API error"""
    pass


class RekorClient:
    """Client for interacting with Rekor transparency log"""
    
    def __init__(self, rekor_url: str = "https://rekor.sigstore.dev"):
        self.rekor_url = rekor_url.rstrip('/')
        self.api_base = f"{self.rekor_url}/api/v1"
        self.timeout = 30
    
    def get_entry(self, entry_uuid: str) -> Dict[str, Any]:
        """Fetch Rekor entry by UUID"""
        url = f"{self.api_base}/log/entries/{entry_uuid}"
        
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Timeout:
            raise RekorError(f"Timeout fetching Rekor entry {entry_uuid}")
        except RequestException as e:
            raise RekorError(f"Failed to fetch Rekor entry: {e}")
    
    def search_by_hash(self, sha256_hash: str) -> List[str]:
        """Search Rekor for entries matching artifact SHA256 hash"""
        url = f"{self.api_base}/index/retrieve"
        
        # Rekor expects hash without 'sha256:' prefix
        if sha256_hash.startswith('sha256:'):
            sha256_hash = sha256_hash[7:]
        
        payload = {
            "hash": f"sha256:{sha256_hash}"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except Timeout:
            raise RekorError(f"Timeout searching Rekor for hash {sha256_hash}")
        except RequestException as e:
            raise RekorError(f"Failed to search Rekor: {e}")
    
    def verify_entry(self, entry_uuid: str, expected_sha256: str) -> bool:
        """Verify Rekor entry matches expected artifact SHA256"""
        try:
            entry_data = self.get_entry(entry_uuid)
            
            # Extract the entry (Rekor returns dict with UUID as key)
            if entry_uuid not in entry_data:
                raise RekorError(f"Entry {entry_uuid} not found in response")
            
            entry = entry_data[entry_uuid]
            
            # Decode the body (base64 encoded)
            body_encoded = entry.get('body')
            if not body_encoded:
                raise RekorError("Entry body not found")
            
            body = json.loads(base64.b64decode(body_encoded))
            
            # Extract hash from entry
            spec = body.get('spec', {})
            data = spec.get('data', {})
            hash_info = data.get('hash', {})
            
            entry_hash = hash_info.get('value', '')
            
            # Normalize hashes for comparison
            if expected_sha256.startswith('sha256:'):
                expected_sha256 = expected_sha256[7:]
            
            if entry_hash == expected_sha256:
                return True
            else:
                raise RekorError(
                    f"Hash mismatch: expected {expected_sha256}, got {entry_hash}"
                )
                
        except RekorError:
            raise
        except Exception as e:
            raise RekorError(f"Failed to verify Rekor entry: {e}")
    
    def get_latest_entry_for_hash(self, sha256_hash: str) -> Optional[str]:
        """Get the most recent Rekor entry UUID for a given artifact hash"""
        try:
            entry_uuids = self.search_by_hash(sha256_hash)
            
            if not entry_uuids:
                return None
            
            # Return the first (most recent) entry
            return entry_uuids[0] if isinstance(entry_uuids, list) else entry_uuids
            
        except RekorError:
            return None
    
    def extract_rekor_uuid_from_bundle(self, bundle_path: str) -> Optional[str]:
        """Extract Rekor entry UUID from cosign bundle file"""
        try:
            with open(bundle_path, 'r') as f:
                bundle = json.load(f)
            
            # Cosign v2+ bundle structure
            rekor_bundle = bundle.get('rekorBundle', {})
            log_entry = rekor_bundle.get('logEntry', {})
            
            # Try to get UUID from different possible locations
            uuid = log_entry.get('uuid') or log_entry.get('logID')
            
            return uuid
            
        except Exception:
            return None
