# app/models/repo.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime, BigInteger, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Repo(Base):
    __tablename__ = "repos"

    id              = Column(Integer, primary_key=True, index=True)
    github_repo_id  = Column(BigInteger, unique=True, index=True)
    name            = Column(String)
    full_name       = Column(String, unique=True)
    description     = Column(String, nullable=True)
    language        = Column(String, nullable=True)
    is_private      = Column(Boolean, default=False)
    stars           = Column(Integer, default=0)
    last_indexed_at = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    # Foreign key
    owner_id        = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationship
    owner           = relationship("User", back_populates="repos")