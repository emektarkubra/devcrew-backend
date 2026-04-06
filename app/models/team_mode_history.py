from sqlalchemy import Column, Integer, String, JSON, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class TeamModeHistory(Base):
    __tablename__ = "team_mode_history"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, index=True, nullable=False)
    repo          = Column(String, nullable=False)
    agents        = Column(JSON, nullable=False)    
    results       = Column(JSON, nullable=False) 
    health_score  = Column(Integer, nullable=True)
    summary       = Column(String, nullable=True)
    top_actions   = Column(JSON, nullable=True)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())