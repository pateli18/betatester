from sqlalchemy import VARCHAR, Column, ForeignKey, Integer, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from betatester_web_service.db.base import Base
from betatester_web_service.db.mixins import ScrapeParamsMixin, TimestampMixin


class TestEventsModel(Base, TimestampMixin, ScrapeParamsMixin):
    __tablename__ = "test_events"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )

    config_id = Column(
        UUID(as_uuid=True),
        ForeignKey("config.id"),
    )
    status = Column(VARCHAR, nullable=False)
    page_views = Column(Integer, nullable=False)
    action_count = Column(Integer, nullable=False)
    fail_reason = Column(VARCHAR, nullable=True)
    event_history = Column(JSONB, nullable=False)

    config = relationship(
        "ConfigModel",
        back_populates="test_events",
    )
