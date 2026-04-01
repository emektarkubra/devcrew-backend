from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from datetime import datetime, timezone
from app.core.database import Base

class DebugHistory(Base):
    __tablename__ = "debug_history"

    id             = Column(Integer, primary_key=True)
    user_id        = Column(Integer, ForeignKey("users.id"))
    repo           = Column(String)
    error          = Column(Text)
    root_cause     = Column(Text)
    severity       = Column(String)
    affected_files = Column(JSON)
    issues         = Column(JSON, default=list)
    explanation    = Column(Text)
    resolved       = Column(String, default="false")
    created_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))