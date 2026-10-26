from sqlalchemy.orm import Session
from typing import List, Optional
# Assure-toi que ce chemin correspond bien à ton projet
from app.database.models import User 

class UserService:
    @staticmethod
    def get_users(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        name: Optional[str] = None,
        email: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> List[User]:
        query = db.query(User)

        if user_id:
            query = query.filter(User.id == user_id)
        if name:
            query = query.filter(User.name.contains(name))
        if email:
            query = query.filter(User.email.contains(email))

        return query.offset(skip).limit(limit).all()

    @staticmethod
    def create_user(db: Session, name: str, email: str) -> User:
        if not name or not email:
            raise ValueError("Name and email are required")

        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            raise ValueError("Email already exists")

        new_user = User(name=name, email=email)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def update_user(db: Session, user_id: int, name: str, email: str) -> Optional[User]:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.name = name
            user.email = email
            db.commit()
            db.refresh(user)
        return user

    @staticmethod
    def delete_user(db: Session, user_id: int) -> bool:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            db.delete(user)
            db.commit()
            return True
        return False