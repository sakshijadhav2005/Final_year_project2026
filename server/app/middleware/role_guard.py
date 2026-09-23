from collections.abc import Sequence

from fastapi import Depends, HTTPException, status

from app.api.deps import get_current_user
from app.core.security import UserRole
from app.models.user import User


def require_role(allowed_roles: Sequence[UserRole] | UserRole):
    roles = [allowed_roles] if isinstance(allowed_roles, (UserRole, str)) else list(allowed_roles)
    allowed_values = {r.value if hasattr(r, "value") else str(r) for r in roles}

    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role_str = (
            current_user.role.value
            if hasattr(current_user.role, "value")
            else str(current_user.role)
        )
        if user_role_str not in allowed_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_checker
