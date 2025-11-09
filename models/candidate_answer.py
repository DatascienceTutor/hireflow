"""
CandidateAnswer model: Stores a candidate's specific answer to a question
during a specific interview.
"""
from sqlalchemy import Column, Integer, Text, Float, DateTime, ForeignKey
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship
from db.session import Base
from datetime import datetime

class CandidateAnswer(Base):
    __tablename__ = "candidate_answers"

    id = Column(Integer, primary_key=True, index=True)
    answer_text = Column(Text, nullable=False)
    answer_embedding = Column(JSON, nullable=True)
    semantic_similarity = Column(Float, nullable=True)
    llm_score = Column(Float, nullable=True)
    feedback = Column(JSON, nullable=True) 
    created_at = Column(DateTime, default=datetime.utcnow)

    # Database-level Links
    
    # Link to the Candidate. If the Candidate is deleted, this Answer is deleted.
    candidate_id = Column(
        Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Link to the Question. If the Question is deleted, this Answer is deleted.
    question_id = Column(
        Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Link to the Interview. If the Interview is deleted, this Answer is deleted.
    interview_id = Column(
        Integer, ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ORM Relationships
    candidate = relationship("Candidate", back_populates="answers")
    question = relationship("Question", back_populates="answers")
    interview = relationship("Interview", back_populates="answers")

    def __repr__(self) -> str:
        return f"<CandidateAnswer {self.id} for Interview {self.interview_id}>"