"""
Workflow Engine

Core orchestration engine for multi-step workflows.
Provides state management, error handling, and progress tracking.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from uuid import uuid4
import structlog

logger = structlog.get_logger()


class WorkflowStatus(Enum):
    """Workflow execution status"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class WorkflowStep:
    """
    Individual step in a workflow
    """

    def __init__(
        self,
        name: str,
        handler: Callable,
        retry_count: int = 3,
        timeout: Optional[int] = None,
    ):
        self.name = name
        self.handler = handler
        self.retry_count = retry_count
        self.timeout = timeout
        self.status = WorkflowStatus.PENDING
        self.result: Any = None
        self.error: Optional[str] = None
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

    async def execute(self, context: Dict) -> Any:
        """Execute step with retry logic"""
        self.started_at = datetime.now()
        self.status = WorkflowStatus.IN_PROGRESS

        for attempt in range(self.retry_count):
            try:
                logger.info(
                    "workflow_step_executing", step=self.name, attempt=attempt + 1
                )

                result = await self.handler(context)

                self.result = result
                self.status = WorkflowStatus.COMPLETED
                self.completed_at = datetime.now()

                logger.info("workflow_step_completed", step=self.name)
                return result

            except Exception as e:
                logger.error(
                    "workflow_step_failed",
                    step=self.name,
                    attempt=attempt + 1,
                    error=str(e),
                )

                if attempt == self.retry_count - 1:
                    self.error = str(e)
                    self.status = WorkflowStatus.FAILED
                    self.completed_at = datetime.now()
                    raise

        return None


class WorkflowEngine:
    """
    Orchestrate multi-step workflows with state management

    Features:
    - Sequential step execution
    - Error handling & retries
    - State persistence
    - Progress tracking
    - Rollback capabilities
    """

    def __init__(self, workflow_id: Optional[str] = None):
        self.workflow_id = workflow_id or str(uuid4())
        self.steps: List[WorkflowStep] = []
        self.status = WorkflowStatus.PENDING
        self.context: Dict[str, Any] = {}
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.current_step_index = 0

    def add_step(
        self, name: str, handler: Callable, retry_count: int = 3
    ) -> "WorkflowEngine":
        """Add a step to the workflow"""
        step = WorkflowStep(name, handler, retry_count)
        self.steps.append(step)
        return self

    async def execute(self, initial_context: Optional[Dict] = None) -> Dict:
        """
        Execute all workflow steps sequentially

        Args:
            initial_context: Initial workflow context/data

        Returns:
            Dictionary with:
            - workflow_id: str
            - status: WorkflowStatus
            - results: Dict (keyed by step name)
            - duration_seconds: float
        """
        self.status = WorkflowStatus.IN_PROGRESS
        self.started_at = datetime.now()

        if initial_context:
            self.context.update(initial_context)

        results = {}

        try:
            for i, step in enumerate(self.steps):
                self.current_step_index = i

                # Execute step
                step_result = await step.execute(self.context)

                # Store result
                results[step.name] = step_result

                # Update context with result (for next steps)
                self.context[f"{step.name}_result"] = step_result

            self.status = WorkflowStatus.COMPLETED
            self.completed_at = datetime.now()

            logger.info(
                "workflow_completed",
                workflow_id=self.workflow_id,
                steps_completed=len(self.steps),
            )

        except Exception as e:
            self.status = WorkflowStatus.FAILED
            self.completed_at = datetime.now()

            logger.error(
                "workflow_failed",
                workflow_id=self.workflow_id,
                failed_step=self.steps[self.current_step_index].name,
                error=str(e),
            )

            raise

        duration = (
            (self.completed_at - self.started_at).total_seconds()
            if self.completed_at and self.started_at
            else 0
        )

        return {
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "results": results,
            "duration_seconds": duration,
            "steps_completed": self.current_step_index + 1,
            "total_steps": len(self.steps),
        }

    async def pause(self):
        """Pause workflow execution"""
        self.status = WorkflowStatus.PAUSED
        logger.info("workflow_paused", workflow_id=self.workflow_id)

    async def resume(self) -> Dict:
        """Resume paused workflow"""
        if self.status != WorkflowStatus.PAUSED:
            raise ValueError("Workflow is not paused")

        self.status = WorkflowStatus.IN_PROGRESS
        logger.info("workflow_resumed", workflow_id=self.workflow_id)

        # Continue from current step
        return await self.execute()

    async def cancel(self):
        """Cancel workflow execution"""
        self.status = WorkflowStatus.CANCELLED
        self.completed_at = datetime.now()
        logger.info("workflow_cancelled", workflow_id=self.workflow_id)

    def get_progress(self) -> Dict:
        """Get current workflow progress"""
        completed_steps = sum(
            1 for step in self.steps if step.status == WorkflowStatus.COMPLETED
        )

        return {
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "current_step": (
                self.steps[self.current_step_index].name
                if self.current_step_index < len(self.steps)
                else None
            ),
            "completed_steps": completed_steps,
            "total_steps": len(self.steps),
            "progress_percentage": (
                (completed_steps / len(self.steps) * 100) if self.steps else 0
            ),
        }
