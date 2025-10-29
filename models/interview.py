from sqlalchemy import Column, Integer, String, Float, ForeignKey
from db.session import Base


class Interview(Base):
    __tablename__ = "interviews"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("jobs.job_code"), nullable=False)
    candidate_id = Column(String, ForeignKey("candidates.candidate_code"), nullable=False)
    status = Column(String(50), default="Pending")
    evaluation_status = Column(String(50), default="Not evaluated")
    final_score = Column(Float, nullable=True)  # 1.0 - 10.0
    scheduled_at = Column(String(50), nullable=True)
    created_at = Column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<Interview job={self.job_id} cand={self.candidate_id} status={self.status}>"
