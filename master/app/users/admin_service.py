"""
Admin user management service.
"""

from typing import Optional, Tuple, List
from datetime import datetime
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.users.models import User, OAuthProvider
from app.auth.models import Session
from app.auth.service import AuthService
from app.auth.password import hash_password
from app.credits.models import UserCredit
from app.projects.models import Project
from app.api_keys.models import UserApiKey


class AdminUserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        status_filter: Optional[str] = None,
        role: Optional[str] = None,
        created_from: Optional[datetime] = None,
        created_to: Optional[datetime] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[dict], int]:
        """List users with filtering, searching, and pagination."""

        # Base query
        query = select(
            User,
            func.coalesce(UserCredit.balance_cents, 0).label("credit_balance_cents"),
            func.coalesce(UserCredit.total_deposited_cents, 0).label("total_deposited_cents"),
            func.coalesce(UserCredit.total_consumed_cents, 0).label("total_consumed_cents"),
            func.count(Project.id.distinct()).label("project_count"),
        ).outerjoin(
            UserCredit, User.id == UserCredit.user_id
        ).outerjoin(
            Project, User.id == Project.user_id
        ).group_by(User.id, UserCredit.balance_cents, UserCredit.total_deposited_cents, UserCredit.total_consumed_cents)

        # Count query
        count_query = select(func.count(User.id.distinct()))

        # Search filter
        if search:
            search_filter = or_(
                User.name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        # Status filter
        if status_filter == "active":
            query = query.where(User.is_active == True)
            count_query = count_query.where(User.is_active == True)
        elif status_filter == "inactive":
            query = query.where(User.is_active == False)
            count_query = count_query.where(User.is_active == False)

        # Role filter
        if role == "admin":
            query = query.where(User.is_admin == True)
            count_query = count_query.where(User.is_admin == True)
        elif role == "user":
            query = query.where(User.is_admin == False)
            count_query = count_query.where(User.is_admin == False)

        # Date range
        if created_from:
            query = query.where(User.created_at >= created_from)
            count_query = count_query.where(User.created_at >= created_from)
        if created_to:
            query = query.where(User.created_at <= created_to)
            count_query = count_query.where(User.created_at <= created_to)

        # Sorting
        allowed_user_sort = {"created_at", "name", "email", "last_login_at", "max_projects"}
        # Computed columns from JOINs
        computed_sort = {
            "credit_balance_cents": func.coalesce(UserCredit.balance_cents, 0),
            "total_deposited_cents": func.coalesce(UserCredit.total_deposited_cents, 0),
            "total_consumed_cents": func.coalesce(UserCredit.total_consumed_cents, 0),
            "project_count": func.count(Project.id.distinct()),
        }

        if sort_by in computed_sort:
            sort_col = computed_sort[sort_by]
        elif sort_by in allowed_user_sort:
            sort_col = getattr(User, sort_by)
        else:
            sort_col = User.created_at

        if sort_order == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())

        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self.db.execute(query)
        rows = result.all()

        users = []
        for row in rows:
            user = row[0]
            users.append({
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "avatar_url": user.avatar_url,
                "oauth_provider": user.oauth_provider.value if user.oauth_provider else "local",
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "is_admin": user.is_admin,
                "max_projects": user.max_projects,
                "max_containers": user.max_containers,
                "created_at": user.created_at,
                "last_login_at": user.last_login_at,
                "credit_balance_cents": row[1],
                "total_deposited_cents": row[2],
                "total_consumed_cents": row[3],
                "project_count": row[4],
            })

        return users, total

    async def get_user_detail(self, user_id: str) -> dict:
        """Get detailed user info with counts."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get credit info
        credit_result = await self.db.execute(
            select(UserCredit).where(UserCredit.user_id == user_id)
        )
        credit = credit_result.scalar_one_or_none()

        # Get counts
        session_count = (await self.db.execute(
            select(func.count(Session.id)).where(
                and_(Session.user_id == user_id, Session.is_revoked == False)
            )
        )).scalar() or 0

        project_count = (await self.db.execute(
            select(func.count(Project.id)).where(Project.user_id == user_id)
        )).scalar() or 0

        api_keys_count = (await self.db.execute(
            select(func.count(UserApiKey.id)).where(UserApiKey.user_id == user_id)
        )).scalar() or 0

        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "avatar_url": user.avatar_url,
            "oauth_provider": user.oauth_provider.value if user.oauth_provider else "local",
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "is_admin": user.is_admin,
            "max_projects": user.max_projects,
            "max_containers": user.max_containers,
            "created_at": user.created_at,
            "last_login_at": user.last_login_at,
            "credit_balance_cents": credit.balance_cents if credit else 0,
            "project_count": project_count,
            "active_sessions_count": session_count,
            "api_keys_count": api_keys_count,
            "total_consumed_cents": credit.total_consumed_cents if credit else 0,
            "total_deposited_cents": credit.total_deposited_cents if credit else 0,
        }

    async def toggle_active(self, user_id: str, is_active: bool, admin_id: str) -> dict:
        """Toggle user active status. Revokes sessions on deactivation."""
        if user_id == admin_id:
            raise HTTPException(status_code=400, detail="Cannot change your own active status")

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.is_active = is_active
        await self.db.flush()

        # Revoke all sessions when deactivating
        if not is_active:
            auth_service = AuthService(self.db)
            await auth_service.logout_all(user_id)

        await self.db.refresh(user)
        return {
            "id": user.id,
            "email": user.email,
            "is_active": user.is_active,
        }

    async def toggle_admin(self, user_id: str, is_admin: bool, admin_id: str) -> dict:
        """Toggle user admin status."""
        if user_id == admin_id:
            raise HTTPException(status_code=400, detail="Cannot change your own admin status")

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.is_admin = is_admin
        await self.db.flush()
        await self.db.refresh(user)
        return {
            "id": user.id,
            "email": user.email,
            "is_admin": user.is_admin,
        }

    async def reset_password(self, user_id: str, new_password: str) -> dict:
        """Reset a user's password. Only for local auth users."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if user.oauth_provider != OAuthProvider.LOCAL:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reset password for {user.oauth_provider.value} OAuth user"
            )

        user.password_hash = hash_password(new_password)
        await self.db.flush()

        # Revoke all sessions to force re-login
        auth_service = AuthService(self.db)
        await auth_service.logout_all(user_id)

        return {"id": user.id, "email": user.email, "message": "Password reset successfully"}

    async def update_max_projects(self, user_id: str, max_projects: int) -> dict:
        """Update user's max projects limit."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.max_projects = max_projects
        await self.db.flush()
        await self.db.refresh(user)
        return {
            "id": user.id,
            "email": user.email,
            "max_projects": user.max_projects,
        }

    async def update_max_containers(self, user_id: str, max_containers: int) -> dict:
        """Update user's max containers limit."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.max_containers = max_containers
        await self.db.flush()
        await self.db.refresh(user)
        return {
            "id": user.id,
            "email": user.email,
            "max_containers": user.max_containers,
        }
