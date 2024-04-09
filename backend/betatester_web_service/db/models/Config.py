from sqlalchemy import VARCHAR, Column, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from betatester_web_service.db.base import Base
from betatester_web_service.db.mixins import ScrapeParamsMixin, TimestampMixin


class ConfigModel(Base, TimestampMixin, ScrapeParamsMixin):
    __tablename__ = "config"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    name = Column(VARCHAR, nullable=False)

    test_events = relationship(
        "TestEventsModel",
        back_populates="config",
    )
