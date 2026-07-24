# app2/repositories/base.py
from sqlalchemy.orm import Session
from typing import TypeVar, Generic

T = TypeVar("T")

class BaseRepository:
    def __init__(self, db: Session):
        self.db = db