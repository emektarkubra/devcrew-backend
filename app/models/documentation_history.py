from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from datetime import datetime, timezone
from app.core.database import Base

class DocumentationHistory(Base):
    __tablename__ = "documentation_history"

    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id"))
    repo        = Column(String)
    target      = Column(String) 
    doc_type    = Column(String) 
    description = Column(Text)
    content     = Column(Text)  
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))