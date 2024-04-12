import logging
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import FileResponse

from betatester_web_service.file import file_client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/data",
    tags=["data"],
    responses={404: {"description": "Not found"}},
    include_in_schema=False,
)


@router.get("/screenshot/{scrape_id}/{step_id}.png")
async def get_screenshot(scrape_id: UUID, step_id: UUID):
    return FileResponse(path=file_client.img_path(scrape_id, step_id))


@router.get("/trace/{scrape_id}.zip")
async def get_trace(scrape_id: UUID):
    return FileResponse(path=file_client.trace_path(scrape_id))
