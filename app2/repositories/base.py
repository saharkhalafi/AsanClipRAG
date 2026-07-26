# app2/repositories/base.py
from typing import TypeVar

from sqlalchemy.orm import Session

T = TypeVar("T")

class BaseRepository:
    def __init__(self, db: Session):
        self.db = db
