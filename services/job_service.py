from sqlalchemy.orm import Session
from models.job import Job
import datetime
import hashlib


def _now_iso() -> str:
    return datetime.datetime.utcnow().isoformat()


def _next_job_code(db: Session) -> str:
    # (function remains the same)
    year = datetime.datetime.utcnow().year
    last = db.query(Job).order_by(Job.id.desc()).first()
    idx = 1
    if last:
        try:
            tail = last.job_code.split("-")[-1]
            idx = int(tail) + 1
        except Exception:
            idx = last.id + 1
    return f"JD-{year}-{str(idx).zfill(3)}"


def create_job(db: Session, tech: str, title: str, description: str,manager_email: str) -> Job:
    # Generate a hash of the description content
    description_hash = hashlib.sha256(description.encode()).hexdigest()
    if not manager_email:
        raise ValueError("Manager email is required to create a job.")

    # Check for duplicate job title
    existing_job_title = db.query(Job).filter(Job.title == title).first()
    if existing_job_title:
        raise ValueError(f"A job with the title '{title}' already exists.")

    # Check for duplicate job description content
    existing_job_content = (
        db.query(Job).filter(Job.description_hash == description_hash).first()
    )
    if existing_job_content:
        raise ValueError(
            "A job with this description content has already been uploaded."
        )

    job_code = _next_job_code(db)
    j = Job(
        job_code=job_code,
        tech=tech,
        title=title,
        description=description,
        description_hash=description_hash,
        manager_email=manager_email,
        created_at=_now_iso(),
    )
    db.add(j)
    db.commit()
    db.refresh(j)
    return j


def list_jobs(db: Session):
    return db.query(Job).order_by(Job.id.desc()).all()
