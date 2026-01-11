from sqlalchemy.orm import Session

import models
import schemas


def get_event(db: Session, event_id: int):
    """Fetches a single event by its ID."""
    return db.query(models.Event).filter(models.Event.id == event_id).first()


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