import uuid
from datetime import datetime
from typing import Optional, Callable, Any
from pydantic import BaseModel

from models.project import Project, ProjectStatus, ProjectBrief, ProjectSettings
from models.artifact import Artifact, ArtifactType, ArtifactStatus
from models.strategy import Strategy, HypothesesArtifact
from models.creative import CreativeSet
from agents.base import AgentTask, TaskType, ReviewResult
from agents.pm import ProjectManagerAgent, AnalysisResult
from agents.strategist import StrategistAgent
from agents.copywriter import CopywriterAgent
from agents.designer import DesignerAgent, BannerSet
from services.parser import parser_service
from routes.artifacts import save_artifact, get_latest_artifact


class PipelineStage(BaseModel):
    """A stage in the pipeline."""

    name: str
    status: str = "pending"
    artifact_type: Optional[ArtifactType] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class Orchestrator:
    """Orchestrates the multi-agent pipeline."""

    def __init__(self):
        self.pm = ProjectManagerAgent()
        self.strategist = StrategistAgent()
        self.copywriter = CopywriterAgent()
        self.designer = DesignerAgent()

        self.max_revisions = 3
        self.event_callbacks: list[Callable] = []

    def on_event(self, callback: Callable):
        """Register event callback."""
        self.event_callbacks.append(callback)

    def _emit_event(self, event_type: str, data: Any):
        """Emit event to all callbacks."""
        for cb in self.event_callbacks:
            try:
                cb(event_type, data)
            except Exception:
                pass

    async def run_pipeline(self, project: Project):
        """Run the full creative generation pipeline."""
        try:
            # Stage 1: Analyze source
            project.status = ProjectStatus.ANALYZING
            project.current_stage = 1
            self._emit_event("stage_start", {"stage": 1, "name": "analyzing"})

            analysis = await self._stage_analyze(project)
            project.brief = analysis.brief

            # Stage 2: Wait for user answers (if questions)
            if analysis.questions:
                project.status = ProjectStatus.QUESTIONS
                self._emit_event("questions_ready", {"questions": analysis.questions})
                # In real implementation, would wait for user answers
                # For MVP, continue with defaults
                project.settings = ProjectSettings(
                    budget_monthly=50000,
                    goals=["leads", "sales"],
                    target_audience_description="",
                )

            # Stage 3: Create strategy
            project.status = ProjectStatus.STRATEGY
            project.current_stage = 2
            self._emit_event("stage_start", {"stage": 2, "name": "strategy"})

            strategy = await self._stage_strategy(project)

            # Stage 4: Create hypotheses
            project.status = ProjectStatus.HYPOTHESES
            project.current_stage = 3
            self._emit_event("stage_start", {"stage": 3, "name": "hypotheses"})

            hypotheses = await self._stage_hypotheses(project, strategy)

            # Stage 5: Create copy
            project.status = ProjectStatus.COPYWRITING
            project.current_stage = 4
            self._emit_event("stage_start", {"stage": 4, "name": "copywriting"})

            creatives = await self._stage_copywriting(project, strategy, hypotheses)

            # Stage 6: Create banners
            project.status = ProjectStatus.DESIGN
            project.current_stage = 5
            self._emit_event("stage_start", {"stage": 5, "name": "design"})

            banners = await self._stage_design(project, strategy, creatives)

            # Stage 7: Finalize
            project.status = ProjectStatus.COMPLETED
            project.current_stage = 6
            self._emit_event("pipeline_complete", {"project_id": project.id})

        except Exception as e:
            project.status = ProjectStatus.FAILED
            project.error_message = str(e)
            self._emit_event("pipeline_error", {"error": str(e)})
            raise

    async def _stage_analyze(self, project: Project) -> AnalysisResult:
        """Stage 1: Analyze website/channel."""
        # Parse the source
        parsed = await parser_service.parse(project.url)

        # PM analyzes
        task = AgentTask(
            task_type=TaskType.ANALYZE,
            description="Analyze source and create brief",
            input_data=parsed.model_dump() if hasattr(parsed, "model_dump") else parsed,
        )

        response = await self.pm.execute(task)
        if not response.success:
            raise Exception(f"Analysis failed: {response.error_message}")

        result: AnalysisResult = response.output

        # Save artifact
        artifact = Artifact(
            id=str(uuid.uuid4()),
            project_id=project.id,
            type=ArtifactType.BRIEF,
            status=ArtifactStatus.APPROVED,
            content=result.brief.model_dump(),
            agent_name=self.pm.name,
        )
        save_artifact(artifact)

        if result.questions:
            questions_artifact = Artifact(
                id=str(uuid.uuid4()),
                project_id=project.id,
                type=ArtifactType.QUESTIONS,
                status=ArtifactStatus.PENDING,
                content={"questions": [q.model_dump() for q in result.questions]},
                agent_name=self.pm.name,
            )
            save_artifact(questions_artifact)

        return result

    async def _stage_strategy(self, project: Project) -> Strategy:
        """Stage 2: Create marketing strategy."""
        task = AgentTask(
            task_type=TaskType.CREATE,
            description="Create marketing strategy",
            context={
                "brief": project.brief.model_dump() if project.brief else {},
                "settings": project.settings.model_dump() if project.settings else {},
            },
        )

        # Create strategy with review loop
        strategy = await self._create_with_review(
            agent=self.strategist,
            task=task,
            artifact_type=ArtifactType.STRATEGY,
            project_id=project.id,
            review_criteria=[
                "Соответствие брифу и целям клиента",
                "Рациональное распределение бюджета",
                "Правильный выбор площадок",
                "Чёткая сегментация аудитории",
            ],
        )

        return strategy

    async def _stage_hypotheses(self, project: Project, strategy: Strategy) -> HypothesesArtifact:
        """Stage 3: Create testing hypotheses."""
        task = AgentTask(
            task_type=TaskType.CREATE,
            description="Create testing hypotheses",
            context={
                "output_type": "hypotheses",
                "strategy": strategy.model_dump(),
                "brief": project.brief.model_dump() if project.brief else {},
            },
        )

        hypotheses = await self._create_with_review(
            agent=self.strategist,
            task=task,
            artifact_type=ArtifactType.HYPOTHESES,
            project_id=project.id,
            review_criteria=[
                "Гипотезы соответствуют стратегии",
                "Разнообразие углов тестирования",
                "Реалистичное количество креативов",
                "Правильное распределение по платформам",
            ],
        )

        return hypotheses

    async def _stage_copywriting(
        self, project: Project, strategy: Strategy, hypotheses: HypothesesArtifact
    ) -> CreativeSet:
        """Stage 4: Create ad copy."""
        task = AgentTask(
            task_type=TaskType.CREATE,
            description="Create ad copy for all hypotheses",
            context={
                "hypotheses": hypotheses.model_dump(),
                "strategy": strategy.model_dump(),
                "brief": project.brief.model_dump() if project.brief else {},
            },
        )

        creatives = await self._create_with_review(
            agent=self.copywriter,
            task=task,
            artifact_type=ArtifactType.COPY,
            project_id=project.id,
            review_criteria=[
                "Соблюдение лимитов символов",
                "Соответствие гипотезам",
                "Качество текстов",
                "Разнообразие вариантов",
                "Соответствие требованиям модерации",
            ],
        )

        return creatives

    async def _stage_design(
        self, project: Project, strategy: Strategy, creatives: CreativeSet
    ) -> BannerSet:
        """Stage 5: Create banners."""
        task = AgentTask(
            task_type=TaskType.CREATE,
            description="Create banner images",
            context={
                "creatives": creatives,
                "strategy": strategy.model_dump(),
                "brief": project.brief.model_dump() if project.brief else {},
            },
        )

        banners = await self._create_with_review(
            agent=self.designer,
            task=task,
            artifact_type=ArtifactType.BANNERS,
            project_id=project.id,
            review_criteria=[
                "Правильные размеры баннеров",
                "Читаемость текста",
                "Соответствие стилю бренда",
            ],
        )

        return banners

    async def _create_with_review(
        self,
        agent,
        task: AgentTask,
        artifact_type: ArtifactType,
        project_id: str,
        review_criteria: list[str],
    ) -> Any:
        """Create artifact with PM review loop."""
        revisions = 0

        while revisions < self.max_revisions:
            # Agent creates
            response = await agent.execute(task)
            if not response.success:
                raise Exception(f"Agent {agent.name} failed: {response.error_message}")

            output = response.output

            # Save artifact (in_progress)
            artifact = Artifact(
                id=str(uuid.uuid4()),
                project_id=project_id,
                type=artifact_type,
                status=ArtifactStatus.REVIEW,
                version=revisions + 1,
                content=output.model_dump() if hasattr(output, "model_dump") else output,
                agent_name=agent.name,
            )
            save_artifact(artifact)

            # PM reviews
            review_task = AgentTask(
                task_type=TaskType.REVIEW,
                description=f"Review {artifact_type.value}",
                input_data=output.model_dump() if hasattr(output, "model_dump") else output,
                context={
                    "work_type": artifact_type.value,
                    "criteria": review_criteria,
                },
            )

            review_response = await self.pm.execute(review_task)
            if not review_response.success:
                # If review fails, just accept the work
                artifact.status = ArtifactStatus.APPROVED
                return output

            review: ReviewResult = review_response.output

            if review.approved or review.score >= 8:
                # Approved!
                artifact.status = ArtifactStatus.APPROVED
                self._emit_event(
                    "artifact_approved",
                    {"type": artifact_type.value, "score": review.score},
                )
                return output

            # Need revision
            revisions += 1
            artifact.status = ArtifactStatus.REVISION
            artifact.review_notes = review.feedback

            self._emit_event(
                "artifact_revision",
                {
                    "type": artifact_type.value,
                    "revision": revisions,
                    "feedback": review.feedback,
                },
            )

            # Update task for revision
            task = AgentTask(
                task_type=TaskType.REVISE,
                description=f"Revise {artifact_type.value}",
                input_data=output,
                context={
                    **task.context,
                    "feedback": review.revision_instructions or review.feedback,
                    "output_type": task.context.get("output_type"),
                },
            )

        # Max revisions reached, accept last version
        return output


# Global instance
orchestrator = Orchestrator()
