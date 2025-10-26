from sqlalchemy import Column, Integer, Text, Float, ForeignKey, String
from db.session import Base


class Answer(Base):
    __tablename__ = "answers"
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    answer_text = Column(Text, nullable=True)
    ai_score = Column(Float, nullable=True)  # 0-100
    validated = Column(Integer, default=0)
    created_at = Column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<Answer {self.id} score={self.ai_score}>"
