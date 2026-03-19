# app/schemas/agents.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class IndexRequest(BaseModel):
    token: str
    owner: str
    repo:  str

class QARequest(BaseModel):
    token: str
    owner: str
    repo:  str
    query: str

class HistoryRequest(BaseModel):
    token: str
    owner: str
    repo:  str


# response
class FileRef(BaseModel):
    name: str
    path: str

class IndexResponse(BaseModel):
    status:        str
    repo:          str
    files_indexed: int
    total_chunks:  int

class QAResponse(BaseModel):
    answer: str
    files:  List[str]
    suggestions: List[str] = []

class HistoryItemResponse(BaseModel):
    question:   str
    response:   Optional[str] = None
    filesFound: int
    timeAgo:    datetime

    class Config:
        from_attributes = True