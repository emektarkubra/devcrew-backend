from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from datetime import datetime, timezone
from app.core.database import Base

class TestHistory(Base):
    __tablename__ = "test_history"

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"))
    repo       = Column(String)
    target     = Column(String)
    framework  = Column(String)
    test_count = Column(Integer)
    coverage   = Column(Integer)
    tests      = Column(JSON)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))