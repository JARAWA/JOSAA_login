from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime, timedelta

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./josaa.db")

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Password reset token storage (in-memory for demo, use database in production)
reset_tokens = {}

def store_reset_token(email: str, token: str):
    """Store password reset token with expiration"""
    reset_tokens[email] = {
        'token': token,
        'expires': datetime.utcnow() + timedelta(hours=1)
    }

def verify_reset_token(email: str, token: str) -> bool:
    """Verify if reset token is valid and not expired"""
    if email in reset_tokens:
        token_data = reset_tokens[email]
        if (token_data['token'] == token and 
            token_data['expires'] > datetime.utcnow()):
            return True
    return False

def clear_reset_token(email: str):
    """Clear reset token after use"""
    if email in reset_tokens:
        del reset_tokens[email]

# Initialize database tables
def init_db():
    Base.metadata.create_all(bind=engine)

# Create tables on import
init_db()
