from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.dialects.sqlite import JSON
from datetime import datetime
from .base import Base

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    job_code = Column(String, index=True)
    question_text = Column(Text, nullable=False)
    model_answer = Column(Text, nullable=True)
    keywords = Column(JSON, nullable=True)
    model_answer_embedding = Column(JSON, nullable=True)  # list[float] or NULL
    created_at = Column(DateTime, default=datetime.utcnow)
