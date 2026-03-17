from sqlalchemy import Column, Integer, String, BigInteger
from app.core.database import Base
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    github_id       = Column(BigInteger, unique=True, index=True)
    username        = Column(String, unique=True)
    email           = Column(String, nullable=True)
    avatar_url      = Column(String, nullable=True)
    access_token    = Column(String) 
    repos = relationship("Repo", back_populates="owner")