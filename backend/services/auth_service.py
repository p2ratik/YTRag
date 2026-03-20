from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status, Response
from backend.models.user import User
from backend.auth.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token
)


async def register_user(email: str, username: str, password: str, db: AsyncSession) -> User:
    """Checks for existing user and creates a new one with a hashed password."""
    query = select(User).where((User.email_id == email) | (User.user_name == username))
    result = await db.execute(query)
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )

    user = User(
        email_id=email,
        user_name=username,
        password=get_password_hash(password)
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(username: str, password: str, db: AsyncSession) -> User:
    """Validates credentials and returns the User model if correct."""
    result = await db.execute(select(User).where(User.user_name == username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    return user


def issue_tokens(user: User, response: Response) -> dict:
    """Generates access + refresh tokens and sets the refresh token as an HttpOnly cookie."""
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=7 * 24 * 60 * 60,
        samesite="lax",
        secure=False  # Set True in production with HTTPS
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "username": user.user_name,
            "email": user.email_id
        }
    }
