"""
Audit logging service for tracking user actions.

Usage:
    from app.audit import audit_log, AuditStatus

    # In an endpoint with Request access:
    await audit_log(
        db=db,
        request=request,
        action="auth.login",
        user_id=user.id,
        status=AuditStatus.SUCCESS,
        metadata={"method": "email"}
    )

    # Without request (background tasks):
    await audit_log(
        db=db,
        action="system.cleanup",
        metadata={"deleted_sessions": 5}
    )
"""

from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request
import logging

from .models import ActivityLog, AuditStatus

logger = logging.getLogger(__name__)


class AuditService:
    """Service for creating and querying audit logs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        action: str,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: AuditStatus = AuditStatus.SUCCESS,
    ) -> ActivityLog:
        """
        Create an audit log entry.

        Args:
            action: Action identifier (e.g., 'auth.login', 'project.create')
            user_id: User who performed the action (None for system/anonymous)
            resource_type: Type of resource affected (e.g., 'user', 'project')
            resource_id: ID of the affected resource
            metadata: Additional context as JSON
            ip_address: Client IP address
            user_agent: Client user agent string
            status: Result status (success/failed/denied)

        Returns:
            Created ActivityLog instance
        """
        log_entry = ActivityLog(
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=metadata,  # 'details' maps to 'metadata' column
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
        )

        self.db.add(log_entry)
        # Don't commit here - let the caller handle transaction
        await self.db.flush()

        logger.debug(
            f"Audit log: {action} by user={user_id} status={status.value} "
            f"resource={resource_type}:{resource_id}"
        )

        return log_entry

    async def log_from_request(
        self,
        request: Request,
        action: str,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: AuditStatus = AuditStatus.SUCCESS,
    ) -> ActivityLog:
        """
        Create an audit log entry with IP and user agent from request.

        Args:
            request: FastAPI Request object
            action: Action identifier
            user_id: User who performed the action
            resource_type: Type of resource affected
            resource_id: ID of the affected resource
            metadata: Additional context
            status: Result status

        Returns:
            Created ActivityLog instance
        """
        # Extract client IP (handle proxies)
        ip_address = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")[:500]  # Truncate if too long

        return await self.log(
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
        )

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address, handling reverse proxies."""
        # Check X-Forwarded-For header (set by nginx/proxy)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take the first IP (original client)
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP header (alternative proxy header)
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"


# Convenience function for simpler usage
async def audit_log(
    db: AsyncSession,
    action: str,
    request: Optional[Request] = None,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    status: AuditStatus = AuditStatus.SUCCESS,
) -> ActivityLog:
    """
    Convenience function to create an audit log entry.

    Args:
        db: Database session
        action: Action identifier (e.g., 'auth.login', 'project.create')
        request: Optional FastAPI Request (to extract IP and user agent)
        user_id: User who performed the action
        resource_type: Type of resource affected
        resource_id: ID of the affected resource
        metadata: Additional context
        status: Result status

    Returns:
        Created ActivityLog instance
    """
    service = AuditService(db)

    if request:
        return await service.log_from_request(
            request=request,
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata,
            status=status,
        )
    else:
        return await service.log(
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata,
            status=status,
        )
