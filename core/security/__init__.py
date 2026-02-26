"""
Security modules
"""

# Import authentication functions from core.security.auth module
from .auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    maybe_upgrade_password_hash,
    get_current_user,
    get_current_active_user,
    get_current_superuser,
    verify_token_type
)

from .password_policy import (
    PasswordPolicy,
    password_policy,
    validate_password,
    get_password_suggestions,
    check_password_strength
)

from .brute_force import (
    BruteForceProtection,
    brute_force_protection,
    check_brute_force,
    record_failed_attempt,
    reset_failed_attempts,
    get_remaining_attempts
)

from .two_factor import (
    TwoFactorAuth,
    two_factor_auth,
    generate_2fa_secret,
    generate_qr_code_uri,
    verify_totp_code,
    generate_backup_codes,
    verify_backup_code,
    get_remaining_backup_codes
)

from .session import (
    SessionManager,
    session_manager,
    create_session,
    get_session,
    revoke_session,
    revoke_all_sessions,
    blacklist_token,
    is_token_blacklisted,
    get_active_sessions
)

from .audit import (
    AuditLogger,
    AuditEventType,
    audit_logger,
    log_event,
    get_events,
    get_security_events,
    get_statistics
)

from .api_security import (
    APIKeyManager,
    IPWhitelist,
    RequestSigning,
    api_key_manager,
    ip_whitelist,
    request_signing,
    generate_api_key,
    verify_api_key,
    revoke_api_key,
    get_user_api_keys,
    is_ip_allowed,
    add_ip_to_whitelist,
    remove_ip_from_whitelist,
    add_ip_to_blacklist,
    remove_ip_from_blacklist
)

__all__ = [
    # Authentication
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "maybe_upgrade_password_hash",
    "get_current_user",
    "get_current_active_user",
    "get_current_superuser",
    "verify_token_type",
    
    # Password Policy
    "PasswordPolicy",
    "password_policy",
    "validate_password",
    "get_password_suggestions",
    "check_password_strength",
    
    # Brute Force Protection
    "BruteForceProtection",
    "brute_force_protection",
    "check_brute_force",
    "record_failed_attempt",
    "reset_failed_attempts",
    "get_remaining_attempts",
    
    # Two-Factor Authentication
    "TwoFactorAuth",
    "two_factor_auth",
    "generate_2fa_secret",
    "generate_qr_code_uri",
    "verify_totp_code",
    "generate_backup_codes",
    "verify_backup_code",
    "get_remaining_backup_codes",
    
    # Session Management
    "SessionManager",
    "session_manager",
    "create_session",
    "get_session",
    "revoke_session",
    "revoke_all_sessions",
    "blacklist_token",
    "is_token_blacklisted",
    "get_active_sessions",
    
    # Audit Logging
    "AuditLogger",
    "AuditEventType",
    "audit_logger",
    "log_event",
    "get_events",
    "get_security_events",
    "get_statistics",
    
    # API Security
    "APIKeyManager",
    "IPWhitelist",
    "RequestSigning",
    "api_key_manager",
    "ip_whitelist",
    "request_signing",
    "generate_api_key",
    "verify_api_key",
    "revoke_api_key",
    "get_user_api_keys",
    "is_ip_allowed",
    "add_ip_to_whitelist",
    "remove_ip_from_whitelist",
    "add_ip_to_blacklist",
    "remove_ip_from_blacklist"
]
