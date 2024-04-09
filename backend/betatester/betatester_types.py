import asyncio
import base64
from abc import abstractmethod
from datetime import datetime
from enum import Enum
from typing import Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, computed_field, model_serializer

message_queues: dict[UUID, asyncio.Queue["ExecutorMessage"]] = {}


class ToolChoiceFunction(BaseModel):
    name: str


class ToolChoiceObject(BaseModel):
    type: str = "function"
    function: ToolChoiceFunction


ToolChoice = Optional[Union[Literal["auto"], ToolChoiceObject]]


class ModelType(str, Enum):
    gpt4vision = "gpt-4-vision-preview"
    gpt4turbo = "gpt-4-turbo-preview"


class ModelChatType(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"


class ModelChatContentImageDetail(str, Enum):
    low = "low"
    auto = "auto"
    high = "high"


class ModelChatContentImage(BaseModel):
    url: str
    detail: ModelChatContentImageDetail

    @classmethod
    def from_b64(
        cls,
        b64_image: str,
        detail: ModelChatContentImageDetail = ModelChatContentImageDetail.auto,
    ) -> "ModelChatContentImage":
        return cls(url=f"data:image/png;base64,{b64_image}", detail=detail)


class ModelChatContentType(str, Enum):
    text = "text"
    image_url = "image_url"


class ModelChatContent(BaseModel):
    type: ModelChatContentType
    content: Union[str, ModelChatContentImage]

    @model_serializer
    def serialize(self) -> dict[str, Union[str, dict]]:
        content_key = self.type.value
        content_value = (
            self.content
            if isinstance(self.content, str)
            else self.content.model_dump()
        )
        return {"type": self.type.value, content_key: content_value}


class ModelChat(BaseModel):
    role: ModelChatType
    content: Union[str, list[ModelChatContent]]

    @classmethod
    def from_b64_image(
        cls, role: ModelChatType, b64_image: str
    ) -> "ModelChat":
        return cls(
            role=role,
            content=[
                ModelChatContent(
                    type=ModelChatContentType.image_url,
                    content=ModelChatContentImage.from_b64(b64_image),
                )
            ],
        )


class ModelFunction(BaseModel):
    name: str
    description: Optional[str]
    parameters: Optional[dict]


class Tool(BaseModel):
    type: str = "function"
    function: ModelFunction


OpenAiPromptReturnType = tuple[
    list[ModelChat], list[ModelFunction], ToolChoice
]


class OpenAiChatInput(BaseModel):
    messages: list[ModelChat]
    model: ModelType
    max_tokens: Optional[int] = None
    n: int = 1
    temperature: float = 0.0
    stop: Optional[str] = None
    tools: Optional[list[Tool]] = None
    tool_choice: ToolChoice = None
    stream: bool = False
    logprobs: bool = False
    top_logprobs: Optional[int] = None

    @property
    def data(self) -> dict:
        exclusion = set()
        if self.tools is None:
            exclusion.add("tools")
        if self.tool_choice is None:
            exclusion.add("tool_choice")

        return self.model_dump(
            exclude=exclusion,
        )


class ActionType(str, Enum):
    click = "click"
    fill = "fill"
    select = "select"
    check = "check"
    upload_file = "upload_file"
    none = "none"


class ActionElement(BaseModel):
    role: Optional[str] = None
    name: Optional[str] = None
    selector: Optional[str] = None


class Action(BaseModel):
    element: ActionElement
    action_type: ActionType
    action_value: Optional[str] = None


class FileInfo(BaseModel):
    name: str
    b64_content: str = Field(exclude=True)
    mime_type: str = Field(alias="mimeType")

    @computed_field
    @property
    def buffer(self) -> bytes:
        # file strings are base64 url encoded
        return base64.b64decode(self.b64_content.split(",", 1)[1])


RunVariables = dict[str, str]
RunFiles = dict[str, FileInfo]


class RunRequest(BaseModel):
    url: str
    high_level_goal: str
    max_page_views: int = 10
    max_total_actions: int = 20
    max_action_attempts_per_step: int = 5
    viewport_width: int = 1280
    viewport_height: int = 720
    variables: RunVariables = Field(default_factory=dict)
    files: RunFiles = Field(default_factory=dict)


class HtmlType(str, Enum):
    full = "full"
    clean = "clean"


class FileClient:
    @abstractmethod
    async def save_img(
        self, scrape_id: UUID, step_id: UUID, img: bytes
    ) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def save_html(
        self, scrape_id: UUID, step_id: UUID, html: str, html_type: HtmlType
    ) -> None:
        raise NotImplementedError()

    @abstractmethod
    async def save_trace(self, tmp_trace_path: str) -> None:
        raise NotImplementedError()

    @abstractmethod
    def img_path(self, scrape_id: UUID, step_id: UUID) -> str:
        raise NotImplementedError()


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


class ExecutorMessage(BaseModel):
    step_id: Optional[UUID] = None
    scrape_page_view_count: Optional[int] = None
    scrape_action_count: Optional[int] = None
    next_step: Optional[str] = None
    action: Optional[Action] = None
    step_action_count: Optional[int] = None
    next_step_chat: Optional[list[ModelChat]] = None
    choose_action_chat: Optional[list[ModelChat]] = None
