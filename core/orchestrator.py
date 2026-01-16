import uuid
from datetime import datetime
from typing import Optional, Callable, Any
from pydantic import BaseModel

from models.project import Project, ProjectStatus, ProjectBrief, ProjectSettings
from models.artifact import Artifact, ArtifactType, ArtifactStatus, ClientInterview, QuestionsArtifact
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

        # Storage for waiting projects (waiting for user answers)
        self.waiting_projects: dict[str, dict] = {}

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
                project.current_stage = 2
                self._emit_event("questions_ready", {
                    "project_id": project.id,
                    "questions": [q.model_dump() for q in analysis.questions]
                })

                # Store analysis for later continuation
                self.waiting_projects[project.id] = {
                    "analysis": analysis,
                    "stage": "questions"
                }

                # Pipeline pauses here - will continue when user submits answers
                return

            # If no questions, continue with default interview
            interview = ClientInterview()
            await self._continue_pipeline(project, interview)

        except Exception as e:
            project.status = ProjectStatus.FAILED
            project.error_message = str(e)
            self._emit_event("pipeline_error", {"error": str(e)})
            raise

    async def continue_after_answers(self, project: Project, answers: dict):
        """Continue pipeline after user submits answers."""
        try:
            # Parse answers into ClientInterview structure
            interview = self._parse_answers_to_interview(answers)

            # Save interview to questions artifact
            questions_artifact = get_latest_artifact(project.id, ArtifactType.QUESTIONS)
            if questions_artifact:
                content = questions_artifact.content or {}
                content["interview"] = interview.model_dump()
                content["all_answered"] = True
                questions_artifact.content = content
                questions_artifact.status = ArtifactStatus.APPROVED
                save_artifact(questions_artifact)

            # Store interview in project settings
            project.settings = ProjectSettings(
                budget_monthly=interview.budget_monthly or 50000,
                goals=[interview.primary_goal] + interview.secondary_goals,
                target_audience_description=interview.target_audience_description,
            )

            # Continue pipeline
            await self._continue_pipeline(project, interview)

        except Exception as e:
            project.status = ProjectStatus.FAILED
            project.error_message = str(e)
            self._emit_event("pipeline_error", {"error": str(e)})
            raise

    def _parse_answers_to_interview(self, answers: dict) -> ClientInterview:
        """Parse user answers into ClientInterview structure."""
        interview = ClientInterview()

        # Parse budget
        if "budget" in answers:
            try:
                interview.budget_monthly = int(answers["budget"])
            except (ValueError, TypeError):
                pass

        if "budget_type" in answers:
            interview.budget_type = answers["budget_type"]

        # Parse goals
        if "primary_goal" in answers:
            interview.primary_goal = answers["primary_goal"]

        if "goals" in answers:
            if isinstance(answers["goals"], list):
                interview.secondary_goals = answers["goals"]
            else:
                interview.secondary_goals = [g.strip() for g in answers["goals"].split(",")]

        if "target_cpa" in answers:
            try:
                interview.target_cpa = int(answers["target_cpa"])
            except (ValueError, TypeError):
                pass

        # Parse audience
        if "target_audience" in answers:
            interview.target_audience_description = answers["target_audience"]

        if "geo" in answers:
            if isinstance(answers["geo"], list):
                interview.geo = answers["geo"]
            else:
                interview.geo = [g.strip() for g in answers["geo"].split(",")]

        if "age_range" in answers:
            interview.age_range = answers["age_range"]

        if "gender" in answers:
            interview.gender = answers["gender"]

        # Parse channel preferences
        if "preferred_platforms" in answers:
            if isinstance(answers["preferred_platforms"], list):
                interview.preferred_platforms = answers["preferred_platforms"]
            else:
                interview.preferred_platforms = [p.strip() for p in answers["preferred_platforms"].split(",")]

        if "excluded_platforms" in answers:
            if isinstance(answers["excluded_platforms"], list):
                interview.excluded_platforms = answers["excluded_platforms"]
            else:
                interview.excluded_platforms = [p.strip() for p in answers["excluded_platforms"].split(",")]

        if "has_telegram_channel" in answers:
            interview.has_telegram_channel = answers["has_telegram_channel"] in [True, "true", "yes", "да", "1"]

        if "telegram_channel_url" in answers:
            interview.telegram_channel_url = answers["telegram_channel_url"]

        # Parse restrictions and experience
        if "restrictions" in answers:
            if isinstance(answers["restrictions"], list):
                interview.restrictions = answers["restrictions"]
            elif answers["restrictions"]:
                interview.restrictions = [answers["restrictions"]]

        if "previous_experience" in answers:
            interview.previous_experience = answers["previous_experience"]

        if "what_worked" in answers:
            interview.what_worked_before = answers["what_worked"]

        if "what_failed" in answers:
            interview.what_failed_before = answers["what_failed"]

        return interview

    async def _continue_pipeline(self, project: Project, interview: ClientInterview):
        """Continue pipeline after questions stage."""

        # Stage 3: Create strategy (with interview data!)
        project.status = ProjectStatus.STRATEGY
        project.current_stage = 3
        self._emit_event("stage_start", {"stage": 3, "name": "strategy"})

        strategy = await self._stage_strategy(project, interview)

        # Stage 4: Create hypotheses
        project.status = ProjectStatus.HYPOTHESES
        project.current_stage = 4
        self._emit_event("stage_start", {"stage": 4, "name": "hypotheses"})

        hypotheses = await self._stage_hypotheses(project, strategy, interview)

        # Stage 5: Create copy (unique per channel!)
        project.status = ProjectStatus.COPYWRITING
        project.current_stage = 5
        self._emit_event("stage_start", {"stage": 5, "name": "copywriting"})

        creatives = await self._stage_copywriting(project, strategy, hypotheses)

        # Stage 6: Create banners (only for platforms that need them)
        project.status = ProjectStatus.DESIGN
        project.current_stage = 6
        self._emit_event("stage_start", {"stage": 6, "name": "design"})

        banners = await self._stage_design(project, strategy, creatives)

        # Stage 7: Finalize
        project.status = ProjectStatus.COMPLETED
        project.current_stage = 7
        self._emit_event("pipeline_complete", {"project_id": project.id})

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

    async def _stage_strategy(self, project: Project, interview: ClientInterview) -> Strategy:
        """Stage 2: Create marketing strategy based on interview."""
        task = AgentTask(
            task_type=TaskType.CREATE,
            description="Create marketing strategy based on client interview",
            context={
                "brief": project.brief.model_dump() if project.brief else {},
                "interview": interview.model_dump(),  # Full interview data!
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
                "Учёт бюджета и предпочтений по каналам",
                "Рациональное распределение бюджета",
                "Правильный выбор площадок с учётом интервью",
                "Чёткая сегментация аудитории",
            ],
        )

        return strategy

    async def _stage_hypotheses(
        self, project: Project, strategy: Strategy, interview: ClientInterview
    ) -> HypothesesArtifact:
        """Stage 3: Create testing hypotheses."""
        task = AgentTask(
            task_type=TaskType.CREATE,
            description="Create testing hypotheses for selected channels",
            context={
                "output_type": "hypotheses",
                "strategy": strategy.model_dump(),
                "interview": interview.model_dump(),
                "brief": project.brief.model_dump() if project.brief else {},
            },
        )

        hypotheses = await self._create_with_review(
            agent=self.strategist,
            task=task,
            artifact_type=ArtifactType.HYPOTHESES,
            project_id=project.id,
            review_criteria=[
                "Гипотезы соответствуют выбранным каналам",
                "Разнообразие углов тестирования",
                "Реалистичное количество креативов",
                "Правильное распределение по платформам",
                "Учёт особенностей каждого канала",
            ],
        )

        return hypotheses

    async def _stage_copywriting(
        self, project: Project, strategy: Strategy, hypotheses: HypothesesArtifact
    ) -> CreativeSet:
        """Stage 4: Create ad copy unique for each channel."""
        task = AgentTask(
            task_type=TaskType.CREATE,
            description="Create channel-specific ad copy for all hypotheses",
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
                "Соблюдение лимитов символов для каждой платформы",
                "Уникальность контента под каждый канал",
                "Для TG посевов - нативный стиль постов",
                "Для TG Ads - компактные 160 символов",
                "Для VK - вовлекающие тексты с CTA",
                "Для Яндекс - соответствие требованиям модерации",
                "Разнообразие вариантов для A/B тестов",
            ],
        )

        return creatives

    async def _stage_design(
        self, project: Project, strategy: Strategy, creatives: CreativeSet
    ) -> BannerSet:
        """Stage 5: Create banners for platforms that need them."""
        # Check which platforms need banners
        platforms_needing_banners = []
        for platform in strategy.platforms:
            if platform.enabled and platform.platform.value not in ["telegram_ads", "telegram_seeding"]:
                platforms_needing_banners.append(platform.platform.value)

        if not platforms_needing_banners:
            # No banners needed (e.g., TG Ads only)
            return BannerSet(banners=[], total_count=0)

        task = AgentTask(
            task_type=TaskType.CREATE,
            description="Create banner images for platforms that need them",
            context={
                "creatives": creatives,
                "strategy": strategy.model_dump(),
                "brief": project.brief.model_dump() if project.brief else {},
                "platforms_needing_banners": platforms_needing_banners,
            },
        )

        banners = await self._create_with_review(
            agent=self.designer,
            task=task,
            artifact_type=ArtifactType.BANNERS,
            project_id=project.id,
            review_criteria=[
                "Правильные размеры баннеров для каждой платформы",
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

    # === Methods for regeneration/variation ===

    async def regenerate_creative(self, project: Project, creative_id: str, feedback: str = "") -> CreativeSet:
        """Regenerate a specific creative with optional feedback."""
        # Get current creatives
        copy_artifact = get_latest_artifact(project.id, ArtifactType.COPY)
        if not copy_artifact:
            raise Exception("No creatives found")

        task = AgentTask(
            task_type=TaskType.REVISE,
            description=f"Regenerate creative {creative_id}",
            input_data=copy_artifact.content,
            context={
                "creative_id": creative_id,
                "feedback": feedback or "Создай новую вариацию этого креатива",
                "action": "regenerate_single",
            },
        )

        response = await self.copywriter.execute(task)
        if not response.success:
            raise Exception(f"Regeneration failed: {response.error_message}")

        # Update artifact
        copy_artifact.content = response.output.model_dump()
        copy_artifact.version += 1
        save_artifact(copy_artifact)

        return response.output

    async def create_variation(self, project: Project, creative_id: str, variation_type: str = "tone") -> CreativeSet:
        """Create a variation of a specific creative."""
        copy_artifact = get_latest_artifact(project.id, ArtifactType.COPY)
        if not copy_artifact:
            raise Exception("No creatives found")

        variation_instructions = {
            "tone": "Создай вариацию с другим тоном (более серьёзный/игривый/срочный)",
            "angle": "Создай вариацию с другим углом подачи (другой акцент на УТП)",
            "length": "Создай вариацию другой длины (короче/длиннее)",
            "cta": "Создай вариацию с другим призывом к действию",
        }

        task = AgentTask(
            task_type=TaskType.REVISE,
            description=f"Create {variation_type} variation for creative {creative_id}",
            input_data=copy_artifact.content,
            context={
                "creative_id": creative_id,
                "feedback": variation_instructions.get(variation_type, variation_instructions["tone"]),
                "action": "create_variation",
                "variation_type": variation_type,
            },
        )

        response = await self.copywriter.execute(task)
        if not response.success:
            raise Exception(f"Variation failed: {response.error_message}")

        # Update artifact
        copy_artifact.content = response.output.model_dump()
        copy_artifact.version += 1
        save_artifact(copy_artifact)

        return response.output

    async def generate_more(self, project: Project, platform: str, count: int = 3) -> CreativeSet:
        """Generate more creatives for a specific platform."""
        strategy_artifact = get_latest_artifact(project.id, ArtifactType.STRATEGY)
        copy_artifact = get_latest_artifact(project.id, ArtifactType.COPY)

        if not strategy_artifact or not copy_artifact:
            raise Exception("Strategy or creatives not found")

        task = AgentTask(
            task_type=TaskType.CREATE,
            description=f"Generate {count} more creatives for {platform}",
            context={
                "existing_creatives": copy_artifact.content,
                "strategy": strategy_artifact.content,
                "brief": project.brief.model_dump() if project.brief else {},
                "platform": platform,
                "count": count,
                "action": "generate_more",
            },
        )

        response = await self.copywriter.execute(task)
        if not response.success:
            raise Exception(f"Generation failed: {response.error_message}")

        # Merge with existing
        existing = copy_artifact.content.get("creatives", [])
        new_creatives = response.output.model_dump().get("creatives", [])
        copy_artifact.content["creatives"] = existing + new_creatives
        copy_artifact.version += 1
        save_artifact(copy_artifact)

        return response.output


# Global instance
orchestrator = Orchestrator()
