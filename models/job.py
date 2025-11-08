"""
Job model: Stores job postings.
This is a "parent" table to Interviews and Questions.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.session import Base

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_code = Column(String(100), nullable=False, unique=True, index=True)
    tech = Column(String(50), nullable=False)
    title = Column(String(255), nullable=True)
    manager_email = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    description_hash = Column(String(64), unique=True, index=True, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # ORM Relationships:
    # If a Job is deleted, all its Interviews and Questions are deleted.
    interviews = relationship(
        "Interview", back_populates="job", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Job {self.job_code} - {self.title}>"