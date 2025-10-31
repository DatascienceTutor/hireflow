"""
Candidate model: Stores candidate information.
This is a "parent" table to Interviews and CandidateAnswers.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.session import Base

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    candidate_code = Column(String(100), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, unique=True, index=True)
    tech = Column(String(64), nullable=False)
    resume = Column(Text, nullable=True)
    resume_hash = Column(String(64), nullable=True, unique=True, index=True)
    created_at = Column(DateTime, server_default=func.now())

    # ORM Relationships:
    # If a Candidate is deleted, all their Interviews and Answers are deleted.
    interviews = relationship(
        "Interview", back_populates="candidate", cascade="all, delete-orphan"
    )
    answers = relationship(
        "CandidateAnswer", back_populates="candidate", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Candidate {self.candidate_code} - {self.name}>"