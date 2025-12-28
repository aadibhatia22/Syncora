from fastapi import FastAPI
from routes import router as api_app

# Initialize main application
app = FastAPI()
app.include_router(api_app)

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)