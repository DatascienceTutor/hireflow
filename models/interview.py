"""
Interview model: The central "junction" table.
Links a Candidate to a Job.
"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.session import Base

class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(50), default="Pending", index=True)
    evaluation_status = Column(String(50), default="Not Evaluated")
    final_score = Column(Float, nullable=True)
    final_selection_status = Column(
        Enum("Undecided", "Selected", "Rejected", name="selection_status_enum"),
        nullable=False,
        default="Undecided",
        server_default="Undecided"
    )
    match_report = Column(JSON, nullable=True) # <-- ADD THIS LINE
    scheduled_at = Column(String(50), nullable=True) # Kept as string per original
    created_at = Column(DateTime, server_default=func.now())

    # Database-level Links
    
    # Link to the Job. If the Job is deleted, this Interview is deleted.
    job_id = Column(
        Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # Link to the Candidate. If the Candidate is deleted, this Interview is deleted.
    candidate_id = Column(
        Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ORM Relationships
    job = relationship("Job", back_populates="interviews")
    candidate = relationship("Candidate", back_populates="interviews")
    
    # If this Interview is deleted, all Answers associated with it are also deleted.
    answers = relationship(
        "CandidateAnswer", back_populates="interview", cascade="all, delete-orphan"
    )
    
    # If this Interview is deleted, all Questions associated with it are also deleted.
    questions = relationship(
        "Question", back_populates="interview", cascade="all, delete-orphan"
    )


    def __repr__(self) -> str:
        return f"<Interview {self.id} - JobID {self.job_id} CandID {self.candidate_id}>"