from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user
from src.database import get_db
from src.models.user import User
from src.schemas.user import ApiKeyResponse

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("/generate", response_model=ApiKeyResponse)
def generate_api_key(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a new API key for the authenticated user. Replaces any existing key."""
    new_key = User.generate_api_key()
    current_user.api_key = new_key
    db.commit()
    return ApiKeyResponse(api_key=new_key)


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoke an API key. Users can only revoke their own key; admins can revoke any."""
    from src.models.user import Role

    if current_user.role == Role.admin:
        target = db.query(User).filter(User.api_key == key).first()
    else:
        target = current_user if current_user.api_key == key else None

    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    target.api_key = None
    db.commit()
