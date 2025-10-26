from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.dialects.sqlite import JSON
from datetime import datetime
from .base import Base

class CandidateAnswer(Base):
    __tablename__ = "candidate_answers"
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(String, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), index=True)
    answer_text = Column(Text, nullable=False)
    answer_embedding = Column(JSON, nullable=True)   # cached vector
    semantic_similarity = Column(Float, nullable=True)
    llm_score = Column(Float, nullable=True)
    final_score = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
