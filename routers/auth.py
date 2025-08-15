from fastapi import APIRouter, HTTPException, status, Depends
from passlib.context import CryptContext
from models.user import UserCreate, UserLogin, User
from utils.jwt import create_access_token
from utils.response import api_response
from typing import Dict
import logging
from utils.logging_config import mask_email

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger("api.auth")

# In-memory user store for demo (replace with DB in production)
fake_users_db: Dict[str, Dict] = {}

def get_password_hash(password):
	return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
	return pwd_context.verify(plain_password, hashed_password)

@router.post("/register")
def register(user: UserCreate):
	if user.email in fake_users_db:
		logger.warning("register_attempt_existing_email", extra={"email": mask_email(user.email)})
		raise HTTPException(status_code=400, detail="Email already registered")
	hashed_password = get_password_hash(user.password)
	user_id = len(fake_users_db) + 1
	fake_users_db[user.email] = {"id": user_id, "email": user.email, "hashed_password": hashed_password}
	logger.info("user_registered", extra={"user_id": user_id, "email": mask_email(user.email)})
	return api_response(data=User(id=user_id, email=user.email).model_dump(), message="User registered", status_code=201)

@router.post("/login")
def login(user: UserLogin):
	db_user = fake_users_db.get(user.email)
	if not db_user or not verify_password(user.password, db_user["hashed_password"]):
		logger.warning("login_failed", extra={"email": mask_email(user.email)})
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
	token = create_access_token({"sub": db_user["email"], "id": db_user["id"]})
	logger.info("login_success", extra={"user_id": db_user["id"], "email": mask_email(db_user["email"])})
	return api_response(
		data={"access_token": token, "token_type": "bearer"},
		message="Login successful",
		status_code=200)