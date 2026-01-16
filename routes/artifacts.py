from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from models.artifact import Artifact, ArtifactType, ArtifactStatus

router = APIRouter()

# In-memory storage for MVP
artifacts_db: dict[str, list[Artifact]] = {}


class ArtifactResponse(BaseModel):
    artifact: Artifact


class ArtifactListResponse(BaseModel):
    artifacts: list[Artifact]


class ArtifactEditRequest(BaseModel):
    content: dict
    feedback: Optional[str] = None


@router.get("/project/{project_id}")
async def get_project_artifacts(project_id: str) -> ArtifactListResponse:
    """Get all artifacts for a project."""
    artifacts = artifacts_db.get(project_id, [])
    return ArtifactListResponse(artifacts=artifacts)


@router.get("/project/{project_id}/{artifact_type}")
async def get_artifact_by_type(project_id: str, artifact_type: ArtifactType) -> ArtifactResponse:
    """Get specific artifact type for a project."""
    artifacts = artifacts_db.get(project_id, [])

    # Find latest version of this type
    matching = [a for a in artifacts if a.type == artifact_type]
    if not matching:
        raise HTTPException(status_code=404, detail="Artifact not found")

    latest = max(matching, key=lambda a: a.version)
    return ArtifactResponse(artifact=latest)


@router.post("/project/{project_id}/{artifact_type}/edit")
async def edit_artifact(
    project_id: str, artifact_type: ArtifactType, data: ArtifactEditRequest
) -> ArtifactResponse:
    """User edits an artifact."""
    artifacts = artifacts_db.get(project_id, [])

    matching = [a for a in artifacts if a.type == artifact_type]
    if not matching:
        raise HTTPException(status_code=404, detail="Artifact not found")

    latest = max(matching, key=lambda a: a.version)

    # Create new version with user edits
    import uuid
    from datetime import datetime

    new_artifact = Artifact(
        id=str(uuid.uuid4()),
        project_id=project_id,
        type=artifact_type,
        status=ArtifactStatus.USER_EDITED,
        version=latest.version + 1,
        content=data.content,
        agent_name="user",
        user_feedback=data.feedback,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    artifacts_db[project_id].append(new_artifact)

    return ArtifactResponse(artifact=new_artifact)


@router.get("/{artifact_id}")
async def get_artifact(artifact_id: str) -> ArtifactResponse:
    """Get specific artifact by ID."""
    for artifacts in artifacts_db.values():
        for artifact in artifacts:
            if artifact.id == artifact_id:
                return ArtifactResponse(artifact=artifact)

    raise HTTPException(status_code=404, detail="Artifact not found")


# Helper function for other modules
def save_artifact(artifact: Artifact):
    """Save an artifact to storage."""
    if artifact.project_id not in artifacts_db:
        artifacts_db[artifact.project_id] = []
    artifacts_db[artifact.project_id].append(artifact)


def get_latest_artifact(project_id: str, artifact_type: ArtifactType) -> Optional[Artifact]:
    """Get latest version of an artifact type."""
    artifacts = artifacts_db.get(project_id, [])
    matching = [a for a in artifacts if a.type == artifact_type]
    if not matching:
        return None
    return max(matching, key=lambda a: a.version)
