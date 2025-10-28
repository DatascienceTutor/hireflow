from sqlalchemy import Column, Integer, String, Text
from db.session import Base


class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(Integer, primary_key=True, index=True)
    candidate_code = Column(String(100), nullable=False, unique=True, index=True)
    job_code = Column(String(100), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    resume = Column(Text, nullable=False)
    job_description = Column(Text, nullable=True)
    tech = Column(String(64), nullable=False)
    resume_hash = Column(String(64), nullable=True, unique=True, index=True)
    interview_completed = Column(Boolean, default=False, nullable=False)
    created_at = Column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<Candidate {self.candidate_code} - {self.name}>"
