import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from betatester.betatester_types import (
    Action,
    ExecutorMessage,
    ModelChat,
    ScrapeFiles,
    ScrapeVariables,
)
from cachetools import TTLCache
from fastapi import APIRouter, Response
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from betatester import ScrapeExecutor
from betatester_web_service.file import file_client
from betatester_web_service.task_manager import task_manager
from betatester_web_service.utils import model_client, settings

logger = logging.getLogger(__name__)

message_queues: dict[UUID, asyncio.Queue[ExecutorMessage]] = {}
scraper_info_cache: TTLCache[UUID, "RunMessage"] = TTLCache(
    maxsize=100, ttl=3600
)
scraper_info_cache_lock = asyncio.Lock()


router = APIRouter(
    prefix="/scraper",
    tags=["scraper"],
    responses={404: {"description": "Not found"}},
)


class RunRequest(BaseModel):
    url: str
    high_level_goal: str
    max_page_views: int = 10
    max_total_actions: int = 20
    max_action_attempts_per_step: int = 5
    viewport_width: int = 1280
    viewport_height: int = 720
    variables: ScrapeVariables = Field(default_factory=dict)
    files: ScrapeFiles = Field(default_factory=dict)


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


class RunEventMetadata(BaseModel):
    id: UUID
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
        message_queues[self.id].put_nowait(ExecutorMessage())

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


async def _run_scraper(scraper: ScrapeExecutor):
    async with scraper_info_cache_lock:
        scraper_info_cache[scraper.scrape_id] = RunMessage(
            id=scraper.scrape_id,
            url=scraper.url,
            high_level_goal=scraper.high_level_goal,
            status=ScrapeStatus.running,
            max_page_views=scraper.max_page_views,
            max_total_actions=scraper.max_total_actions,
            steps=[],
        )

    if scraper.scrape_id not in message_queues:
        message_queues[scraper.scrape_id] = asyncio.Queue()

    # subscribe to scraper
    scraper.subscriptions = set([message_queues[scraper.scrape_id]])

    try:
        await scraper.run()
        scraper_info_cache[scraper.scrape_id].complete()
    except Exception as e:
        scraper_info_cache[scraper.scrape_id].fail(str(e))


@router.post("/run")
async def run_scraper(request: RunRequest):
    scraper = ScrapeExecutor(
        url=request.url,
        high_level_goal=request.high_level_goal,
        openai_api_key=settings.openai_api_key,
        max_page_views=request.max_page_views,
        max_total_actions=request.max_total_actions,
        max_action_attempts_per_step=request.max_action_attempts_per_step,
        viewport_width=request.viewport_width,
        viewport_height=request.viewport_height,
        variables=request.variables,
        files=request.files,
        file_client=file_client,
        save_playwright_trace=True,
        model_client=model_client,
    )

    task_manager.add_task(
        str(scraper.scrape_id),
        _run_scraper,
        scraper,
    )

    return {"scrape_id": scraper.scrape_id}


@router.post("/stop/{scrape_id}", status_code=204)
async def processing_stop(scrape_id: UUID):
    task_manager.cancel_task(str(scrape_id))
    async with scraper_info_cache_lock:
        if scrape_id in scraper_info_cache:
            scraper_info_cache[scrape_id].stop()
    return Response(status_code=204)


@router.get("/status-ui/{scrape_id}", include_in_schema=False)
async def run_status_ui(
    scrape_id: UUID,
):
    async def event_generator():
        while True:
            if scrape_id in message_queues:
                message = await message_queues[scrape_id].get()
                async with scraper_info_cache_lock:
                    content = message
                    scraper_info_cache[scrape_id].update_metadata(
                        action_count=content.scrape_action_count,
                        page_views=content.scrape_page_view_count,
                    )
                    if content.step_id is not None:
                        scraper_info_cache[scrape_id].add_step(
                            step_id=content.step_id,
                            next_step=content.next_step,
                            action=content.action,
                            action_count=content.step_action_count,
                            debug_choose_action_chat=content.choose_action_chat,
                            debug_next_step_chat=content.next_step_chat,
                        )

                yield {"data": scraper_info_cache[scrape_id].model_dump_json()}
            else:
                # wait before checking agian if queue has been created
                await asyncio.sleep(15)

    return EventSourceResponse(event_generator())
