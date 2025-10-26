from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db.session import Base


class User(Base):
    """ORM model for application users."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # 'candidate' or 'interviewer'
    is_confirmed = Column(Boolean, default=False, nullable=False)
    confirmation_code = Column(String(255), nullable=True)
    reset_code = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    verifications = relationship(
        "EmailVerification", back_populates="user", cascade="all, delete-orphan"
    )


class EmailVerification(Base):
    """Stores one-time verification codes for signup flow."""

    __tablename__ = "email_verifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    consumed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="verifications")
