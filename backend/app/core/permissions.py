from enum import Enum
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session
from app.models.user import UserRole
from app.database import get_db
from app.core.security import decode_token
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class Permission(str, Enum):
    USER_MANAGE = "user:manage"
    PROJECT_MANAGE = "project:manage"
    TEST_EXECUTE = "test:execute"
    TEST_VIEW = "test:view"
    REPORT_CREATE = "report:create"
    REPORT_VIEW = "report:view"
    SYSTEM_CONFIG = "system:config"
    SCENE_MANAGE = "scene:manage"
    THRESHOLD_MANAGE = "threshold:manage"
    DATA_EXPORT = "data:export"
    CLOUD_AR_MANAGE = "cloud_ar:manage"


ROLE_PERMISSIONS = {
    UserRole.ADMIN: [
        Permission.USER_MANAGE,
        Permission.PROJECT_MANAGE,
        Permission.TEST_EXECUTE,
        Permission.TEST_VIEW,
        Permission.REPORT_CREATE,
        Permission.REPORT_VIEW,
        Permission.SYSTEM_CONFIG,
        Permission.SCENE_MANAGE,
        Permission.THRESHOLD_MANAGE,
        Permission.DATA_EXPORT,
        Permission.CLOUD_AR_MANAGE,
    ],
    UserRole.TESTER: [
        Permission.TEST_EXECUTE,
        Permission.TEST_VIEW,
        Permission.REPORT_VIEW,
        Permission.SCENE_MANAGE,
        Permission.CLOUD_AR_MANAGE,
    ],
    UserRole.REPORT_EDITOR: [
        Permission.TEST_VIEW,
        Permission.REPORT_CREATE,
        Permission.REPORT_VIEW,
        Permission.DATA_EXPORT,
    ],
    UserRole.VIEWER: [
        Permission.TEST_VIEW,
        Permission.REPORT_VIEW,
    ],
}


def check_permission(user_role: UserRole, required_permission: Permission) -> bool:
    permissions = ROLE_PERMISSIONS.get(user_role, [])
    return required_permission in permissions


def require_permission(required_permission: Permission):
    def permission_checker(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
        from app.models.user import User

        payload = decode_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证令牌",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的认证令牌",
            )

        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在",
            )

        if user.status.value == "locked":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已被锁定",
            )

        if user.status.value == "inactive":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已被禁用",
            )

        if not check_permission(user.role, required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )

        return user

    return permission_checker


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from app.models.user import User

    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    return user
