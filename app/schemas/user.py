from pydantic import BaseModel, EmailStr, Field
 
class UserCreate(BaseModel):   # post isteginde {"email": "test@mail.com", "password": "123456"}
    email: EmailStr
    username: str = Field(min_length=4, max_length=12)
    password: str = Field(min_length=8, max_length=72)
 
class UserResponse(BaseModel):   # response boyle olmali
    id: int
    email: EmailStr
    username: str
 
    class Config:
        orm_mode = True # SQLAlchemy model objesini direkt Pydantic schema'ya çevirebilirsin. User (ORM) → UserOut (Pydantic) dönüşümü yapar.
 
 
 
# KISACA--> Fast Api
# ORM objesini al → UserResponse formatına çevir → JSON üret