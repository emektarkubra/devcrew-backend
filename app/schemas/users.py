from pydantic import BaseModel
from typing import Optional

class UserResponse(BaseModel):
    id:         int
    github_id:  int
    username:   str
    email:      Optional[str] = None
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class UserDetailResponse(BaseModel):
    id:           int
    github_id:    int
    username:     str
    email:        Optional[str] = None
    avatar_url:   Optional[str] = None
    name:         Optional[str] = None
    bio:          Optional[str] = None
    location:     Optional[str] = None
    company:      Optional[str] = None
    blog:         Optional[str] = None
    followers:    Optional[int] = None
    following:    Optional[int] = None
    public_repos: Optional[int] = None
    html_url:     Optional[str] = None

    class Config:
        from_attributes = True