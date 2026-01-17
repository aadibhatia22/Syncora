from sqlalchemy.orm import Session

import models
import schemas


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


def get_event(db: Session, event_id: int):
    """Fetches a single event by its ID."""
    return db.query(models.Event).filter(models.Event.id == event_id).first()

def create_event(db: Session, event: schemas.EventCreate, owner_id: str):
    db_event = models.Event(**event.model_dump(), owner_id=owner_id)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

def update_event(db: Session, db_event: models.Event, update_data: schemas.EventUpdate) -> models.Event:
    """
    Updates an event record in the database.

    Args:
        db: The SQLAlchemy database session.
        db_event: The existing event model instance from the database.
        update_data: A Pydantic schema with the fields to update.

    Returns:
        The updated event model instance.
    """
    # Get the update data as a dictionary, excluding any fields that were not set.
    # This allows for partial updates (PATCH behavior).
    update_dict = update_data.model_dump(exclude_unset=True)

    for key, value in update_dict.items():
        setattr(db_event, key, value)

    db.commit()
    db.refresh(db_event)
    return db_event

def get_assignment(db: Session, assignment_id: int):
    """Fetches a single assignment by its ID."""
    return db.query(models.Assignment).filter(models.Assignment.id == assignment_id).first()

def update_assignment(db: Session, db_assignment: models.Assignment, update_data: schemas.UpdateAssignment) -> models.Assignment:
    """
    Updates an assignment record in the database.

    Args:
        db: The SQLAlchemy database session.
        db_assignment: The existing assignment model instance from the database.
        update_data: A Pydantic schema with the fields to update.

    Returns:
        The updated assignment model instance.
    """
    update_dict = update_data.model_dump(exclude_unset=True)

    for key, value in update_dict.items():
        setattr(db_assignment, key, value)

    db.commit()
    db.refresh(db_assignment)
    return db_assignment
