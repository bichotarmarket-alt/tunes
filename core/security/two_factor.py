"""
Two-Factor Authentication (2FA)
"""

import secrets
import time
from typing import Optional, Dict
from fastapi import HTTPException, status
import pyotp


class TwoFactorAuth:
    """Two-factor authentication using TOTP"""
    
    def __init__(self):
        self.backup_codes: Dict[str, list] = {}
        self.last_used_codes: Dict[str, float] = {}
    
    def generate_secret(self) -> str:
        """Generate a new TOTP secret
        
        Returns:
            str: Base32 encoded secret
        """
        return secrets.token_urlsafe(32)
    
    def generate_qr_code_uri(
        self,
        secret: str,
        email: str,
        issuer: str = "AutoTrade"
    ) -> str:
        """Generate QR code URI for TOTP
        
        Args:
            secret: TOTP secret
            email: User email
            issuer: Application name
            
        Returns:
            str: QR code URI
        """
        return pyotp.totp.TOTP(secret).provisioning_uri(
            name=email,
            issuer_name=issuer
        )
    
    def verify_totp(
        self,
        secret: str,
        code: str,
        window: int = 1
    ) -> bool:
        """Verify TOTP code
        
        Args:
            secret: TOTP secret
            code: 6-digit TOTP code
            window: Time window for code validity
            
        Returns:
            bool: True if code is valid
        """
        totp = pyotp.TOTP(secret)
        
        # Check current code and adjacent codes
        for offset in range(-window, window + 1):
            if totp.verify(code, valid_window=offset):
                return True
        
        return False
    
    def generate_backup_codes(
        self,
        user_id: str,
        count: int = 10
    ) -> list:
        """Generate backup codes for 2FA
        
        Args:
            user_id: User identifier
            count: Number of backup codes to generate
            
        Returns:
            list: List of backup codes
        """
        codes = []
        for _ in range(count):
            code = secrets.token_hex(4)
            codes.append(code)
        
        self.backup_codes[user_id] = codes
        return codes
    
    def verify_backup_code(
        self,
        user_id: str,
        code: str
    ) -> bool:
        """Verify and consume backup code
        
        Args:
            user_id: User identifier
            code: Backup code
            
        Returns:
            bool: True if code is valid
        """
        if user_id not in self.backup_codes:
            return False
        
        if code in self.backup_codes[user_id]:
            # Remove used code
            self.backup_codes[user_id].remove(code)
            return True
        
        return False
    
    def get_remaining_backup_codes(self, user_id: str) -> int:
        """Get remaining backup codes
        
        Args:
            user_id: User identifier
            
        Returns:
            int: Number of remaining backup codes
        """
        return len(self.backup_codes.get(user_id, []))
    
    def enable_2fa(self, user_id: str, secret: str):
        """Enable 2FA for user
        
        Args:
            user_id: User identifier
            secret: TOTP secret
        """
        # In a real implementation, this would be stored in the database
        pass
    
    def disable_2fa(self, user_id: str):
        """Disable 2FA for user
        
        Args:
            user_id: User identifier
        """
        # In a real implementation, this would be removed from the database
        if user_id in self.backup_codes:
            del self.backup_codes[user_id]


# Global 2FA instance
two_factor_auth = TwoFactorAuth()


def generate_2fa_secret() -> str:
    """Generate a new TOTP secret
    
    Returns:
        str: Base32 encoded secret
    """
    return two_factor_auth.generate_secret()


def generate_qr_code_uri(
    secret: str,
    email: str,
    issuer: str = "AutoTrade"
) -> str:
    """Generate QR code URI for TOTP
    
    Args:
        secret: TOTP secret
        email: User email
        issuer: Application name
        
    Returns:
        str: QR code URI
    """
    return two_factor_auth.generate_qr_code_uri(secret, email, issuer)


def verify_totp_code(
    secret: str,
    code: str,
    window: int = 1
) -> bool:
    """Verify TOTP code
    
    Args:
        secret: TOTP secret
        code: 6-digit TOTP code
        window: Time window for code validity
        
    Returns:
        bool: True if code is valid
    """
    return two_factor_auth.verify_totp(secret, code, window)


def generate_backup_codes(
    user_id: str,
    count: int = 10
) -> list:
    """Generate backup codes for 2FA
    
    Args:
        user_id: User identifier
        count: Number of backup codes to generate
        
    Returns:
        list: List of backup codes
    """
    return two_factor_auth.generate_backup_codes(user_id, count)


def verify_backup_code(
    user_id: str,
    code: str
) -> bool:
    """Verify and consume backup code
    
    Args:
        user_id: User identifier
        code: Backup code
        
    Returns:
        bool: True if code is valid
    """
    return two_factor_auth.verify_backup_code(user_id, code)


def get_remaining_backup_codes(user_id: str) -> int:
    """Get remaining backup codes
    
    Args:
        user_id: User identifier
        
    Returns:
        int: Number of remaining backup codes
    """
    return two_factor_auth.get_remaining_backup_codes(user_id)
