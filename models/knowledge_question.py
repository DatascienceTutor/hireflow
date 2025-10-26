from sqlalchemy import Column, Integer, String, Text
from db.session import Base


class KnowledgeQuestion(Base):
    __tablename__ = "knowledge_questions"
    id = Column(Integer, primary_key=True, index=True)
    tech = Column(String(50), nullable=False)
    question_prompt = Column(Text, nullable=False)
    reference_answer = Column(Text, nullable=True)
    keywords = Column(String(500), nullable=True)  # comma-separated
    created_at = Column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<KnowledgeQuestion {self.tech} - {self.question_prompt[:40]!r}>"
