from fastapi import APIRouter, Depends, Response, status, Form
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.session import get_db
from backend.services import auth_service

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    email: str = Form(...),
    password: str = Form(...),
    username: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    await auth_service.register_user(email, username, password, db)
    return {"message": "Signup successful"}


@router.post("/login", status_code=status.HTTP_200_OK)
async def login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    user = await auth_service.authenticate_user(username, password, db)
    return auth_service.issue_tokens(user, response)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("refresh_token")
    return {"message": "Logged out successfully"}