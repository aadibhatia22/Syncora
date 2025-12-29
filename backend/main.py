from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from routes import router as api_app
import os
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
app = FastAPI()
load_dotenv()
app.add_middleware(
    SessionMiddleware,
    secret_key="change-this-in-prod",  # use an env var in real deployments
    same_site="lax",
    https_only=False,  # True in production with HTTPS
)

app.include_router(api_app)

# Calculate the correct path for the frontend directory
app_directory = os.path.dirname(os.path.abspath(__file__))
frontend_path = os.path.join(app_directory, "../frontend")

# Serve the frontend static files
app.mount("/frontend", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
