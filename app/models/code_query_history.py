from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime, timezone
from app.core.database import Base

class CodeQueryHistory(Base):
    __tablename__ = "code_query_history"

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"))
    repo       = Column(String)
    query      = Column(Text)
    response   = Column(Text, nullable=True)
    file_count = Column(Integer)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    