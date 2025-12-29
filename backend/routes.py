from typing import List
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from starlette.requests import Request
from starlette.config import Config
from authlib.integrations.starlette_client import OAuth
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer
from dotenv import load_dotenv

from models import Event, EventCreate, events_db, User

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

# --- User Storage (In-Memory) ---
users_db_by_id = {}
users_db_by_google_sub = {}

def create_user(email, provider, provider_user_id):
    user_id = f"user_{len(users_db_by_id) + 1}"
    user_data = {
        "id": user_id,
        "email": email,
        "provider": provider,
        "provider_user_id": provider_user_id,
        "created_at": datetime.utcnow(),
    }
    users_db_by_id[user_id] = user_data
    users_db_by_google_sub[(provider, provider_user_id)] = user_data
    return user_data

def get_user_by_google_sub(provider, provider_user_id):
    return users_db_by_google_sub.get((provider, provider_user_id))

def get_user_by_id(user_id: str):
    return users_db_by_id.get(user_id)

# --- Authentication Dependencies ---
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    return user

# --- Routes ---
@router.get("/auth/google/login")
async def google_login(request: Request):
    # The external URL is HTTPS, but the redirect URI for the internal app is HTTP
    # We will use the request's scheme to build the correct redirect URI
    redirect_uri = request.url_for('google_callback')
    return await oauth.google.authorize_redirect(request, str(redirect_uri))


@router.get("/auth/google/callback")
async def google_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get('userinfo')
    if not userinfo:
        raise HTTPException(status_code=500, detail="Could not fetch user info from Google.")
        
    google_sub = userinfo["sub"]
    email = userinfo.get("email")

    user = get_user_by_google_sub("google", google_sub)
    if not user:
        user = create_user(
            email=email,
            provider="google",
            provider_user_id=google_sub
        )

    payload = {"user_id": user["id"], "exp": datetime.utcnow() + timedelta(minutes=JWT_EXP_MIN)}
    syncora_jwt = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

    response = RedirectResponse(url="/frontend/index.html#token=" + syncora_jwt)
    return response

@router.get("/users/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user

@router.get("/users/all")
async def get_all_users():
    return users_db_by_id

@router.get("/events", response_model=List[Event])
async def list_events(current_user: dict = Depends(get_current_user)):
    return [event for event in events_db if event.owner_id == current_user["id"]]

@router.post("/events", response_model=Event)
async def create_event(event_data: EventCreate, current_user: dict = Depends(get_current_user)):
    event_id = len(events_db) + 1
    new_event = Event(
        id=event_id,
        owner_id=current_user["id"],
        **event_data.dict()
    )
    events_db.append(new_event)
    return new_event

@router.get("/events/{event_id}", response_model=Event)
async def get_event(event_id: int, current_user: dict = Depends(get_current_user)):
    for event in events_db:
        if event.id == event_id:
            if event.owner_id == current_user["id"]:
                return event
            else:
                raise HTTPException(status_code=403, detail="Not authorized to view this event")
    raise HTTPException(status_code=404, detail="Event not found")

@router.delete("/events/{event_id}", response_model=dict)
async def delete_event(event_id: int, current_user: dict = Depends(get_current_user)):
    event_to_delete = None
    for event in events_db:
        if event.id == event_id:
            if event.owner_id == current_user["id"]:
                event_to_delete = event
                break
            else:
                raise HTTPException(status_code=403, detail="Not authorized to delete this event")
    
    if event_to_delete:
        events_db.remove(event_to_delete)
        return {"detail": "Event deleted"}
    else:
        raise HTTPException(status_code=404, detail="Event not found")