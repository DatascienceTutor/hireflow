"""
Question model: Stores a *specific* question assigned to a *specific* Job.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.session import Base
from datetime import datetime

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    question_text = Column(Text, nullable=False)
    model_answer = Column(Text, nullable=True)
    keywords = Column(JSON, nullable=True)
    model_answer_embedding = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Database-level Links
    
    # Link to the Job. If the Job is deleted, this Question is deleted.
    job_id = Column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Link to the master bank. If the master Q is deleted, set this to NULL.
    knowledge_question_id = Column(
        Integer, ForeignKey("knowledge_questions.id", ondelete="SET NULL"), nullable=True
    )

    # ORM Relationships
    job = relationship("Job", back_populates="questions")
    knowledge_question = relationship("KnowledgeQuestion", back_populates="copied_questions")
    
    # If this Question is deleted, all CandidateAnswers for it are deleted.
    answers = relationship(
        "CandidateAnswer", back_populates="question", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Question {self.id} for Job ID {self.job_id}>"