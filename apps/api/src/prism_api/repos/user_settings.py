"""Per-user settings repository."""

from typing import Any

from sqlalchemy.orm import Session

from prism_api.models.user_settings import UserSetting


class UserSettingsRepo:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: str, key: str) -> UserSetting | None:
        return self._session.get(UserSetting, (user_id, key))

    def upsert(self, user_id: str, key: str, value: dict[str, Any]) -> UserSetting:
        existing = self.get(user_id, key)
        if existing is not None:
            existing.value = value
            return existing
        row = UserSetting(user_id=user_id, key=key, value=value)
        self._session.add(row)
        self._session.flush()
        return row
