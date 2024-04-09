from sqlalchemy import VARCHAR, Column, Integer
from sqlalchemy.dialects.postgresql import JSONB


class ScrapeParamsMixin(object):
    url = Column(VARCHAR, nullable=False)
    high_level_goal = Column(VARCHAR, nullable=False)
    max_page_views = Column(Integer, nullable=False)
    max_total_actions = Column(Integer, nullable=False)
    max_action_attempts_per_step = Column(Integer, nullable=False)
    viewport_width = Column(Integer, nullable=False)
    viewport_height = Column(Integer, nullable=False)
    variables = Column(JSONB, nullable=False)
    files = Column(JSONB, nullable=False)
