import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from models.project import Project, ProjectCreate, ProjectStatus
from core.orchestrator import orchestrator

router = APIRouter()

# In-memory storage for MVP (replace with DB)
projects_db: dict[str, Project] = {}


class ProjectResponse(BaseModel):
    project: Project


class ProjectListResponse(BaseModel):
    projects: list[Project]
    total: int


class ChatMessage(BaseModel):
    message: str
    stage: Optional[str] = None


@router.post("", response_model=ProjectResponse)
async def create_project(data: ProjectCreate, background_tasks: BackgroundTasks):
    """Create a new project and start analysis."""
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        user_id="user_1",  # TODO: get from auth
        name=data.name or f"Project {project_id[:8]}",
        url=str(data.url),
        status=ProjectStatus.CREATED,
    )
    projects_db[project_id] = project

    # Start pipeline in background
    background_tasks.add_task(orchestrator.run_pipeline, project)

    return ProjectResponse(project=project)


@router.get("", response_model=ProjectListResponse)
async def list_projects(user_id: str = "user_1"):
    """List all projects for a user."""
    user_projects = [p for p in projects_db.values() if p.user_id == user_id]
    user_projects.sort(key=lambda p: p.created_at, reverse=True)
    return ProjectListResponse(projects=user_projects, total=len(user_projects))


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str):
    """Get a project by ID."""
    project = projects_db.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(project=project)


@router.get("/{project_id}/status")
async def get_project_status(project_id: str):
    """Get current pipeline status."""
    project = projects_db.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return {
        "project_id": project_id,
        "status": project.status,
        "current_stage": project.current_stage,
        "error_message": project.error_message,
    }


@router.get("/{project_id}/stream")
async def stream_project_updates(project_id: str):
    """SSE stream for real-time pipeline updates."""

    async def event_generator():
        import asyncio

        while True:
            project = projects_db.get(project_id)
            if not project:
                yield f"data: {{'error': 'Project not found'}}\n\n"
                break

            yield f"data: {{'status': '{project.status}', 'stage': {project.current_stage}}}\n\n"

            if project.status in [ProjectStatus.COMPLETED, ProjectStatus.FAILED]:
                break

            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{project_id}/start")
async def start_pipeline(project_id: str, background_tasks: BackgroundTasks):
    """Start or restart the pipeline for a project."""
    project = projects_db.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status not in [ProjectStatus.CREATED, ProjectStatus.FAILED]:
        raise HTTPException(status_code=400, detail="Pipeline already running or completed")

    project.status = ProjectStatus.ANALYZING
    project.updated_at = datetime.utcnow()

    background_tasks.add_task(orchestrator.run_pipeline, project)

    return {"message": "Pipeline started", "project_id": project_id}


@router.post("/{project_id}/chat")
async def send_chat_message(project_id: str, data: ChatMessage):
    """Send a message to adjust the current stage."""
    project = projects_db.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # TODO: Process chat message through PM agent
    # For now, just acknowledge
    return {
        "message": "Message received",
        "user_message": data.message,
        "stage": data.stage or project.status,
    }


@router.post("/{project_id}/answer")
async def submit_answers(project_id: str, answers: dict):
    """Submit answers to PM questions."""
    project = projects_db.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # TODO: Process answers and continue pipeline
    return {"message": "Answers received", "project_id": project_id}
