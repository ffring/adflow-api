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


class AnswersSubmit(BaseModel):
    """Answers to client interview questions."""

    answers: dict


class RegenerateRequest(BaseModel):
    """Request to regenerate a creative."""

    creative_id: str
    feedback: Optional[str] = None


class VariationRequest(BaseModel):
    """Request to create a variation of a creative."""

    creative_id: str
    variation_type: str = "tone"  # tone, angle, length, cta


class GenerateMoreRequest(BaseModel):
    """Request to generate more creatives for a platform."""

    platform: str
    count: int = 3


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


@router.post("/{project_id}/answers")
async def submit_answers(project_id: str, data: AnswersSubmit, background_tasks: BackgroundTasks):
    """Submit answers to interview questions and continue pipeline."""
    project = projects_db.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status != ProjectStatus.QUESTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Project is not waiting for answers (current status: {project.status})"
        )

    # Continue pipeline with answers in background
    background_tasks.add_task(orchestrator.continue_after_answers, project, data.answers)

    return {
        "message": "Answers received, continuing pipeline",
        "project_id": project_id,
        "answers_count": len(data.answers),
    }


@router.post("/{project_id}/creatives/regenerate")
async def regenerate_creative(project_id: str, data: RegenerateRequest):
    """Regenerate a specific creative with optional feedback."""
    project = projects_db.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status != ProjectStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Cannot regenerate creatives until pipeline is complete"
        )

    try:
        result = await orchestrator.regenerate_creative(
            project, data.creative_id, data.feedback or ""
        )
        return {
            "message": "Creative regenerated",
            "creative_id": data.creative_id,
            "creatives": result.model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/creatives/variation")
async def create_creative_variation(project_id: str, data: VariationRequest):
    """Create a variation of a specific creative."""
    project = projects_db.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status != ProjectStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Cannot create variations until pipeline is complete"
        )

    if data.variation_type not in ["tone", "angle", "length", "cta"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid variation type. Must be one of: tone, angle, length, cta"
        )

    try:
        result = await orchestrator.create_variation(
            project, data.creative_id, data.variation_type
        )
        return {
            "message": f"Variation ({data.variation_type}) created",
            "creative_id": data.creative_id,
            "creatives": result.model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/creatives/generate-more")
async def generate_more_creatives(project_id: str, data: GenerateMoreRequest):
    """Generate more creatives for a specific platform."""
    project = projects_db.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.status != ProjectStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Cannot generate more creatives until pipeline is complete"
        )

    valid_platforms = [
        "yandex_direct", "vk_ads", "telegram_ads", "telegram_seeding",
        "yandex_business", "vk_market"
    ]
    if data.platform not in valid_platforms:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid platform. Must be one of: {', '.join(valid_platforms)}"
        )

    if not 1 <= data.count <= 10:
        raise HTTPException(
            status_code=400,
            detail="Count must be between 1 and 10"
        )

    try:
        result = await orchestrator.generate_more(project, data.platform, data.count)
        return {
            "message": f"Generated {data.count} more creatives for {data.platform}",
            "platform": data.platform,
            "count": data.count,
            "creatives": result.model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Legacy endpoint for backward compatibility
@router.post("/{project_id}/answer")
async def submit_answers_legacy(project_id: str, answers: dict, background_tasks: BackgroundTasks):
    """Submit answers to PM questions (legacy endpoint)."""
    return await submit_answers(project_id, AnswersSubmit(answers=answers), background_tasks)
