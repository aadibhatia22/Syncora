from typing import List
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from starlette.requests import Request
from starlette.config import Config
from authlib.integrations.starlette_client import OAuth
from jose import jwt
from dotenv import load_dotenv

from models import Event, events_db, User

# Load environment variables
load_dotenv()

router = APIRouter()


config = Config(environ=os.environ)
oauth = OAuth(config)
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# -------------------------
# JWT configuration
# -------------------------

JWT_SECRET = os.getenv("APP_JWT_SECRET")
JWT_ALG = "HS256"
JWT_EXP_MIN = 60 * 24  # 24 hours



# In-memory user store keyed by Google sub
users_db = {}

def create_user(email, provider, provider_user_id):
    user_id = f"user_{len(users_db) + 1}"
    users_db[(provider, provider_user_id)] = {
        "id": user_id,
        "email": email,
        "provider": provider,
        "provider_user_id": provider_user_id,
        "created_at": datetime.utcnow(),
    }
    return users_db[(provider, provider_user_id)]

def get_user(provider, provider_user_id):
    return users_db.get((provider, provider_user_id))


@router.get("/auth/google/login")
async def google_login(request: Request):
    return await oauth.google.authorize_redirect(
        request,
        redirect_uri="http://127.0.0.1:8000/auth/google/callback"
    )


@router.get("/auth/google/callback")
async def google_callback(request: Request):
    # 1. Exchange code → tokens (Google verification happens here)
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get('userinfo')
    if not userinfo:
        raise HTTPException(status_code=500, detail="Could not fetch user info from Google.")
        
    google_sub = userinfo["sub"]
    email = userinfo.get("email")

    # 3. Find or create Syncora user
    user = get_user("google", google_sub)

    if not user:
        user = create_user(
            email=email,
            provider="google",
            provider_user_id=google_sub
        )

    # 4. Issue Syncora JWT
    payload = {
        "user_id": user["id"],
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXP_MIN)
    }

    syncora_jwt = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

    # 5. Send user back to the frontend
    response = RedirectResponse(url="/frontend/index.html#token=" + syncora_jwt)
    return response



@router.get("/events", response_model=List[Event])
async def list_events():
    return events_db

@router.post("/events", response_model=Event)
async def create_event(event: Event):
    events_db.append(event)
    return event

@router.get("/events/{event_id}", response_model=Event)
async def get_event(event_id: int):
    for event in events_db:
        if event.id == event_id:
            return event
    raise HTTPException(status_code=404, detail="Event not found")

@router.delete("/events/{event_id}", response_model=dict)
async def delete_event(event_id: int):
    events_db[:] = [event for event in events_db if event.id != event_id]
    return {"detail": "Event deleted"}