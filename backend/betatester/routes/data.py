import logging
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import FileResponse

from betatester.file import file_client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/data",
    tags=["data"],
    responses={404: {"description": "Not found"}},
)


@router.get("/screenshot/{scrape_id}/{step_id}.png")
async def get_screenshot(scrape_id: UUID, step_id: UUID):
    return FileResponse(path=file_client.img_path(scrape_id, step_id))
