import asyncio
import logging
from uuid import UUID

from cachetools import TTLCache
from fastapi import APIRouter, Response
from sse_starlette.sse import EventSourceResponse

from betatester.betatester_types import (
    RunMessage,
    RunRequest,
    ScrapeStatus,
    message_queues,
)
from betatester.file import file_client
from betatester.scraper.execution import ScrapeExecutor
from betatester.task_manager import task_manager
from betatester.utils import settings

logger = logging.getLogger(__name__)

scraper_info_cache: TTLCache[UUID, RunMessage] = TTLCache(
    maxsize=100, ttl=3600
)
scraper_info_cache_lock = asyncio.Lock()


router = APIRouter(
    prefix="/scraper",
    tags=["scraper"],
    responses={404: {"description": "Not found"}},
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
