from sqlalchemy import Column, Integer, String, Text, ForeignKey
from pgvector.sqlalchemy import Vector
from app.core.database import Base

class CodeEmbedding(Base):
    __tablename__ = "code_embeddings"

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"))
    repo       = Column(String)       
    file_path  = Column(String)        
    chunk_text = Column(Text)          
    embedding  = Column(Vector(384))  