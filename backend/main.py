from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, time
from enum import Enum

app = FastAPI()

# In-memory data structures for tasks, availability, and logs:
tasks_db = []
availability_db = []
work_log_db = []

# Task Model
class Task(BaseModel):
    id: int
    user_id: int
    title: str
    subject: str
    due_date: datetime
    priority: int = Field(..., ge=1, le=3)
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from datetime import datetime, time
from enum import Enum

app = FastAPI()

# In-memory data structures for tasks, availability, and logs:
tasks_db = []
availability_db = []
work_log_db = []

# Task Model
class Task(BaseModel):
    id: int
    user_id: int
    title: str
    subject: str
    due_date: datetime
    priority: int = Field(..., ge=1, le=3)
    estimated_minutes: int
    remaining_minutes: int
    status: str
    created_at: datetime
    updated_at: datetime

# Availability Model
class AvailabilityWindow(BaseModel):
    id: int
    user_id: int
    date: datetime
    start_time: time
    end_time: time

# Schedule Block Type
class BlockType(str, Enum):
    work = "work"
    break_ = "break"

# Schedule Block
class ScheduleBlock(BaseModel):
    start_datetime: datetime
    end_datetime: datetime
    type: BlockType
    task_id: Optional[int] = None
    label: Optional[str] = None

# WorkLog Model
class WorkLog(BaseModel):
    id: int
    user_id: int
    task_id: int
    timestamp: datetime
    planned_minutes: Optional[int] = None
    actual_minutes: int

# Endpoints for managing tasks
@app.get("/tasks", response_model=List[Task])
async def list_tasks():
    return tasks_db

@app.post("/tasks", response_model=Task)
async def create_task(task: Task):
    tasks_db.append(task)
    return task

@app.patch("/tasks/{id}", response_model=Task)
async def update_task(id: int, task: Task):
    for t in tasks_db:
        if t.id == id:
            t.priority = task.priority
            t.estimated_minutes = task.estimated_minutes
            t.status = task.status
            return t
    raise HTTPException(status_code=404, detail="Task not found")

@app.delete("/tasks/{id}")
async def delete_task(id: int):
    global tasks_db
    tasks_db = [t for t in tasks_db if t.id != id]
    return {"detail": "Task deleted"}

# Placeholder function for generating a schedule
@app.post("/schedule/today/generate")
async def generate_schedule():
    # Logic to generate schedule goes here
    return {"detail": "Schedule generated"}

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
    estimated_minutes: int
    remaining_minutes: int
    status: str
    created_at: datetime
    updated_at: datetime

# Availability Model
class AvailabilityWindow(BaseModel):
    id: int
    user_id: int
    date: datetime
    start_time: time
    end_time: time

# Schedule Block Type
class BlockType(str, Enum):
    work = "work"
    break_ = "break"

# Schedule Block
class ScheduleBlock(BaseModel):
    start_datetime: datetime
    end_datetime: datetime
    type: BlockType
    task_id: Optional[int] = None
    label: Optional[str] = None

# WorkLog Model
class WorkLog(BaseModel):
    id: int
    user_id: int
    task_id: int
    timestamp: datetime
    planned_minutes: Optional[int] = None
    actual_minutes: int

# Endpoints for managing tasks
@app.get("/tasks", response_model=List[Task])
async def list_tasks():
    return tasks_db

@app.post("/tasks", response_model=Task)
async def create_task(task: Task):
    tasks_db.append(task)
    return task

@app.patch("/tasks/{id}", response_model=Task)
async def update_task(id: int, task: Task):
    for t in tasks_db:
        if t.id == id:
            t.priority = task.priority
            t.estimated_minutes = task.estimated_minutes
            t.status = task.status
            return t
    raise HTTPException(status_code=404, detail="Task not found")

@app.delete("/tasks/{id}")
async def delete_task(id: int):
    global tasks_db
    tasks_db = [t for t in tasks_db if t.id != id]
    return {"detail": "Task deleted"}

# Placeholder function for generating a schedule
@app.post("/schedule/today/generate")
async def generate_schedule():
    # Logic to generate schedule goes here
    return {"detail": "Schedule generated"}

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)