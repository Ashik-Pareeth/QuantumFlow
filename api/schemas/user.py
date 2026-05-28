import re

from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=20,
        description="Public display name for the leaderboard",
    )
    email: EmailStr
    password: str = Field(
        ..., min_length=8, description="Password must be at least 8 characters"
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError(
                "Username can only contain letters, numbers, and underscores."
            )
        return v

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one number.")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character.")

        # If it passes all checks, return the valid password
        return v


class PaperTradingInfo(BaseModel):
    starting_capital: float
    currency: str
    status: str


class UserInfo(BaseModel):
    id: UUID = Field(..., description="Unique identifier for the user")
    username: str
    email: str


# 2. Compose the final response
class UserRegisterResponse(BaseModel):
    message: str
    paper_trading: PaperTradingInfo
    user: UserInfo
    access_token: str
    token_type: str = "bearer"
