from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from betatester.betatester_types import (
    Action,
    FileClient,
    ModelChat,
    ScrapeFiles,
    ScrapeVariables,
)
from pydantic import BaseModel, Field, computed_field

from betatester import ScrapeExecutor
from betatester_web_service.utils import model_client, settings


class ConfigBase(BaseModel):
    url: str
    name: str
    high_level_goal: str
    max_page_views: int
    max_total_actions: int
    max_action_attempts_per_step: int
    viewport_width: int
    viewport_height: int
    variables: ScrapeVariables
    files: ScrapeFiles


class TestConfig(ConfigBase):
    config_id: UUID

    def scrape_executor(
        self, scrape_id: UUID, file_client: FileClient
    ) -> ScrapeExecutor:
        return ScrapeExecutor(
            scrape_id=scrape_id,
            url=self.url,
            high_level_goal=self.high_level_goal,
            max_page_views=self.max_page_views,
            max_total_actions=self.max_total_actions,
            max_action_attempts_per_step=self.max_action_attempts_per_step,
            viewport_width=self.viewport_width,
            viewport_height=self.viewport_height,
            variables=self.variables,
            files=self.files,
            openai_api_key=settings.openai_api_key,
            model_client=model_client,
            file_client=file_client,
            save_playwright_trace=True,
        )


class UpsertConfig(ConfigBase):
    config_id: Optional[UUID] = None


class TestConfigMetadata(BaseModel):
    config_id: UUID
    name: str
    url: str
    last_updated: str


class ScrapeStatus(str, Enum):
    running = "running"
    completed = "completed"
    failed = "failed"
    stopped = "stopped"


class RunStep(BaseModel):
    step_id: UUID
    next_step: str
    action: Optional[Action]
    action_count: Optional[int]
    status: ScrapeStatus
    debug_next_step_chat: Optional[list[ModelChat]]
    debug_choose_action_chat: Optional[list[ModelChat]]
    start_timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    @staticmethod
    def _process_debug_chat(
        chat: Optional[list[dict]],
    ) -> Optional[list[ModelChat]]:
        if chat is None:
            return None
        else:
            return [ModelChat.from_serialized(msg) for msg in chat]

    @classmethod
    def from_serialized(cls, serialized: dict) -> "RunStep":
        return cls(
            step_id=serialized["step_id"],
            next_step=serialized["next_step"],
            action=(
                Action(**serialized["action"])
                if serialized["action"] is not None
                else None
            ),
            action_count=serialized["action_count"],
            status=ScrapeStatus(serialized["status"]),
            debug_next_step_chat=cls._process_debug_chat(
                serialized["debug_next_step_chat"]
            ),
            debug_choose_action_chat=cls._process_debug_chat(
                serialized["debug_choose_action_chat"]
            ),
            start_timestamp=serialized["start_timestamp"],
            timestamp=serialized["timestamp"],
        )


class RunEventMetadata(BaseModel):
    id: UUID
    config_id: UUID
    url: str
    high_level_goal: str
    status: ScrapeStatus
    start_timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    page_views: int = 0
    action_count: int = 0
    max_page_views: Optional[int]
    max_total_actions: Optional[int]
    fail_reason: Optional[str] = None

    @computed_field
    @property
    def trace_url(self) -> str:
        return f"https://trace.playwright.dev/?trace={settings.base_url}/data/trace/{self.id}.zip"


class RunMessage(RunEventMetadata):
    steps: list[RunStep]

    def _upsert_step(
        self,
        step: RunStep,
        next_step: Optional[str] = None,
        action: Optional[Action] = None,
        action_count: Optional[int] = None,
        debug_next_step_chat: Optional[list[ModelChat]] = None,
        debug_choose_action_chat: Optional[list[ModelChat]] = None,
    ) -> RunStep:
        if next_step is not None:
            step.next_step = next_step
        if action is not None:
            step.action = action
        if action_count is not None:
            step.action_count = action_count
        if debug_next_step_chat is not None:
            step.debug_next_step_chat = debug_next_step_chat
        if debug_choose_action_chat is not None:
            step.debug_choose_action_chat = debug_choose_action_chat
        step.timestamp = datetime.now().isoformat()
        return step

    def update_metadata(
        self,
        page_views: Optional[int] = None,
        action_count: Optional[int] = None,
    ) -> None:
        if page_views is not None:
            self.page_views = page_views
        if action_count is not None:
            self.action_count = action_count
        self.timestamp = datetime.now().isoformat()

    def add_step(
        self,
        step_id: UUID,
        next_step: Optional[str] = None,
        action: Optional[Action] = None,
        action_count: Optional[int] = None,
        debug_next_step_chat: Optional[list[ModelChat]] = None,
        debug_choose_action_chat: Optional[list[ModelChat]] = None,
    ) -> None:
        new_steps = []
        step_found = False
        for step in self.steps:
            if step.step_id == step_id:
                step_found = True
                step = self._upsert_step(
                    step,
                    next_step,
                    action,
                    action_count,
                    debug_next_step_chat,
                    debug_choose_action_chat,
                )
            new_steps.append(step)

        if not step_found:
            new_steps.append(
                self._upsert_step(
                    RunStep(
                        step_id=step_id,
                        next_step="",
                        action=None,
                        action_count=None,
                        status=ScrapeStatus.running,
                        debug_choose_action_chat=None,
                        debug_next_step_chat=None,
                    ),
                    next_step,
                )
            )
        self.steps = new_steps

    def _step_status_update(self):
        if (
            len(self.steps) > 0
            and self.steps[-1].status == ScrapeStatus.running
        ):
            self.steps[-1].status = self.status
            self.steps[-1].timestamp = self.timestamp

    def _cleanup(self, status: ScrapeStatus) -> None:
        self.status = status
        self.timestamp = datetime.now().isoformat()
        self._step_status_update()

    def stop(self) -> None:
        self._cleanup(ScrapeStatus.stopped)

    def complete(self) -> None:
        self._cleanup(ScrapeStatus.completed)

    def fail(self, fail_reason: str) -> None:
        self.fail_reason = fail_reason
        self._cleanup(ScrapeStatus.failed)

    def step_failed(self) -> None:
        if (
            len(self.steps) > 0
            and self.steps[-1].status == ScrapeStatus.running
        ):
            self.steps[-1].status = ScrapeStatus.failed
            self.steps[-1].timestamp = datetime.now().isoformat()

    @property
    def metadata(self) -> RunEventMetadata:
        return RunEventMetadata(
            id=self.id,
            config_id=self.config_id,
            url=self.url,
            high_level_goal=self.high_level_goal,
            status=self.status,
            start_timestamp=self.start_timestamp,
            timestamp=self.timestamp,
            page_views=self.page_views,
            action_count=self.action_count,
            max_page_views=self.max_page_views,
            max_total_actions=self.max_total_actions,
        )


class TestConfigResponse(BaseModel):
    history: list[RunEventMetadata]
    config: TestConfig
