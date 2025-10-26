from sqlalchemy import Column, Integer, String, Text
from db.session import Base


class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    job_code = Column(String(100), nullable=False, unique=True, index=True)
    tech = Column(String(50), nullable=False)  # technology tag
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    description_hash = Column(String, unique=True, index=True)
    created_at = Column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<Job {self.job_code} - {self.tech}>"
