"""
Audit Logging
"""

import time
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
import json


class AuditEventType(Enum):
    """Audit event types"""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET = "password_reset"
    ACCOUNT_CREATED = "account_created"
    ACCOUNT_DELETED = "account_deleted"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    TWO_FA_ENABLED = "2fa_enabled"
    TWO_FA_DISABLED = "2fa_disabled"
    TRADE_EXECUTED = "trade_executed"
    TRADE_FAILED = "trade_failed"
    STRATEGY_CREATED = "strategy_created"
    STRATEGY_UPDATED = "strategy_updated"
    STRATEGY_DELETED = "strategy_deleted"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    DATA_EXPORTED = "data_exported"
    DATA_IMPORTED = "data_imported"
    SETTINGS_CHANGED = "settings_changed"
    API_KEY_CREATED = "api_key_created"
    API_KEY_DELETED = "api_key_deleted"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"


class AuditLogger:
    """Audit logging for security events"""
    
    def __init__(self):
        self.events: List[dict] = []
        self.max_events = 10000  # Keep last 10000 events
    
    def log_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[dict] = None,
        severity: str = "INFO"
    ) -> dict:
        """Log an audit event
        
        Args:
            event_type: Type of event
            user_id: User identifier
            ip_address: Client IP address
            user_agent: Client user agent
            details: Additional event details
            severity: Event severity (INFO, WARNING, ERROR, CRITICAL)
            
        Returns:
            dict: Event information
        """
        event = {
            "id": len(self.events) + 1,
            "event_type": event_type.value,
            "user_id": user_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "details": details or {},
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat(),
            "unix_timestamp": time.time()
        }
        
        self.events.append(event)
        
        # Keep only last N events
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
        
        return event
    
    def get_events(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100
    ) -> List[dict]:
        """Get audit events
        
        Args:
            user_id: Filter by user
            event_type: Filter by event type
            severity: Filter by severity
            limit: Maximum number of events to return
            
        Returns:
            list: List of events
        """
        events = self.events
        
        # Apply filters
        if user_id:
            events = [e for e in events if e.get("user_id") == user_id]
        
        if event_type:
            events = [e for e in events if e.get("event_type") == event_type]
        
        if severity:
            events = [e for e in events if e.get("severity") == severity]
        
        # Sort by timestamp (newest first)
        events = sorted(events, key=lambda x: x.get("unix_timestamp", 0), reverse=True)
        
        # Limit results
        return events[:limit]
    
    def get_recent_events(
        self,
        hours: int = 24,
        severity: Optional[str] = None
    ) -> List[dict]:
        """Get recent events
        
        Args:
            hours: Number of hours to look back
            severity: Filter by severity
            
        Returns:
            list: List of recent events
        """
        cutoff_time = time.time() - (hours * 3600)
        events = [
            e for e in self.events
            if e.get("unix_timestamp", 0) > cutoff_time
        ]
        
        if severity:
            events = [e for e in events if e.get("severity") == severity]
        
        return sorted(events, key=lambda x: x.get("unix_timestamp", 0), reverse=True)
    
    def get_security_events(self, hours: int = 24) -> List[dict]:
        """Get security-related events
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            list: List of security events
        """
        security_types = [
            "login_failed",
            "account_locked",
            "suspicious_activity",
            "password_change",
            "2fa_disabled"
        ]
        
        cutoff_time = time.time() - (hours * 3600)
        events = [
            e for e in self.events
            if e.get("unix_timestamp", 0) > cutoff_time
            and e.get("event_type") in security_types
        ]
        
        return sorted(events, key=lambda x: x.get("unix_timestamp", 0), reverse=True)
    
    def export_events(
        self,
        format: str = "json",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> str:
        """Export audit events
        
        Args:
            format: Export format (json, csv)
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            
        Returns:
            str: Exported data
        """
        events = self.events
        
        # Filter by date range
        if start_date:
            start_timestamp = datetime.fromisoformat(start_date).timestamp()
            events = [e for e in events if e.get("unix_timestamp", 0) >= start_timestamp]
        
        if end_date:
            end_timestamp = datetime.fromisoformat(end_date).timestamp()
            events = [e for e in events if e.get("unix_timestamp", 0) <= end_timestamp]
        
        if format == "json":
            return json.dumps(events, indent=2)
        elif format == "csv":
            # Simple CSV export
            headers = ["id", "event_type", "user_id", "timestamp", "severity"]
            rows = []
            rows.append(",".join(headers))
            
            for event in events:
                row = [
                    str(event.get("id", "")),
                    event.get("event_type", ""),
                    event.get("user_id", ""),
                    event.get("timestamp", ""),
                    event.get("severity", "")
                ]
                rows.append(",".join(row))
            
            return "\n".join(rows)
        
        return ""
    
    def get_statistics(self) -> dict:
        """Get audit statistics
        
        Returns:
            dict: Statistics
        """
        event_counts = {}
        severity_counts = {}
        user_counts = {}
        
        for event in self.events:
            # Count by event type
            event_type = event.get("event_type", "unknown")
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
            # Count by severity
            severity = event.get("severity", "INFO")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # Count by user
            user_id = event.get("user_id", "unknown")
            user_counts[user_id] = user_counts.get(user_id, 0) + 1
        
        return {
            "total_events": len(self.events),
            "event_counts": event_counts,
            "severity_counts": severity_counts,
            "top_users": dict(sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        }


# Global audit logger instance
audit_logger = AuditLogger()


def log_event(
    event_type: AuditEventType,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[dict] = None,
    severity: str = "INFO"
) -> dict:
    """Log an audit event
    
    Args:
        event_type: Type of event
        user_id: User identifier
        ip_address: Client IP address
        user_agent: Client user agent
        details: Additional event details
        severity: Event severity
        
    Returns:
        dict: Event information
    """
    return audit_logger.log_event(
        event_type, user_id, ip_address, user_agent, details, severity
    )


def get_events(
    user_id: Optional[str] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100
) -> List[dict]:
    """Get audit events
    
    Args:
        user_id: Filter by user
        event_type: Filter by event type
        severity: Filter by severity
        limit: Maximum number of events to return
        
    Returns:
        list: List of events
    """
    return audit_logger.get_events(user_id, event_type, severity, limit)


def get_security_events(hours: int = 24) -> List[dict]:
    """Get security-related events
    
    Args:
        hours: Number of hours to look back
        
    Returns:
        list: List of security events
    """
    return audit_logger.get_security_events(hours)


def get_statistics() -> dict:
    """Get audit statistics
    
    Returns:
        dict: Statistics
    """
    return audit_logger.get_statistics()
