from datetime import datetime, time
from typing import Optional, List
from pydantic import BaseModel, Field

# Basic Task Model
class Task(BaseModel):
    id: int
    user_id: int
    title: str
    subject: str
    due_date: datetime
    priority: int = Field(..., ge=1, le=5)
    estimated_minutes: int
    remaining_minutes: int
    status: str
    created_at: datetime
    updated_at: datetime

# Basic Calendar Event Model
class CalendarEvent(BaseModel):
    id: int
    user_id: int
    title: str
    start_datetime: datetime
    end_datetime: datetime
    description: Optional[str] = None

tasks_db: List[Task] = []
events_db: List[CalendarEvent] = []