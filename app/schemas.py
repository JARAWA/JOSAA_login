from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        orm_mode = True

class JosaaDataBase(BaseModel):
    institute: str
    college_type: str
    location: str
    academic_program_name: str
    category: str
    opening_rank: float
    closing_rank: float
    round: str

class JosaaDataCreate(JosaaDataBase):
    pass

class JosaaData(JosaaDataBase):
    id: int

    class Config:
        orm_mode = True
