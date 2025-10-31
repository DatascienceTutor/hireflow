"""
KnowledgeQuestion model: The "Master Bank" of all possible questions.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db.session import Base

class KnowledgeQuestion(Base):
    __tablename__ = "knowledge_questions"

    id = Column(Integer, primary_key=True, index=True)
    technology = Column(String(50), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    model_answer = Column(Text, nullable=True)
    keywords = Column(JSON, nullable=True) # <-- Changed from String to JSON
    created_at = Column(DateTime, server_default=func.now())

    # ORM Relationship:
    # This links to all the job-specific questions copied from this master.
    # If this master Q is deleted, the 'knowledge_question_id' on the
    # 'Question' table will be set to NULL.
    copied_questions = relationship(
        "Question", back_populates="knowledge_question"
    )

    def __repr__(self) -> str:
        return f"<KnowledgeQuestion {self.technology} - {self.question_text[:40]!r}>"