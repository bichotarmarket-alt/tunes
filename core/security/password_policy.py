"""
Password Policies
"""

import re
from typing import List, Optional
from fastapi import HTTPException, status


class PasswordPolicy:
    """Password policy validator"""
    
    def __init__(self):
        self.min_length = 12
        self.max_length = 128
        self.require_uppercase = True
        self.require_lowercase = True
        self.require_numbers = True
        self.require_special_chars = True
        self.special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        self.forbidden_patterns = [
            r"password",  # Palavra "password"
            r"123456",     # Sequências comuns
            r"qwerty",     # Padrões de teclado
            r"admin",     # Palavras comuns
        ]
        self.forbidden_common_passwords = [
            "password", "123456", "12345678", "qwerty", "abc123",
            "password123", "admin123", "letmein", "welcome", "monkey"
        ]
    
    def validate_password(
        self,
        password: str,
        check_common: bool = True
    ) -> tuple[bool, List[str]]:
        """Validate password against policy
        
        Args:
            password: Password to validate
            check_common: Check against common passwords
            
        Returns:
            tuple: (is_valid, list of errors)
        """
        errors = []
        
        # Check length
        if len(password) < self.min_length:
            errors.append(f"Password must be at least {self.min_length} characters")
        
        if len(password) > self.max_length:
            errors.append(f"Password must not exceed {self.max_length} characters")
        
        # Check uppercase
        if self.require_uppercase and not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter")
        
        # Check lowercase
        if self.require_lowercase and not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter")
        
        # Check numbers
        if self.require_numbers and not re.search(r"\d", password):
            errors.append("Password must contain at least one number")
        
        # Check special characters
        if self.require_special_chars:
            has_special = any(char in password for char in self.special_chars)
            if not has_special:
                errors.append(f"Password must contain at least one special character ({self.special_chars})")
        
        # Check forbidden patterns
        for pattern in self.forbidden_patterns:
            if re.search(pattern, password, re.IGNORECASE):
                errors.append(f"Password contains forbidden pattern: {pattern}")
        
        # Check common passwords
        if check_common:
            if password.lower() in [p.lower() for p in self.forbidden_common_passwords]:
                errors.append("Password is too common")
        
        return (len(errors) == 0, errors)
    
    def generate_password_suggestions(self) -> List[str]:
        """Generate password suggestions
        
        Returns:
            list: List of password suggestions
        """
        import secrets
        import string
        
        suggestions = []
        
        for _ in range(3):
            # Generate random password with required characters
            chars = string.ascii_letters + string.digits + "!@#$%^&*"
            password = ''.join(secrets.choice(chars) for _ in range(self.min_length))
            
            # Ensure it has all required characters
            if not re.search(r"[A-Z]", password):
                password = password[:-1] + secrets.choice(string.ascii_uppercase)
            
            if not re.search(r"[a-z]", password):
                password = password[:-1] + secrets.choice(string.ascii_lowercase)
            
            if not re.search(r"\d", password):
                password = password[:-1] + secrets.choice(string.digits)
            
            if not any(char in password for char in self.special_chars):
                password = password[:-1] + secrets.choice("!@#$%^&*")
            
            suggestions.append(password)
        
        return suggestions


# Global password policy instance
password_policy = PasswordPolicy()


def validate_password(
    password: str,
    check_common: bool = True
) -> tuple[bool, List[str]]:
    """Validate password against policy
    
    Args:
        password: Password to validate
        check_common: Check against common passwords
        
    Returns:
        tuple: (is_valid, list of errors)
    """
    return password_policy.validate_password(password, check_common)


def get_password_suggestions() -> List[str]:
    """Get password suggestions
    
    Returns:
        list: List of password suggestions
    """
    return password_policy.generate_password_suggestions()


def check_password_strength(password: str) -> dict:
    """Check password strength
    
    Args:
        password: Password to check
        
    Returns:
        dict: Password strength information
    """
    strength = 0
    feedback = []
    
    # Length
    if len(password) >= 8:
        strength += 1
    if len(password) >= 12:
        strength += 1
    if len(password) >= 16:
        strength += 1
    
    # Complexity
    if re.search(r"[A-Z]", password):
        strength += 1
        feedback.append("Has uppercase letters")
    
    if re.search(r"[a-z]", password):
        strength += 1
        feedback.append("Has lowercase letters")
    
    if re.search(r"\d", password):
        strength += 1
        feedback.append("Has numbers")
    
    if re.search(r"[!@#$%^&*]", password):
        strength += 1
        feedback.append("Has special characters")
    
    # Strength rating
    if strength <= 2:
        rating = "Weak"
    elif strength <= 4:
        rating = "Medium"
    elif strength <= 6:
        rating = "Strong"
    else:
        rating = "Very Strong"
    
    return {
        "strength": strength,
        "rating": rating,
        "feedback": feedback,
        "max_strength": 7
    }
