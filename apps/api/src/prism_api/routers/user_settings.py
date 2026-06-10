"""Per-user settings endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from prism_api.deps import csrf_protect, current_user, session_dep
from prism_api.models.user import User
from prism_api.repos.user_settings import UserSettingsRepo
from prism_api.schemas.user_settings import UserSettingIn, UserSettingOut

router = APIRouter(prefix="/api/v1/me/settings", tags=["user-settings"])


@router.get("/{key}")
def get_setting(
    key: str,
    user: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> UserSettingOut:
    row = UserSettingsRepo(session).get(user.id, key)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "setting not found")
    return UserSettingOut(key=row.key, value=row.value, updated_at=row.updated_at)


@router.put("/{key}", dependencies=[Depends(csrf_protect)])
def put_setting(
    key: str,
    body: UserSettingIn,
    user: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> UserSettingOut:
    row = UserSettingsRepo(session).upsert(user.id, key, body.value)
    session.flush()
    return UserSettingOut(key=row.key, value=row.value, updated_at=row.updated_at)
