"""
Session Management
"""

import time
from typing import Dict, Optional
from fastapi import HTTPException, status


class SessionManager:
    """Session management for JWT tokens"""
    
    def __init__(self):
        self.active_sessions: Dict[str, dict] = {}
        self.blacklisted_tokens: Dict[str, float] = {}
        self.session_timeout = 3600  # 1 hour
        self.refresh_token_rotation = True
    
    def create_session(
        self,
        user_id: str,
        token: str,
        refresh_token: str,
        ip_address: str,
        user_agent: str
    ) -> dict:
        """Create a new session
        
        Args:
            user_id: User identifier
            token: Access token
            refresh_token: Refresh token
            ip_address: Client IP address
            user_agent: Client user agent
            
        Returns:
            dict: Session information
        """
        session = {
            "user_id": user_id,
            "token": token,
            "refresh_token": refresh_token,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": time.time(),
            "last_activity": time.time(),
            "expires_at": time.time() + self.session_timeout
        }
        
        self.active_sessions[token] = session
        return session
    
    def get_session(self, token: str) -> Optional[dict]:
        """Get session by token
        
        Args:
            token: Access token
            
        Returns:
            dict: Session information or None
        """
        # Check if token is blacklisted
        if token in self.blacklisted_tokens:
            return None
        
        # Get session
        session = self.active_sessions.get(token)
        if not session:
            return None
        
        # Check if session is expired
        if time.time() > session["expires_at"]:
            del self.active_sessions[token]
            return None
        
        # Update last activity
        session["last_activity"] = time.time()
        
        return session
    
    def revoke_session(self, token: str) -> bool:
        """Revoke a session
        
        Args:
            token: Access token
            
        Returns:
            bool: True if session was revoked
        """
        if token in self.active_sessions:
            del self.active_sessions[token]
            return True
        return False
    
    def revoke_all_sessions(self, user_id: str) -> int:
        """Revoke all sessions for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            int: Number of sessions revoked
        """
        count = 0
        tokens_to_remove = []
        
        for token, session in self.active_sessions.items():
            if session.get("user_id") == user_id:
                tokens_to_remove.append(token)
        
        for token in tokens_to_remove:
            self.revoke_session(token)
            count += 1
        
        return count
    
    def blacklist_token(self, token: str) -> bool:
        """Add token to blacklist
        
        Args:
            token: Token to blacklist
            
        Returns:
            bool: True if token was blacklisted
        """
        if token in self.blacklisted_tokens:
            return False
        
        self.blacklisted_tokens[token] = time.time()
        return True
    
    def is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted
        
        Args:
            token: Token to check
            
        Returns:
            bool: True if token is blacklisted
        """
        return token in self.blacklisted_tokens
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        now = time.time()
        expired_tokens = []
        
        for token, session in self.active_sessions.items():
            if now > session.get("expires_at", 0):
                expired_tokens.append(token)
        
        for token in expired_tokens:
            del self.active_sessions[token]
        
        # Clean up old blacklisted tokens (older than 24 hours)
        old_blacklisted_tokens = []
        for token, timestamp in self.blacklisted_tokens.items():
            if now - timestamp > 86400:
                old_blacklisted_tokens.append(token)
        
        for token in old_blacklisted_tokens:
            del self.blacklisted_tokens[token]
    
    def get_active_sessions(self, user_id: str) -> list:
        """Get all active sessions for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            list: List of active sessions
        """
        sessions = []
        
        for session in self.active_sessions.values():
            if session.get("user_id") == user_id:
                sessions.append(session)
        
        return sessions
    
    def rotate_refresh_token(
        self,
        old_refresh_token: str,
        new_refresh_token: str
    ) -> bool:
        """Rotate refresh token
        
        Args:
            old_refresh_token: Old refresh token
            new_refresh_token: New refresh token
            
        Returns:
            bool: True if rotation was successful
        """
        for session in self.active_sessions.values():
            if session.get("refresh_token") == old_refresh_token:
                session["refresh_token"] = new_refresh_token
                return True
        
        return False


# Global session manager instance
session_manager = SessionManager()


def create_session(
    user_id: str,
    token: str,
    refresh_token: str,
    ip_address: str,
    user_agent: str
) -> dict:
    """Create a new session
    
    Args:
        user_id: User identifier
        token: Access token
        refresh_token: Refresh token
        ip_address: Client IP address
        user_agent: Client user agent
        
    Returns:
        dict: Session information
    """
    return session_manager.create_session(
        user_id, token, refresh_token, ip_address, user_agent
    )


def get_session(token: str) -> Optional[dict]:
    """Get session by token
    
    Args:
        token: Access token
        
    Returns:
        dict: Session information or None
    """
    return session_manager.get_session(token)


def revoke_session(token: str) -> bool:
    """Revoke a session
    
    Args:
        token: Access token
        
    Returns:
        bool: True if session was revoked
    """
    return session_manager.revoke_session(token)


def revoke_all_sessions(user_id: str) -> int:
    """Revoke all sessions for a user
    
    Args:
        user_id: User identifier
        
    Returns:
        int: Number of sessions revoked
    """
    return session_manager.revoke_all_sessions(user_id)


def blacklist_token(token: str) -> bool:
    """Add token to blacklist
    
    Args:
        token: Token to blacklist
        
    Returns:
        bool: True if token was blacklisted
    """
    return session_manager.blacklist_token(token)


def is_token_blacklisted(token: str) -> bool:
    """Check if token is blacklisted
    
    Args:
        token: Token to check
        
    Returns:
        bool: True if token is blacklisted
    """
    return session_manager.is_token_blacklisted(token)


def get_active_sessions(user_id: str) -> list:
    """Get all active sessions for a user
    
    Args:
        user_id: User identifier
        
    Returns:
        list: List of active sessions
    """
    return session_manager.get_active_sessions(user_id)
