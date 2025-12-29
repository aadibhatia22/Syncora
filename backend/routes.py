from typing import List
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
from starlette.config import Config
from authlib.integrations.starlette_client import OAuth
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer
from dotenv import load_dotenv
from sqlalchemy.orm import Session

import models
import schemas
from database import SessionLocal

# Load environment variables
load_dotenv()

router = APIRouter()

# --- OAuth and JWT Configuration ---
config = Config(environ=os.environ)
oauth = OAuth(config)
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

JWT_SECRET = os.getenv("APP_JWT_SECRET")
JWT_ALG = "HS256"
JWT_EXP_MIN = 60 * 24  # 24 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Database Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- User CRUD Functions ---
def get_user_by_google_sub(db: Session, google_sub: str):
    return db.query(models.User).filter(models.User.google_sub == google_sub).first()

def get_user_by_id(db: Session, user_id: str):
    return db.query(models.User).filter(models.User.id == user_id).first()

def create_user(db: Session, email: str, google_sub: str):
    db_user = models.User(id=f"user_{google_sub}", email=email, google_sub=google_sub)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# --- Authentication Dependencies ---
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG], options={"verify_exp": True})
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception
    return user

# --- Routes ---
@router.get("/auth/google/login")
async def google_login(request: Request):
    redirect_uri = request.url_for('google_callback')
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get('userinfo')
    if not userinfo:
        raise HTTPException(status_code=500, detail="Could not fetch user info from Google.")
        
    google_sub = userinfo["sub"]

    user = get_user_by_google_sub(db, google_sub=google_sub)
    if not user:
        user = create_user(
            db=db,
            email=userinfo.get("email"),
            google_sub=google_sub
        )

    payload = {"user_id": user.id, "exp": datetime.utcnow() + timedelta(minutes=JWT_EXP_MIN)}
    syncora_jwt = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

    response = RedirectResponse(url="/frontend/index.html#token=" + syncora_jwt)
    return response

@router.get("/users/me")
async def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user

@router.get("/events", response_model=List[schemas.Event])
async def list_events(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Event).filter(models.Event.owner_id == current_user.id).all()

@router.post("/events", response_model=schemas.Event)
async def create_event(event_data: schemas.EventCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    new_event = models.Event(
        **event_data.model_dump(),
        owner_id=current_user.id
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return new_event

@router.get("/events/{event_id}", response_model=schemas.Event)
async def get_event(event_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this event")
    return event

@router.delete("/events/{event_id}", response_model=dict)
async def delete_event(event_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    event_to_delete = db.query(models.Event).filter(models.Event.id == event_id).first()
    
    if not event_to_delete:
        raise HTTPException(status_code=404, detail="Event not found")
    
    if event_to_delete.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this event")
    
    db.delete(event_to_delete)
    db.commit()
    return {"detail": "Event deleted"}