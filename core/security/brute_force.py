"""
Brute Force Protection
"""

import time
from typing import Dict, Optional
from collections import defaultdict
from fastapi import HTTPException, status


class BruteForceProtection:
    """Brute force protection for authentication"""
    
    def __init__(self):
        self.attempts: Dict[str, list] = defaultdict(list)
        self.lockouts: Dict[str, float] = {}
        self.max_attempts = 5
        self.lockout_duration = 300  # 5 minutes
        self.increase_lockout = True  # Increase lockout time on repeated failures
    
    def record_attempt(self, identifier: str):
        """Record a failed authentication attempt
        
        Args:
            identifier: Unique identifier (email, IP, etc.)
        """
        now = time.time()
        
        # Remove attempts older than 1 hour
        self.attempts[identifier] = [
            timestamp for timestamp in self.attempts[identifier]
            if now - timestamp < 3600
        ]
        
        # Add current attempt
        self.attempts[identifier].append(now)
    
    def is_locked(self, identifier: str) -> tuple[bool, Optional[int]]:
        """Check if identifier is locked out
        
        Args:
            identifier: Unique identifier
            
        Returns:
            tuple: (is_locked, remaining_seconds)
        """
        # Check if currently locked
        if identifier in self.lockouts:
            if time.time() < self.lockouts[identifier]:
                remaining = int(self.lockouts[identifier] - time.time())
                return (True, remaining)
            else:
                # Lockout expired
                del self.lockouts[identifier]
        
        return (False, None)
    
    def should_block(self, identifier: str) -> tuple[bool, Optional[int]]:
        """Check if identifier should be blocked
        
        Args:
            identifier: Unique identifier
            
        Returns:
            tuple: (should_block, remaining_seconds)
        """
        # Check if locked
        is_locked, remaining = self.is_locked(identifier)
        if is_locked:
            return (True, remaining)
        
        # Check attempt count
        recent_attempts = len(self.attempts[identifier])
        
        if recent_attempts >= self.max_attempts:
            # Lock out
            lockout_time = time.time() + self.lockout_duration
            
            # Increase lockout time on repeated failures
            if self.increase_lockout and identifier in self.lockouts:
                lockout_time += 300  # Add 5 minutes
            
            self.lockouts[identifier] = lockout_time
            remaining = int(lockout_time - time.time())
            
            # Clear attempts
            self.attempts[identifier] = []
            
            return (True, remaining)
        
        return (False, None)
    
    def reset_attempts(self, identifier: str):
        """Reset attempts for successful authentication
        
        Args:
            identifier: Unique identifier
        """
        if identifier in self.attempts:
            del self.attempts[identifier]
        
        if identifier in self.lockouts:
            del self.lockouts[identifier]
    
    def get_remaining_attempts(self, identifier: str) -> int:
        """Get remaining attempts before lockout
        
        Args:
            identifier: Unique identifier
            
        Returns:
            int: Remaining attempts
        """
        return max(0, self.max_attempts - len(self.attempts[identifier]))


# Global brute force protection instance
brute_force_protection = BruteForceProtection()


def check_brute_force(identifier: str):
    """Check if identifier should be blocked due to brute force
    
    Args:
        identifier: Unique identifier
        
    Raises:
        HTTPException: If identifier is locked
    """
    should_block, remaining = brute_force_protection.should_block(identifier)
    
    if should_block:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "too_many_attempts",
                "message": "Too many failed attempts. Please try again later.",
                "retry_after": remaining
            },
            headers={
                "Retry-After": str(remaining)
            }
        )


def record_failed_attempt(identifier: str):
    """Record a failed authentication attempt
    
    Args:
        identifier: Unique identifier
    """
    brute_force_protection.record_attempt(identifier)


def reset_failed_attempts(identifier: str):
    """Reset failed attempts after successful authentication
    
    Args:
        identifier: Unique identifier
    """
    brute_force_protection.reset_attempts(identifier)


def get_remaining_attempts(identifier: str) -> int:
    """Get remaining attempts before lockout
    
    Args:
        identifier: Unique identifier
        
    Returns:
        int: Remaining attempts
    """
    return brute_force_protection.get_remaining_attempts(identifier)
