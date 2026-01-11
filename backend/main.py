from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from dotenv import load_dotenv

from routes import router as api_app
from database import engine, Base


app = FastAPI()
load_dotenv()

# Add the middleware to trust the proxy headers from Caddy
app.add_middleware(
    ProxyHeadersMiddleware,
    trusted_hosts="*"
)

# Create the database tables on startup
Base.metadata.create_all(bind=engine)

# Load the secret key from environment variables for security
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY not set")

# The secure flag will be handled by the proxy. 
# The connection between Caddy and FastAPI is HTTP.
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    same_site="lax",
    https_only=False, 
)

app.include_router(api_app)

app_directory = os.path.dirname(os.path.abspath(__file__))
frontend_path = os.path.join(app_directory, "../frontend")

app.mount("/frontend", StaticFiles(directory=frontend_path, html=True), name="frontend")

@app.get("/")
async def root():
    return RedirectResponse(url="/frontend/index.html")

if __name__ == "__main__":
    import uvicorn
    # Run as a standard HTTP server. Caddy will handle HTTPS.
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=8000
    )
