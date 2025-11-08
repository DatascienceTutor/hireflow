from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from db.session import Base

class QuestionFeedback(Base):
    __tablename__ = "question_feedback"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"))
    manager_id = Column(Integer, ForeignKey("users.id"))
    is_good = Column(Boolean, default=True)
    feedback = Column(String)

    question = relationship("Question", back_populates="feedback")
    manager = relationship("User")
