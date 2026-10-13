from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.db.session import get_db
from app.db import models
from app.core.security import verify_password, create_access_token, get_current_active_user
from app.services.audit_service import log_action
from datetime import timedelta

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    full_name: str
    roles: list[str]


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db), request: Request = None):
    result = await db.execute(
        select(models.User).where(
            models.User.username == body.username,
            models.User.is_active == True,
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_access_token({"sub": user.id})

    # Load roles
    roles_result = await db.execute(
        select(models.Role)
        .join(models.UserRole, models.UserRole.role_id == models.Role.id)
        .where(models.UserRole.user_id == user.id)
    )
    roles = [r.name for r in roles_result.scalars().all()]

    await log_action(
        db=db,
        action="auth.login",
        user_id=user.id,
        resource_type="user",
        resource_id=user.id,
        ip_address=request.client.host if request else None,
    )

    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        roles=roles,
    )


@router.post("/logout")
async def logout(current_user=Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    await log_action(db=db, action="auth.logout", user_id=current_user.id)
    return {"message": "Logged out successfully"}


@router.get("/me")
async def me(current_user=Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    roles_result = await db.execute(
        select(models.Role)
        .join(models.UserRole, models.UserRole.role_id == models.Role.id)
        .where(models.UserRole.user_id == current_user.id)
    )
    roles = [r.name for r in roles_result.scalars().all()]
    return {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "roles": roles,
        "is_active": current_user.is_active,
    }


@router.post("/register")
async def register_first_admin(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Register the initial admin account.
    Only works if no users exist yet.
    """
    existing = await db.execute(select(models.User).limit(1))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Registration is only available for the first admin. Use admin management to add more users.",
        )

    from app.core.security import hash_password
    import uuid
    from datetime import datetime, timezone

    username = body.get("username")
    password = body.get("password")
    email = body.get("email")
    full_name = body.get("full_name", username)

    if not all([username, password, email]):
        raise HTTPException(status_code=400, detail="username, password, and email are required")

    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    now = datetime.now(timezone.utc)
    user = models.User(
        id=str(uuid.uuid4()),
        email=email,
        username=username,
        full_name=full_name,
        hashed_password=hash_password(password),
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    await db.flush()

    # Assign admin role
    role_result = await db.execute(select(models.Role).where(models.Role.name == "admin"))
    admin_role = role_result.scalar_one_or_none()
    if admin_role:
        user_role = models.UserRole(
            id=str(uuid.uuid4()),
            user_id=user.id,
            role_id=admin_role.id,
            assigned_at=now,
        )
        db.add(user_role)

    await log_action(db=db, action="auth.register_admin", resource_type="user", resource_id=user.id)
    return {"message": "Admin account created", "username": username}
