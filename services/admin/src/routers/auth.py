from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user
from src.auth.jwt import create_access_token
from src.database import get_db
from src.models.user import User
from src.schemas.user import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.email == body.email,
        User.is_active == True,
        User.is_admin == True,
    ).first()
    if user is None or not _pwd_context.verify(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    token = create_access_token(str(user.user_id), extra_claims={"role": user.role})
    return TokenResponse(access_token=token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(current_user: User = Depends(get_current_user)):
    token = create_access_token(str(current_user.user_id), extra_claims={"role": current_user.role})
    return TokenResponse(access_token=token)
