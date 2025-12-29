import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from jose import jwt
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# -------------------------
# OAuth configuration
# -------------------------

oauth = OAuth()
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
