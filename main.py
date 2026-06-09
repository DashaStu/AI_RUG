from fastapi import FastAPI, UploadFile, HTTPException, Form, File, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
import os
import shutil
from sqlalchemy import select

from auth import get_password_hash
from ingest import start_ingestion, ask_question
from schemas import UserCreate, UserLogin, User as UserBase
from model import User
from database import get_db
from database import engine, Base
import auth
app = FastAPI()

UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.post("/register", response_model=UserBase)
async def register_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user.email))

    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already exists")
    hashed_password = get_password_hash(user.password)
    new_user = User(name=user.name, email=user.email, password=hashed_password)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@app.post("/login")
async def login_user(form_data: OAuth2PasswordRequestForm = Depends(),
                     db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user_db = result.scalar_one_or_none()
    if not user_db or auth.verify_password(get_password_hash(form_data.password), user_db.password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    token_data = {"sub": str(user_db.id)}
    access_token = auth.create_access_token(data=token_data)
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/upload")
async def upload_document(background_tasks: BackgroundTasks,
                          file: UploadFile = File(...),
                          current_user: User = Depends(auth.get_current_user)):
    file_path = os.path.join(UPLOAD_DIR, f"{current_user.id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    try:
        background_tasks.add_task(start_ingestion, current_user.id, file_path)

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обработке: {str(e)}")

@app.post("/ask")
async def ask_questions(question: str = Form(...), current_user: User = Depends(auth.get_current_user)):
    try:
        result = await ask_question(current_user.id, question)
        return {"answer": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"error: {str(e)}")

