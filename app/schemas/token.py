from uuid import UUID
from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenPayload(BaseModel):
    sub: UUID | str
    exp: int
    