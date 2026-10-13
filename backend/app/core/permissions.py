from enum import Enum
from fastapi import HTTPException, status


class Role(str, Enum):
    ADMIN = "admin"
    ENGINEER = "engineer"
    L1_SUPPORT = "l1_support"
    L2_SUPPORT = "l2_support"
    AUDITOR = "auditor"


# What each role can do
ROLE_PERMISSIONS = {
    Role.ADMIN: {"*"},  # All permissions
    Role.ENGINEER: {
        "incident:read", "incident:create", "incident:update",
        "log:upload", "log:read",
        "analysis:run", "analysis:read",
        "copilot:use",
        "remediation:propose", "remediation:read",
        "knowledge:read", "knowledge:write",
        "models:read", "models:train",
        "audit:read",
    },
    Role.L1_SUPPORT: {
        "incident:read", "incident:create", "incident:update",
        "log:upload", "log:read",
        "analysis:read",
        "copilot:use",
        "remediation:read",
        "knowledge:read",
        "audit:read",
    },
    Role.L2_SUPPORT: {
        "incident:read", "incident:create", "incident:update",
        "log:upload", "log:read",
        "analysis:run", "analysis:read",
        "copilot:use",
        "remediation:propose", "remediation:read",
        "knowledge:read", "knowledge:write",
        "audit:read",
    },
    Role.AUDITOR: {
        "incident:read",
        "log:read",
        "analysis:read",
        "remediation:read",
        "knowledge:read",
        "audit:read",
    },
}


def has_permission(user, permission: str) -> bool:
    for role_name in [r.name for r in user.roles]:
        role = Role(role_name.lower())
        perms = ROLE_PERMISSIONS.get(role, set())
        if "*" in perms or permission in perms:
            return True
    return False


def require_permission(permission: str):
    from fastapi import Depends
    from app.core.security import get_current_active_user

    async def checker(current_user=Depends(get_current_active_user)):
        if not has_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}",
            )
        return current_user

    return Depends(checker)
