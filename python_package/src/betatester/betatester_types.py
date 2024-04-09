import base64
from abc import abstractmethod
from enum import Enum
from typing import Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, model_serializer


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


class ToolChoiceFunction(BaseModel):
    name: str


class ToolChoiceObject(BaseModel):
    type: str = "function"
    function: ToolChoiceFunction


ToolChoice = Optional[Union[Literal["auto"], ToolChoiceObject]]


class ModelType(str, Enum):
    gpt4vision = "gpt-4-vision-preview"
    gpt4turbo = "gpt-4-turbo-preview"


class ModelFunction(BaseModel):
    name: str
    description: Optional[str]
    parameters: Optional[dict]


class Tool(BaseModel):
    type: str = "function"
    function: ModelFunction


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


class FileInfo(BaseModel):
    name: str
    b64_content: str
    mime_type: str

    @property
    def buffer(self) -> bytes:
        # file strings are base64 url encoded
        return base64.b64decode(self.b64_content.split(",", 1)[1])

    @property
    def input_files(self) -> dict[str, Union[str, bytes]]:
        return {
            "name": self.name,
            "buffer": self.buffer,
            "mimeType": self.mime_type,
        }


ScrapeVariables = dict[str, str]
ScrapeFiles = dict[str, FileInfo]


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


class ExecutorMessage(BaseModel):
    step_id: Optional[UUID] = None
    scrape_page_view_count: Optional[int] = None
    scrape_action_count: Optional[int] = None
    next_step: Optional[str] = None
    action: Optional[Action] = None
    step_action_count: Optional[int] = None
    next_step_chat: Optional[list[ModelChat]] = None
    choose_action_chat: Optional[list[ModelChat]] = None


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
    async def save_trace(self, scrape_id: UUID, tmp_trace_path: str) -> None:
        raise NotImplementedError()

    @abstractmethod
    def img_path(self, scrape_id: UUID, step_id: UUID) -> str:
        raise NotImplementedError()

    @abstractmethod
    def trace_path(self, scrape_id: UUID) -> str:
        raise NotImplementedError()
