# app/schemas/repo.py

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class RepoResponse(BaseModel):
    id:             int
    github_repo_id: int
    name:           str
    full_name:      str
    description:    Optional[str] = None
    language:       Optional[str] = None
    is_private:     bool
    stars:          int
    default_branch: Optional[str] = None
    watchers_count: int
    size:           int
    forks_count:    int
    html_url:       Optional[str] = None
    updated_at:     Optional[datetime] = None
    last_indexed_at: Optional[datetime] = None
    created_at:     datetime
    owner_id:       int

    class Config:
        from_attributes = True