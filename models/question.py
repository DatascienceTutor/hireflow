from sqlalchemy import Column, Integer, String, Text, ForeignKey
from db.session import Base


class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    prompt = Column(Text, nullable=False)
    source_knowledge_id = Column(
        Integer, ForeignKey("knowledge_questions.id"), nullable=True
    )
    approved = Column(Integer, default=0)
    created_at = Column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<Question {self.id} interview={self.interview_id} approved={self.approved}>"
