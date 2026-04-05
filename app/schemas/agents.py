from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Any


# ─── Request Models ───────────────────────────────────────────────────────────

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
    token:    str
    owner:    str
    repo:     str
    target:   str
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

class ApplyDebugFixRequest(BaseModel):
    token:  str
    owner:  str
    repo:   str
    issues: list
    error:  str

class SaveTestsRequest(BaseModel):
    token:     str
    tests:     list
    filename:  str
    framework: str


# ─── Response Models ──────────────────────────────────────────────────────────

class IndexResponse(BaseModel):
    status:        str
    repo:          str
    files_indexed: int
    total_chunks:  int

class QAResponse(BaseModel):
    answer:      str
    files:       List[str]
    suggestions: List[str] = []

class HistoryItemResponse(BaseModel):
    question:   str
    response:   str
    filesFound: int
    files:      list = []
    timeAgo:    datetime

    class Config:
        from_attributes = True

class CheckIndexResponse(BaseModel):
    indexed:    bool
    file_count: int

class PRReviewResponse(BaseModel):
    pr:           str
    title:        str
    riskScore:    int
    issueCount:   int
    issues:       List[Any] = []
    diff:         Optional[str] = None
    files:        List[str] = []
    summary:      Optional[str] = None
    changedFiles: int = 0

class PRHistoryItemResponse(BaseModel):
    pr:           str
    title:        Optional[str] = None
    riskScore:    Optional[int] = None
    issueCount:   Optional[int] = None
    issues:       List[Any] = []
    diff:         Optional[str] = None
    files:        List[str] = []
    summary:      Optional[str] = None
    changedFiles: int = 0
    timeAgo:      datetime

    class Config:
        from_attributes = True

class AffectedFile(BaseModel):
    path: str
    name: str
    code: str

class DebugResponse(BaseModel):
    rootCause:     str
    severity:      str
    explanation:   str
    affectedFiles: list[AffectedFile]  # ← düzelt
    issues:        list[dict]
    contextFiles:  list[str]

class DebugHistoryItemResponse(BaseModel):
    error:         str
    rootCause:     Optional[str] = None
    severity:      Optional[str] = None
    affectedFiles: List[str] = []
    issues:        List[Any] = []
    explanation:   Optional[str] = None
    resolved:      Optional[bool] = None
    timeAgo:       datetime

    class Config:
        from_attributes = True

class DebugApplyFixResponse(BaseModel):
    pr_url:  Optional[str] = None
    branch:  Optional[str] = None
    message: Optional[str] = None

class TestItem(BaseModel):
    name: str
    code: str

class TestGeneratorResponse(BaseModel):
    target:           str
    testCount:        int
    coverage:         Optional[int] = None
    unitCount:        Optional[int] = None
    edgeCount:        Optional[int] = None
    integrationCount: Optional[int] = None
    tests:            List[Any] = []
    framework:        str
    mergedCode:       Optional[str] = None

class TestHistoryItemResponse(BaseModel):
    target:     str
    testCount:  int
    coverage:   Optional[int] = None 
    tests:      List[Any] = []
    framework:  str
    mergedCode: Optional[str] = None
    timeAgo:    datetime

    class Config:
        from_attributes = True

class SaveTestsResponse(BaseModel):
    content:  str
    filename: str

class DocumentationResponse(BaseModel):
    fileName:     str
    description:  str
    markdown:     str
    contextFiles: List[str] = []

class DocumentationHistoryItemResponse(BaseModel):
    target:      str
    docType:     str
    description: str
    content:     str
    timeAgo:     datetime

    class Config:
        from_attributes = True

class RepoFilesResponse(BaseModel):
    files: List[str]

class ApplyFixesResponse(BaseModel):
    fixes: List[Any] = []

class ApplyFixesToBranchResponse(BaseModel):
    message:      Optional[str] = None
    branch:       Optional[str] = None
    committed:    Optional[int] = None
    skipped:      Optional[int] = None