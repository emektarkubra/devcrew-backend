from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime, timezone
from app.core.database import Base

class PrReviewQueryHistory(Base):
    __tablename__ = "pr_review_query_history"

    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id"))
    repo        = Column(String)
    pr_number   = Column(Integer)
    pr_title    = Column(String) 
    risk_score  = Column(Integer)
    issue_count = Column(Integer)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))