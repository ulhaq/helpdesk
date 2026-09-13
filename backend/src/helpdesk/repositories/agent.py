from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.platform.models.permission import Permission, RolePermission
from src.platform.models.role import Role, UserRole
from src.platform.models.user import User
from src.platform.models.user_organization import UserOrganization


class AgentRepository:
    """Resolves which members of an organization work its tickets."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def user_ids_with_permission(
        self, organization_id: int, permission: str
    ) -> list[int]:
        """Active members granted `permission` by one of their roles in the
        organization."""
        stmt = (
            select(UserOrganization.user_id)
            .distinct()
            .join(
                User,
                and_(User.id == UserOrganization.user_id, User.deleted_at.is_(None)),
            )
            .join(UserRole, UserRole.user_id == UserOrganization.user_id)
            .join(
                Role,
                and_(
                    Role.id == UserRole.role_id,
                    Role.organization_id == organization_id,
                    Role.deleted_at.is_(None),
                ),
            )
            .join(RolePermission, RolePermission.role_id == Role.id)
            .join(
                Permission,
                and_(
                    Permission.id == RolePermission.permission_id,
                    Permission.name == permission,
                    Permission.deleted_at.is_(None),
                ),
            )
            .where(UserOrganization.organization_id == organization_id)
            .order_by(UserOrganization.user_id)
        )
        rs = await self.db.execute(stmt)
        return list(rs.scalars().all())

    async def names(self, user_ids: set[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        rs = await self.db.execute(
            select(User.id, User.name).where(User.id.in_(user_ids))
        )
        return dict(rs.tuples().all())
