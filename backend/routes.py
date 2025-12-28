from typing import List

from fastapi import APIRouter, HTTPException

from models import Event, events_db # Ensure this import is correct

router = APIRouter()

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