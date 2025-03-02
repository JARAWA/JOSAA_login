from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from .database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

class JosaaData(Base):
    __tablename__ = "josaa_data"

    id = Column(Integer, primary_key=True, index=True)
    institute = Column(String, index=True)
    college_type = Column(String, index=True)
    location = Column(String)
    academic_program_name = Column(String, index=True)
    category = Column(String, index=True)
    opening_rank = Column(Float)
    closing_rank = Column(Float)
    round = Column(String)
