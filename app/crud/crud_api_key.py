from uuid import UUID
from typing import Sequence
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.base import CRUDBase
from app.core.security import generate_api_key, hash_api_key
from app.models.api_key import APIKey
from app.schemas.api_key import APIKeyCreate


class CRUDAPIKey(CRUDBase[APIKey, APIKeyCreate, APIKeyCreate]):
    async def create_for_user(
        self, db: AsyncSession, *, obj_in: APIKeyCreate, user_id: UUID
    ) -> tuple[APIKey, str]:
        """Creates a new API key record, returning the DB object and raw key string."""
        raw_key, key_prefix, hashed_key = generate_api_key()

        db_obj = APIKey(
            user_id=user_id,
            name=obj_in.name,
            prefix=key_prefix,
            hashed_key=hashed_key,
            rate_limit_override=obj_in.rate_limit_override,
            expires_at=obj_in.expires_at,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj, raw_key

    async def get_by_user(
        self, db: AsyncSession, *, user_id: UUID, skip: int = 0, limit: int = 50
    ) -> Sequence[APIKey]:
        """Retrieves active and revoked API keys for a specific user."""
        result = await db.execute(
            select(APIKey)
            .where(APIKey.user_id == user_id)
            .order_by(APIKey.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_id_and_user(
        self, db: AsyncSession, *, key_id: UUID, user_id: UUID
    ) -> APIKey | None:
        """Fetches a specific key ensuring it belongs to the authenticated user."""
        result = await db.execute(
            select(APIKey).where(
                APIKey.id == key_id,
                APIKey.user_id == user_id,
            )
        )
        return result.scalars().first()

    async def revoke(
        self, db: AsyncSession, *, key_id: UUID, user_id: UUID
    ) -> APIKey | None:
        """Soft-deletes an API key by marking is_active = False."""
        db_key = await self.get_by_id_and_user(db, key_id=key_id, user_id=user_id)
        if not db_key:
            return None

        db_key.is_active = False
        db.add(db_key)
        await db.commit()
        await db.refresh(db_key)
        return db_key

    async def get_by_raw_key(self, db: AsyncSession, *, raw_key: str) -> APIKey | None:
        """Finds an active API key matching the SHA-256 hash."""
        hashed = hash_api_key(raw_key)
        result = await db.execute(
            select(APIKey).where(
                APIKey.hashed_key == hashed,
                APIKey.is_active == True,
            )
        )
        return result.scalars().first()


api_key_crud = CRUDAPIKey(APIKey)