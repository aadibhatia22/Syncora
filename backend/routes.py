from typing import List
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request, File, UploadFile, Query
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
import schemas
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

@router.put("/events/{event_id}", response_model=schemas.Event)
def update_single_event(
    event_id: int,
    event_update: schemas.EventUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an existing event by its ID.
    """
    # First, retrieve the event from the database
    db_event = crud.get_event(db, event_id=event_id)

    if db_event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    # Now, pass the existing event and the update data to the CRUD function
    updated_event = crud.update_event(db=db, db_event=db_event, update_data=event_update)

    return updated_event

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

#OLD CODE
""" 
@router.post("/OCR")
async def perform_ocr(file: UploadFile = File(...)):
    # Read file bytes ONCE
    file_bytes = await file.read()

    content_type = file.content_type.lower()

    try:
        if content_type in ("image/jpeg", "image/png"):
            image = Image.open(io.BytesIO(file_bytes))
            text = pytesseract.image_to_string(image)

        elif content_type == "application/pdf":
            images = convert_from_bytes(file_bytes)
            text = "".join(
                pytesseract.image_to_string(img) for img in images
            )

        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid file format. Only JPEG, PNG, or PDF allowed."
            )

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"OCR processing failed: {str(e)}"
        )
    return {"text": text}

@router.post("/LLM/{assignment_text}")
async def perform_llm(
    assignment_text: str,
    custom_instructions: Optional[str] = Query(default="")
):
    try:
        #assignment = assignmentText.json()
        #ocr_text = assignment["text"]
        ocr_text = assignment_text
        system_message = {
            "role": "system",
            "content": "You have an extremely important job. You will be passed in assignments (CONVERTED TO TEXT AND USUALLY FOR SCHOOL) and YOUR TASK is to accurately estimate how long the assigment will take a student in minutes. YOUR OUTPUT FORMAT SHOULD JUST BE A NUMBER (in minutes) of how long the assigment would take. If the media provided does not look like an assignment output 'ASSIGNMENT NOT DETECTED'. You may recieve custom instructions about the assingment such as, the student has to only do even problems which may effect your time estimation. Assume the student works at an average high school pace and be lenient (remember they are not robots!). Make sure your response does not contain any \\n characters "
        }
        user_message = {
            "role": "user",
            "content": (
                "ASSIGNMENT:\n"
                f"{ocr_text}"
                "CUSTOM INSTRUCTIONS:\n"
                f"{custom_instructions or 'None'}"
            )
        }
        completion = LLM.client.chat.completions.create(
            model="google/gemma-3-27b-it",
            messages=[system_message, user_message]
        )
        response_text = completion.choices[0].message.content
        return {"response": response_text}
    except requests.exceptions.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="INVALID INPUT, JSON REQUIRED"
        )







@router.post("/EstimateTime")
async def estimate_time(file: UploadFile = File(...)):
    """"""
    Integrate OCR and LLM to estimate the time required for an assignment.
    """"""
    # Step 1: Call OCR method to extract text from the uploaded file
    ocr_result = await perform_ocr(file)

    # Extract text for use in LLM processing
    assignment_text = ocr_result["text"]

    # Step 2: Call the LLM method with the extracted text
    llm_response = await perform_llm(assignment_text)

    # Return the estimate time determined by the LLM
    return llm_response

@router.post("/create-assignment")
async def create_assignment(payload: schemas.CreateAssignmentRequest):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://localhost:8000/LLM/{payload.assignment_text}",
                params={"custom_instructions": payload.custom_instructions}
            )

        response.raise_for_status()
        llm_result = response.json()

        return {
            "estimated_minutes": llm_result["response"]
        }

    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=str(e))


"""


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

