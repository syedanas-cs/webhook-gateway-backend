from typing import Annotated, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud.crud_api_key import api_key_crud
from app.models.user import User
from app.schemas.api_key import (
    APIKeyCreate,
    APIKeyCreateResponse,
    APIKeyRead,
)

router = APIRouter()


@router.post(
    "",
    response_model=APIKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new API key",
)
async def create_api_key(
    key_in: APIKeyCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    Generates a new developer API key.

    **Note:** The full `raw_api_key` is returned **only once** in this response.
    Subsequent GET requests will return only the masked `prefix`.
    """
    db_obj, raw_key = await api_key_crud.create_for_user(
        db, obj_in=key_in, user_id=current_user.id
    )

    return APIKeyCreateResponse(
        id=db_obj.id,
        user_id=db_obj.user_id,
        name=db_obj.name,
        prefix=db_obj.prefix,
        is_active=db_obj.is_active,
        rate_limit_override=db_obj.rate_limit_override,
        expires_at=db_obj.expires_at,
        last_used_at=db_obj.last_used_at,
        created_at=db_obj.created_at,
        updated_at=db_obj.updated_at,
        raw_api_key=raw_key,
    )


@router.get(
    "",
    response_model=List[APIKeyRead],
    summary="List all API keys",
)
async def list_api_keys(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """Retrieves all API keys belonging to the authenticated user."""
    keys = await api_key_crud.get_by_user(
        db, user_id=current_user.id, skip=skip, limit=limit
    )
    return keys


@router.delete(
    "/{key_id}",
    response_model=APIKeyRead,
    summary="Revoke an API key",
)
async def revoke_api_key(
    key_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Revokes (soft-deletes) an API key immediately so it cannot be used for gateway requests."""
    revoked_key = await api_key_crud.revoke(
        db, key_id=key_id, user_id=current_user.id
    )
    if not revoked_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key not found or does not belong to the user.",
        )
    return revoked_key