from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from db.session import Base
from datetime import datetime
import json

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("Candidate.candidate_code"), nullable=False)
    job_code = Column(String(100), nullable=False)
    email = Column(String(120), nullable=False)
    questions_dict = Column(JSON, nullable=False)  # stores dict of all approved questions
    approved = Column(Integer, default=0)
    created_at = Column(String(50), default=lambda: datetime.utcnow().isoformat())

    # relationships (optional if you use them)
    # candidate = relationship("Candidate", back_populates="questions", lazy="joined")

    def __repr__(self):
        return f"<Question id={self.id} candidate_id={self.candidate_id} job_code={self.job_code}>"
