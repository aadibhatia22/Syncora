from typing import List
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request, File, UploadFile, Query, Form
from fastapi.responses import RedirectResponse
from starlette.config import Config
from authlib.integrations.starlette_client import OAuth
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer
from dotenv import load_dotenv
from sqlalchemy.orm import Session
import pytesseract
from PIL import Image
import io
from pdf2image import convert_from_bytes
import requests
import LLM
from typing import Optional
import models
import schemas
import crud
from database import SessionLocal
import httpx


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
    
    user = crud.get_user_by_id(db, user_id)
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

    user = crud.get_user_by_google_sub(db, google_sub=google_sub)
    if not user:
        print("IN THE LOOP")
        user = crud.create_user(
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
async def create_event_route(event_data: schemas.EventCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return crud.create_event(db=db, event=event_data, owner_id=current_user.id)

@router.get("/events/{event_id}", response_model=schemas.Event)
async def get_event(event_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = crud.get_event(db, event_id=event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this event")
    return event

@router.put("/events/{event_id}", response_model=schemas.Event)
def update_single_event(
    event_id: int,
    event_update: schemas.EventUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_event = crud.get_event(db, event_id=event_id)
    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if db_event.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this event")

    updated_event = crud.update_event(db=db, db_event=db_event, update_data=event_update)
    return updated_event

@router.delete("/events/{event_id}", response_model=dict)
async def delete_event(event_id: int, current_user: models.User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    event_to_delete = crud.get_event(db, event_id=event_id)

    if not event_to_delete:
        raise HTTPException(status_code=404, detail="Event not found")

    if event_to_delete.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this event")

    db.delete(event_to_delete)
    db.commit()
    return {"detail": "Event deleted"}



async def ocr_from_file(file: UploadFile) -> str:
    file_bytes = await file.read()
    content_type = file.content_type.lower()

    if content_type in ("image/jpeg", "image/png"):
        image = Image.open(io.BytesIO(file_bytes))
        return pytesseract.image_to_string(image)

    if content_type == "application/pdf":
        images = convert_from_bytes(file_bytes)
        return "".join(pytesseract.image_to_string(img) for img in images)

    raise HTTPException(
        status_code=400,
        detail="Invalid file format. Only JPEG, PNG, or PDF allowed."
    )

async def estimate_assignment_time(
    assignment_text: str,
    custom_instructions: str = ""
) -> str:
    system_message = {
        "role": "system",
        "content": (
            "You have an extremely important job. You will be passed in assignments "
            "(CONVERTED TO TEXT AND USUALLY FOR SCHOOL) and YOUR TASK is to accurately "
            "estimate how long the assigment will take a student in minutes. "
            "YOUR OUTPUT FORMAT SHOULD JUST BE A NUMBER (in minutes). "
            "If the media provided does not look like an assignment output "
            "'ASSIGNMENT NOT DETECTED'. Assume an average high school pace. "
            "Make sure your response does not contain any \\n characters."
        )
    }

    user_message = {
        "role": "user",
        "content": (
            "ASSIGNMENT:\n"
            f"{assignment_text}\n\n"
            "CUSTOM INSTRUCTIONS:\n"
            f"{custom_instructions or 'None'}"
        )
    }

    completion = LLM.client.chat.completions.create(
        model="google/gemma-3-27b-it",
        messages=[system_message, user_message]
    )

    return completion.choices[0].message.content


@router.post("/OCR")
async def perform_ocr(file: UploadFile = File(...)):
    text = await ocr_from_file(file)
    return {"text": text}


@router.post("/LLM")
async def perform_llm(
    assignment_text: str,
    custom_instructions: Optional[str] = Query(default="")
):
    response = await estimate_assignment_time(
        assignment_text,
        custom_instructions
    )
    return {"response": response}

@router.post("/EstimateTime")
async def estimate_time(
    file: UploadFile = File(...),
    custom_instructions: Optional[str] = Query(default="")
):
    assignment_text = await ocr_from_file(file)

    estimate = await estimate_assignment_time(
        assignment_text,
        custom_instructions
    )

    return {"response": estimate}


#ASSIGNMENT FULL CREATIONS
@router.post("/assignments", response_model=schemas.Assignment)
async def create_assignment(assignment_data: schemas.CreateAssignment, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    new_assignment = models.Assignment(
        **assignment_data.model_dump(),
        owner_id=current_user.id
    )
    db.add(new_assignment)
    db.commit()
    db.refresh(new_assignment)
    return new_assignment

@router.post("/assignments/upload", response_model=schemas.Assignment)
async def create_assignment_with_file(
    title: str = Form(...),
    subject: str = Form(...),
    file: UploadFile = File(...),
    custom_instructions: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    assignment_text = await ocr_from_file(file)
    estimated_time_str = await estimate_assignment_time(assignment_text, custom_instructions or "")
    try:
        estimated_minutes = int(estimated_time_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Could not estimate time for the assignment. The file might not be a valid assignment.")

    new_assignment = models.Assignment(
        title=title,
        subject=subject,
        estimated_minutes=estimated_minutes,
        description=description,
        owner_id=current_user.id
    )
    db.add(new_assignment)
    db.commit()
    db.refresh(new_assignment)
    return new_assignment





@router.get("/assignments", response_model=List[schemas.Assignment])
async def list_assignments(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(models.Assignment).filter(models.Assignment.owner_id == current_user.id).all()


@router.get("/assignments/{assignment_id}", response_model=schemas.Assignment)
async def get_single_assignment(assignment_id: int, current_user: models.User = Depends(get_current_user),
                                db: Session = Depends(get_db)):
    assignment = crud.get_assignment(db, assignment_id=assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if assignment.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this assignment")
    return assignment



@router.put("/assignments/{assignment_id}", response_model=schemas.Assignment)
def update_single_assignment(
        assignment_id: int,
        assignment_update: schemas.UpdateAssignment,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    db_assignment = crud.get_assignment(db, assignment_id=assignment_id)
    if db_assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    if db_assignment.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this assignment")

    updated_assignment = crud.update_assignment(db=db, db_assignment=db_assignment, update_data=assignment_update)
    return updated_assignment


@router.delete("/assignments/{assignment_id}", response_model=dict)
async def delete_assignment(assignment_id: int, current_user: models.User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    assignment_to_delete = crud.get_assignment(db, assignment_id=assignment_id)

    if not assignment_to_delete:
        raise HTTPException(status_code=404, detail="Assignment not found")

    if assignment_to_delete.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this assignment")

    db.delete(assignment_to_delete)
    db.commit()
    return {"detail": "Assignment deleted"}
