from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.base import CRUDBase
from app.core.security import generate_api_key, hash_api_key
from app.models.api_key import APIKey
from app.schemas.api_key import APIKeyCreate


class CRUDAPIKey(CRUDBase[APIKey, APIKeyCreate, APIKeyCreate]):
    async def create_for_user(
        self, db: AsyncSession, *, obj_in: APIKeyCreate, user_id: UUID
    ) -> tuple[APIKey, str]:
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

    async def get_by_raw_key(self, db: AsyncSession, *, raw_key: str) -> APIKey | None:
        hashed = hash_api_key(raw_key)
        result = await db.execute(
            select(APIKey).where(APIKey.hashed_key == hashed, APIKey.is_active == True)
        )
        return result.scalars().first()


api_key_crud = CRUDAPIKey(APIKey)