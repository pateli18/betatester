import logging
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, insert, select
from sqlalchemy.ext.asyncio import async_scoped_session

from betatester_web_service.betatester_web_service_types import (
    TestConfigMetadata,
    TestConfigResponse,
    UpsertConfig,
)
from betatester_web_service.db.api import (
    get_test_config,
    get_test_event_history,
)
from betatester_web_service.db.base import get_session
from betatester_web_service.db.models import ConfigModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/config",
    tags=["config"],
    responses={404: {"description": "Not found"}},
)


class UpsertConfigResponse(BaseModel):
    config_id: UUID


@router.post("/upsert", response_model=UpsertConfigResponse)
async def upsert_config(
    request: UpsertConfig,
    db: async_scoped_session = Depends(get_session),
) -> UpsertConfigResponse:

    if request.config_id is None:
        values_to_insert = request.model_dump(exclude={"config_id"})

        config_raw = await db.execute(
            insert(ConfigModel).returning(ConfigModel),
            [
                values_to_insert,
            ],
        )
        config = config_raw.scalars().one()
        config_id = cast(UUID, config.id)

    else:
        config_id = request.config_id
        config_result = await db.execute(
            select(ConfigModel).where(ConfigModel.id == config_id)
        )
        config: ConfigModel = config_result.scalars().one_or_none()
        if config is None:
            raise HTTPException(
                status_code=404,
                detail="Config not found",
            )
        config.name = cast(Column[str], request.name)
        config.url = cast(Column[str], request.url)
        config.high_level_goal = cast(Column[str], request.high_level_goal)
        config.max_page_views = cast(Column[int], request.max_page_views)
        config.max_total_actions = cast(Column[int], request.max_total_actions)
        config.max_action_attempts_per_step = cast(
            Column[int], request.max_action_attempts_per_step
        )
        config.viewport_width = cast(Column[int], request.viewport_width)
        config.viewport_height = cast(Column[int], request.viewport_height)
        config.variables = cast(Column[dict], request.variables)
        config.files = cast(
            Column[dict], {k: v.model_dump() for k, v in request.files.items()}
        )

    await db.commit()
    return UpsertConfigResponse(config_id=config_id)


@router.get("/all", response_model=list[TestConfigMetadata])
async def get_all_configs(
    db: async_scoped_session = Depends(get_session),
) -> list[TestConfigMetadata]:
    configs_result = await db.execute(
        select(ConfigModel).order_by(ConfigModel.updated_at.desc())
    )
    configs = configs_result.scalars().all()
    return [
        TestConfigMetadata(
            config_id=cast(UUID, config.id),
            name=cast(str, config.name),
            last_updated=config.updated_at.isoformat(),
            url=cast(str, config.url),
        )
        for config in configs
    ]


@router.get("/{config_id}", response_model=TestConfigResponse)
async def get_config(
    config_id: UUID,
    db: async_scoped_session = Depends(get_session),
) -> TestConfigResponse:
    config = await get_test_config(config_id, db)
    if config is None:
        raise HTTPException(
            status_code=404,
            detail="Config not found",
        )
    event_history = await get_test_event_history(config_id, db)

    return TestConfigResponse(config=config, history=event_history)
