from sqlalchemy.orm import Session
from . import models, schemas, security
from datetime import datetime

def get_user(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = security.get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_last_login(db: Session, user: models.User):
    user.last_login = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user

def get_all_josaa_data(db: Session):
    return db.query(models.JosaaData).all()

def create_josaa_data(db: Session, data: schemas.JosaaDataCreate):
    db_data = models.JosaaData(**data.dict())
    db.add(db_data)
    db.commit()
    db.refresh(db_data)
    return db_data

def bulk_create_josaa_data(db: Session, data_list: list):
    db_data_list = [models.JosaaData(**data) for data in data_list]
    db.bulk_save_objects(db_data_list)
    db.commit()
    return db_data_list
