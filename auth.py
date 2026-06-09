from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from model import User

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

SECRET_KEY = "MY_SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, ALGORITHM)
    return encoded_jwt

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        print(e)
        return None

async def get_current_user(token: str = Depends(oauth2_scheme),
                           db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(token)
        if payload is None:
            raise HTTPException(status_code=404, detail="Could not validate credentials (token invalid or expired)")
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=404, detail="Incorrect username or password1")
    except:
        raise HTTPException(status_code=404, detail="Incorrect username or password2")
    query = await db.execute(select(User).where(User.id == int(user_id)))
    user = query.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Incorrect username or password3")
    return user



