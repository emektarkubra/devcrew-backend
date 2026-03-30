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

class PRReviewRequest(BaseModel):
    token:     str
    owner:     str
    repo:      str
    pr_number: int

class PRHistoryRequest(BaseModel):
    token: str
    owner: str
    repo:  str

class PRListRequest(BaseModel):
    token: str
    owner: str
    repo:  str


class DebugRequest(BaseModel):
    token: str
    owner: str
    repo:  str
    error: str

class DebugHistoryRequest(BaseModel):
    token: str
    owner: str
    repo:  str

class DocumentationRequest(BaseModel):
    token: str
    owner: str
    repo:  str
    target: str  
    doc_type: str 

class DocumentationHistoryRequest(BaseModel):
    token: str
    owner: str
    repo:  str

class RepoFilesRequest(BaseModel):
    token: str
    owner: str
    repo:  str


class TestGeneratorRequest(BaseModel):
    token:     str
    owner:     str
    repo:      str
    target:    str
    framework: str = "pytest"

class TestHistoryRequest(BaseModel):
    token: str
    owner: str
    repo:  str

class ApplyFixRequest(BaseModel):
    token:     str
    owner:     str
    repo:      str
    pr_number: int
    issues:    list

class ApplyFixesToBranchRequest(BaseModel):
    token:     str
    owner:     str
    repo:      str
    pr_number: int
    fixes:     list

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
    response:   str
    filesFound: int
    files:      list = []
    timeAgo:    datetime

    class Config:
        from_attributes = True