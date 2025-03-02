from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserBase(BaseModel):
    email: str  # Changed from EmailStr to str for simplicity
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True  # Updated from orm_mode

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
        from_attributes = True  # Updated from orm_mode

class PredictionInput(BaseModel):
    jee_rank: int
    category: str
    college_type: str
    preferred_branch: str
    round_no: str
    min_probability: float = 0

class CollegePreference(BaseModel):
    preference: int
    institute: str
    college_type: str
    location: str
    branch: str
    opening_rank: float
    closing_rank: float
    admission_probability: float
    admission_chances: str

class PredictionOutput(BaseModel):
    preferences: List[CollegePreference]
    plot_data: Optional[dict] = None
