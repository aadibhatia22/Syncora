from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import crud
import schemas
from database import get_db

# We can define a prefix for all routes in this file
router = APIRouter(
    prefix="/events",
    tags=["events"],
)


@router.put("/{event_id}", response_model=schemas.Event)
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    # Now, pass the existing event and the update data to the CRUD function
    updated_event = crud.update_event(db=db, db_event=db_event, update_data=event_update)

    return updated_event