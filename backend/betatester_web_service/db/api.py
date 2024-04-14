import json
import logging
from typing import Optional, cast
from uuid import UUID

from betatester.betatester_types import ScrapeSpec
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import async_scoped_session

from betatester_web_service.betatester_web_service_types import (
    RunEventMetadata,
    RunMessage,
    RunStep,
    ScrapeStatus,
    TestConfig,
)
from betatester_web_service.db.models import ConfigModel, TestEventsModel

logger = logging.getLogger(__name__)


async def get_test_config(
    config_id: UUID, db: async_scoped_session
) -> Optional[TestConfig]:
    config_result = await db.execute(
        select(ConfigModel).where(ConfigModel.id == config_id)
    )
    config_model: ConfigModel = config_result.scalars().one_or_none()

    if config_model is None:
        config = None
    else:
        config = TestConfig(
            config_id=cast(UUID, config_model.id),
            name=cast(str, config_model.name),
            url=cast(str, config_model.url),
            high_level_goal=cast(str, config_model.high_level_goal),
            max_page_views=cast(int, config_model.max_page_views),
            max_total_actions=cast(int, config_model.max_total_actions),
            max_action_attempts_per_step=cast(
                int, config_model.max_action_attempts_per_step
            ),
            viewport_width=cast(int, config_model.viewport_width),
            viewport_height=cast(int, config_model.viewport_height),
            variables=cast(dict, config_model.variables),
            files=cast(dict, config_model.files),
        )

    return config


async def insert_test_event(
    test_config: TestConfig,
    db: async_scoped_session,
    scrape_spec_id: Optional[UUID],
) -> UUID:
    event_raw = await db.execute(
        insert(TestEventsModel)
        .returning(TestEventsModel.id)
        .values(
            {
                **test_config.model_dump(exclude={"name"}),
                "page_views": 0,
                "action_count": 0,
                "status": ScrapeStatus.running.value,
                "event_history": [],
                "scrape_spec_id": scrape_spec_id,
            }
        )
    )
    event_id = event_raw.scalars().one()
    return event_id


async def update_test_event(
    event: RunMessage | RunEventMetadata,
    db: async_scoped_session,
    scrape_spec: Optional[ScrapeSpec] = None,
    scrape_spec_id: Optional[UUID] = None,
) -> None:
    update_values = event.model_dump(
        exclude={
            "steps",
            "id",
            "timestamp",
            "start_timestamp",
            "trace_url",
            "using_scrape_spec",
            "scrape_spec_failed",
        }
    )
    update_values["scrape_spec"] = (
        None if scrape_spec is None else scrape_spec.model_dump()
    )
    update_values["scrape_spec_id"] = scrape_spec_id
    if isinstance(event, RunMessage):
        event_history_raw = event.model_dump_json(include={"steps"})
        event_history = json.loads(event_history_raw)
        update_values["event_history"] = event_history["steps"]

    await db.execute(
        update(TestEventsModel)
        .where(TestEventsModel.id == event.id)
        .values(update_values)
    )


async def get_test_event_history(
    config_id: UUID,
    db: async_scoped_session,
) -> list[RunEventMetadata]:
    event_result = await db.execute(
        select(
            TestEventsModel.id,
            TestEventsModel.config_id,
            TestEventsModel.url,
            TestEventsModel.high_level_goal,
            TestEventsModel.status,
            TestEventsModel.max_page_views,
            TestEventsModel.max_total_actions,
            TestEventsModel.created_at,
            TestEventsModel.updated_at,
            TestEventsModel.page_views,
            TestEventsModel.action_count,
            TestEventsModel.fail_reason,
            TestEventsModel.scrape_spec,
            TestEventsModel.scrape_spec_id,
        )
        .where(TestEventsModel.config_id == config_id)
        .order_by(TestEventsModel.updated_at.desc())
    )

    event_metadata = []
    for event in event_result:
        event_metadata.append(
            RunEventMetadata(
                id=cast(UUID, event.id),
                config_id=cast(UUID, event.config_id),
                url=cast(str, event.url),
                high_level_goal=cast(str, event.high_level_goal),
                status=cast(ScrapeStatus, event.status),
                max_page_views=cast(int, event.max_page_views),
                max_total_actions=cast(int, event.max_total_actions),
                start_timestamp=cast(str, event.created_at.isoformat()),
                timestamp=cast(str, event.updated_at.isoformat()),
                page_views=cast(int, event.page_views),
                action_count=cast(int, event.action_count),
                fail_reason=cast(str, event.fail_reason),
                using_scrape_spec=event.scrape_spec_id is not None,
                scrape_spec_failed=event.scrape_spec is not None
                and event.scrape_spec_id is None,
            )
        )

    return event_metadata


async def get_test_event(
    config_id: UUID,
    scrape_id: UUID,
    db: async_scoped_session,
) -> Optional[RunMessage]:
    event_result = await db.execute(
        select(TestEventsModel).where(
            TestEventsModel.config_id == config_id,
            TestEventsModel.id == scrape_id,
        )
    )
    event = event_result.scalars().one_or_none()
    run_messsage = None
    if event is not None:
        run_messsage = RunMessage(
            id=cast(UUID, event.id),
            config_id=cast(UUID, event.config_id),
            url=cast(str, event.url),
            high_level_goal=cast(str, event.high_level_goal),
            page_views=cast(int, event.page_views),
            action_count=cast(int, event.action_count),
            status=cast(ScrapeStatus, event.status),
            steps=[
                RunStep.from_serialized(step)
                for step in cast(list[dict], event.event_history)
            ],
            start_timestamp=cast(str, event.created_at.isoformat()),
            timestamp=cast(str, event.updated_at.isoformat()),
            max_page_views=cast(int, event.max_page_views),
            max_total_actions=cast(int, event.max_total_actions),
            fail_reason=cast(str, event.fail_reason),
            using_scrape_spec=event.scrape_spec_id is not None,
            scrape_spec_failed=event.scrape_spec is not None
            and event.scrape_spec_id is None,
        )
    return run_messsage


async def get_latest_scrape_spec(
    config_id: UUID, db: async_scoped_session
) -> Optional[ScrapeSpec]:
    scrape_spec_raw = await db.execute(
        select(TestEventsModel.scrape_spec)
        .where(TestEventsModel.config_id == config_id)
        .where(TestEventsModel.scrape_spec.isnot(None))
        .order_by(TestEventsModel.updated_at.desc())
        .limit(1)
    )
    scrape_spec = scrape_spec_raw.scalars().one_or_none()

    scrape_spec_output = None
    if scrape_spec is not None:
        scrape_spec_output = ScrapeSpec.model_validate(scrape_spec)

    return scrape_spec_output
