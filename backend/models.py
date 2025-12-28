from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class EventType(str, Enum):
    SCHOOL_TASK = "school_task"
    GENERAL_EVENT = "general_event"

# Basic Task Model
class Event(BaseModel):
    id: int
    user_id: int
    title: str
    start_datetime: datetime
    end_datetime: datetime
    event_type: EventType
    subject: Optional[str] = None  # Specific to school tasks
    priority: Optional[int] = Field(None, ge=1, le=5)  # Specific to school tasks
    description: Optional[str] = None  # Specific to general events
    estimated_minutes: Optional[int] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
# Basic Calendar Event Model


# In-memory databases
events_db: List[Event] = []
