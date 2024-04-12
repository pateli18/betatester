import asyncio
import json
import logging
from typing import AsyncGenerator
from uuid import UUID

from betatester.betatester_types import (
    ExecutorMessage,
    ModelChat,
    ModelChatContentType,
    ModelChatType,
    ModelType,
    OpenAiChatInput,
)
from betatester.model import openai_stream_response_generator
from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, validator
from sqlalchemy.ext.asyncio import async_scoped_session
from sse_starlette.sse import EventSourceResponse

from betatester import ScrapeAiExecutor
from betatester_web_service.betatester_web_service_types import (
    RunEventMetadata,
    RunMessage,
    ScrapeStatus,
)
from betatester_web_service.db.api import (
    get_test_config,
    get_test_event,
    insert_test_event,
    update_test_event,
)
from betatester_web_service.db.base import async_session_scope, get_session
from betatester_web_service.file import file_client
from betatester_web_service.task_manager import task_manager
from betatester_web_service.utils import model_client, settings

logger = logging.getLogger(__name__)

message_queues: dict[str, asyncio.Queue[ExecutorMessage]] = {}
scraper_info_cache: TTLCache[str, RunMessage] = TTLCache(maxsize=100, ttl=3600)
scraper_info_cache_lock = asyncio.Lock()


router = APIRouter(
    prefix="/scraper",
    tags=["scraper"],
    responses={404: {"description": "Not found"}},
)


async def _run_scraper(scraper: ScrapeAiExecutor, config_id: UUID):
    item_key = f"{config_id}-{scraper.scrape_id}"
    async with scraper_info_cache_lock:
        scraper_info_cache[item_key] = RunMessage(
            id=scraper.scrape_id,
            url=scraper.url,
            high_level_goal=scraper.high_level_goal,
            status=ScrapeStatus.running,
            max_page_views=scraper.max_page_views,
            max_total_actions=scraper.max_total_actions,
            steps=[],
            config_id=config_id,
        )

    if scraper.scrape_id not in message_queues:
        message_queues[item_key] = asyncio.Queue()

    # subscribe to scraper
    scraper.subscriptions = set([message_queues[item_key]])

    try:
        await scraper.run()
        scraper_info_cache[item_key].complete()
    except Exception as e:
        scraper_info_cache[item_key].fail(str(e))
    message_queues[item_key].put_nowait(ExecutorMessage())

    async with async_session_scope() as db:
        await update_test_event(scraper_info_cache[item_key], db)

        await db.commit()


@router.post("/start/{config_id}")
async def run_scraper(
    config_id: UUID, db: async_scoped_session = Depends(get_session)
):
    config = await get_test_config(config_id, db)
    if config is None:
        raise HTTPException(status_code=404, detail="Config not found")

    test_event_id = await insert_test_event(config, db)

    scraper = config.scrape_executor(test_event_id, file_client)

    task_manager.add_task(
        f"{config_id}-{scraper.scrape_id}", _run_scraper, scraper, config_id
    )

    return {"scrape_id": scraper.scrape_id}


@router.post("/stop/{config_id}/{scrape_id}", status_code=204)
async def processing_stop(config_id: UUID, scrape_id: UUID):
    item_key = f"{config_id}-{scrape_id}"
    task_manager.cancel_task(item_key)
    async with scraper_info_cache_lock:
        if item_key in scraper_info_cache:
            scraper_info_cache[item_key].stop()
            message_queues[item_key].put_nowait(ExecutorMessage())

    async with async_session_scope() as db:
        test_event = await get_test_event(config_id, scrape_id, db)
        if test_event:
            test_event.stop()
            await update_test_event(test_event, db)
            await db.commit()
    return Response(status_code=204)


@router.get("/status/{config_id}/{scrape_id}", response_model=RunEventMetadata)
async def processing_status(
    config_id: UUID,
    scrape_id: UUID,
    db: async_scoped_session = Depends(get_session),
) -> RunEventMetadata:
    item_key = f"{config_id}-{scrape_id}"
    async with scraper_info_cache_lock:
        scraper_info = scraper_info_cache.get(item_key)
        if scraper_info is None or scraper_info.id != scrape_id:
            scraper_info = await get_test_event(config_id, scrape_id, db)

    if scraper_info is None:
        raise HTTPException(
            status_code=404,
            detail="Scrape not found",
        )
    return scraper_info.metadata


@router.get("/status-ui/{config_id}/{scrape_id}", include_in_schema=False)
async def run_status_ui(
    config_id: UUID,
    scrape_id: UUID,
    db: async_scoped_session = Depends(get_session),
):
    async def event_generator():
        item_key = f"{config_id}-{scrape_id}"
        async with scraper_info_cache_lock:
            scrape_info = scraper_info_cache.get(item_key)
            if scrape_info is None:
                scrape_info = await get_test_event(config_id, scrape_id, db)
                if scrape_info is not None:
                    # add to cache
                    scraper_info_cache[item_key] = scrape_info
        if item_key in scraper_info_cache:
            yield {"data": scraper_info_cache[item_key].model_dump_json()}
        while True:
            if item_key in message_queues:
                message = await message_queues[item_key].get()
                async with scraper_info_cache_lock:
                    content = message
                    scraper_info_cache[item_key].update_metadata(
                        action_count=content.scrape_action_count,
                        page_views=content.scrape_page_view_count,
                    )
                    if content.step_id is not None:
                        scraper_info_cache[item_key].add_step(
                            step_id=content.step_id,
                            next_step=content.next_step,
                            action=content.action,
                            action_count=content.step_action_count,
                            debug_choose_action_chat=content.choose_action_chat,
                            debug_next_step_chat=content.next_step_chat,
                        )

                yield {"data": scraper_info_cache[item_key].model_dump_json()}
            else:
                await asyncio.sleep(15)

    return EventSourceResponse(event_generator())


class ChatRequest(BaseModel):
    chat: list[ModelChat]

    @validator("chat", pre=True)
    def validate_chat(cls, v):
        reconstructed_chat = [ModelChat.from_serialized(item) for item in v]
        return reconstructed_chat


@router.post("/chat", include_in_schema=False)
async def chat_endpoint(request: ChatRequest):
    async def openai_chat_stream(
        request: OpenAiChatInput,
    ) -> AsyncGenerator[str, None]:
        async for output in openai_stream_response_generator(
            model_client, request, settings.openai_api_key
        ):
            if "error" in output:
                yield output["error"]
                break
            else:
                chat = ModelChat(
                    role=ModelChatType.assistant, content=output["content"]
                )
                yield json.dumps(
                    {
                        "content": chat.model_dump(),
                    }
                ) + "\n"

    model = ModelType.gpt4turbo
    max_tokens = None
    stop = None
    for message in request.chat:
        if isinstance(message.content, list):
            for item in message.content:
                if item.type == ModelChatContentType.image_url:
                    model = ModelType.gpt4vision
                    max_tokens = 1000
                    stop = "<<END>>"
                    break

    chat_input = OpenAiChatInput(
        messages=request.chat,
        stream=True,
        model=model,
        max_tokens=max_tokens,
        stop=stop,
    )

    return StreamingResponse(
        openai_chat_stream(chat_input),
        media_type="application/x-ndjson",
    )
