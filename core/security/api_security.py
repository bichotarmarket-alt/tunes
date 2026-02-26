"""
API Security
"""

import secrets
import time
from typing import Dict, Optional
from fastapi import HTTPException, status


class APIKeyManager:
    """API key management for API security"""
    
    def __init__(self):
        self.api_keys: Dict[str, dict] = {}
        self.key_prefix = "ak_"
    
    def generate_api_key(
        self,
        user_id: str,
        name: str,
        scopes: list = None
    ) -> tuple[str, str]:
        """Generate a new API key
        
        Args:
            user_id: User identifier
            name: Key name/description
            scopes: List of scopes/permissions
            
        Returns:
            tuple: (api_key, key_id)
        """
        # Generate random key
        key_suffix = secrets.token_urlsafe(32)
        api_key = f"{self.key_prefix}{key_suffix}"
        key_id = secrets.token_hex(8)
        
        # Store key information
        self.api_keys[key_id] = {
            "key_id": key_id,
            "api_key": api_key,
            "user_id": user_id,
            "name": name,
            "scopes": scopes or [],
            "created_at": time.time(),
            "last_used": None,
            "is_active": True
        }
        
        return (api_key, key_id)
    
    def verify_api_key(
        self,
        api_key: str,
        required_scope: Optional[str] = None
    ) -> Optional[dict]:
        """Verify API key
        
        Args:
            api_key: API key to verify
            required_scope: Required scope/permission
            
        Returns:
            dict: Key information or None if invalid
        """
        # Find key
        key_info = None
        for key_id, info in self.api_keys.items():
            if info.get("api_key") == api_key:
                key_info = info
                break
        
        if not key_info:
            return None
        
        # Check if active
        if not key_info.get("is_active"):
            return None
        
        # Check scope
        if required_scope:
            if required_scope not in key_info.get("scopes", []):
                return None
        
        # Update last used
        key_info["last_used"] = time.time()
        
        return key_info
    
    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke API key
        
        Args:
            key_id: Key identifier
            
        Returns:
            bool: True if key was revoked
        """
        if key_id in self.api_keys:
            self.api_keys[key_id]["is_active"] = False
            return True
        return False
    
    def get_user_api_keys(self, user_id: str) -> list:
        """Get all API keys for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            list: List of API keys
        """
        keys = []
        for key_id, info in self.api_keys.items():
            if info.get("user_id") == user_id:
                keys.append({
                    "key_id": key_id,
                    "name": info.get("name"),
                    "scopes": info.get("scopes"),
                    "created_at": info.get("created_at"),
                    "last_used": info.get("last_used"),
                    "is_active": info.get("is_active")
                })
        
        return keys
    
    def cleanup_inactive_keys(self, days: int = 90):
        """Remove inactive keys older than specified days
        
        Args:
            days: Number of days
        """
        cutoff_time = time.time() - (days * 86400)
        keys_to_remove = []
        
        for key_id, info in self.api_keys.items():
            if (
                not info.get("is_active")
                and info.get("created_at", 0) < cutoff_time
            ):
                keys_to_remove.append(key_id)
        
        for key_id in keys_to_remove:
            del self.api_keys[key_id]


class IPWhitelist:
    """IP whitelist/blacklist management"""
    
    def __init__(self):
        self.whitelist: set = set()
        self.blacklist: set = set()
    
    def add_to_whitelist(self, ip: str):
        """Add IP to whitelist
        
        Args:
            ip: IP address
        """
        self.whitelist.add(ip)
    
    def remove_from_whitelist(self, ip: str):
        """Remove IP from whitelist
        
        Args:
            ip: IP address
        """
        if ip in self.whitelist:
            self.whitelist.remove(ip)
    
    def add_to_blacklist(self, ip: str):
        """Add IP to blacklist
        
        Args:
            ip: IP address
        """
        self.blacklist.add(ip)
    
    def remove_from_blacklist(self, ip: str):
        """Remove IP from blacklist
        
        Args:
            ip: IP address
        """
        if ip in self.blacklist:
            self.blacklist.remove(ip)
    
    def is_allowed(self, ip: str) -> tuple[bool, str]:
        """Check if IP is allowed
        
        Args:
            ip: IP address
            
        Returns:
            tuple: (is_allowed, reason)
        """
        # Check blacklist first
        if ip in self.blacklist:
            return (False, "IP is blacklisted")
        
        # If whitelist is not empty, check whitelist
        if self.whitelist and ip not in self.whitelist:
            return (False, "IP is not whitelisted")
        
        return (True, "OK")
    
    def get_whitelist(self) -> list:
        """Get whitelist
        
        Returns:
            list: List of whitelisted IPs
        """
        return list(self.whitelist)
    
    def get_blacklist(self) -> list:
        """Get blacklist
        
        Returns:
            list: List of blacklisted IPs
        """
        return list(self.blacklist)


class RequestSigning:
    """Request signing for API security"""
    
    def __init__(self):
        pass
    
    def sign_request(
        self,
        method: str,
        path: str,
        body: str,
        api_key: str,
        secret: str,
        timestamp: int
    ) -> str:
        """Sign a request
        
        Args:
            method: HTTP method
            path: Request path
            body: Request body
            api_key: API key
            secret: API secret
            timestamp: Request timestamp
            
        Returns:
            str: Signature
        """
        import hmac
        import hashlib
        
        # Create message to sign
        message = f"{method}\n{path}\n{body}\n{api_key}\n{timestamp}"
        
        # Sign with HMAC-SHA256
        signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def verify_signature(
        self,
        method: str,
        path: str,
        body: str,
        api_key: str,
        secret: str,
        timestamp: int,
        signature: str
    ) -> bool:
        """Verify request signature
        
        Args:
            method: HTTP method
            path: Request path
            body: Request body
            api_key: API key
            secret: API secret
            timestamp: Request timestamp
            signature: Signature to verify
            
        Returns:
            bool: True if signature is valid
        """
        # Check timestamp (prevent replay attacks)
        current_time = time.time()
        if abs(current_time - timestamp) > 300:  # 5 minutes
            return False
        
        # Generate expected signature
        expected_signature = self.sign_request(
            method, path, body, api_key, secret, timestamp
        )
        
        # Use constant-time comparison
        import secrets
        return secrets.compare_digest(expected_signature, signature)


# Global instances
api_key_manager = APIKeyManager()
ip_whitelist = IPWhitelist()
request_signing = RequestSigning()


def generate_api_key(
    user_id: str,
    name: str,
    scopes: list = None
) -> tuple[str, str]:
    """Generate a new API key
    
    Args:
        user_id: User identifier
        name: Key name/description
        scopes: List of scopes/permissions
        
    Returns:
        tuple: (api_key, key_id)
    """
    return api_key_manager.generate_api_key(user_id, name, scopes)


def verify_api_key(
    api_key: str,
    required_scope: Optional[str] = None
) -> Optional[dict]:
    """Verify API key
    
    Args:
        api_key: API key to verify
        required_scope: Required scope/permission
        
    Returns:
        dict: Key information or None if invalid
    """
    return api_key_manager.verify_api_key(api_key, required_scope)


def revoke_api_key(key_id: str) -> bool:
    """Revoke API key
    
    Args:
        key_id: Key identifier
        
    Returns:
        bool: True if key was revoked
    """
    return api_key_manager.revoke_api_key(key_id)


def get_user_api_keys(user_id: str) -> list:
    """Get all API keys for a user
    
    Args:
        user_id: User identifier
        
    Returns:
        list: List of API keys
    """
    return api_key_manager.get_user_api_keys(user_id)


def is_ip_allowed(ip: str) -> tuple[bool, str]:
    """Check if IP is allowed
    
    Args:
        ip: IP address
        
    Returns:
        tuple: (is_allowed, reason)
    """
    return ip_whitelist.is_allowed(ip)


def add_ip_to_whitelist(ip: str):
    """Add IP to whitelist
    
    Args:
        ip: IP address
    """
    ip_whitelist.add_to_whitelist(ip)


def remove_ip_from_whitelist(ip: str):
    """Remove IP from whitelist
    
    Args:
        ip: IP address
    """
    ip_whitelist.remove_from_whitelist(ip)


def add_ip_to_blacklist(ip: str):
    """Add IP to blacklist
    
    Args:
        ip: IP address
    """
    ip_whitelist.add_to_blacklist(ip)


def remove_ip_from_blacklist(ip: str):
    """Remove IP from blacklist
    
    Args:
        ip: IP address
    """
    ip_whitelist.remove_from_blacklist(ip)
