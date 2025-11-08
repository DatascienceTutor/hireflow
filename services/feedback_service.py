from sqlalchemy.orm import Session
from models.question_feedback import QuestionFeedback

def add_feedback(db: Session, question_id: int, manager_id: int, is_good: bool, feedback: str = None, commit: bool = True):
    """
    Adds feedback for a question to the database.
    Optionally allows for committing the transaction.
    """
    db_feedback = QuestionFeedback(
        question_id=question_id,
        manager_id=manager_id,
        is_good=is_good,
        feedback=feedback,
    )
    db.add(db_feedback)
    if commit:
        db.commit()
        db.refresh(db_feedback)
    return db_feedback

