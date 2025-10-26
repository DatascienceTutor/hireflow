from sqlalchemy.orm import Session
from models.candidate import Candidate
import datetime
import hashlib


def _now_iso():
    return datetime.datetime.utcnow().isoformat()


def _next_candidate_code(db: Session) -> str:
    year = datetime.datetime.utcnow().year
    last = db.query(Candidate).order_by(Candidate.id.desc()).first()
    idx = 1
    if last:
        try:
            tail = last.candidate_code.split("-")[-1]
            idx = int(tail) + 1
        except Exception:
            idx = last.id + 1
    return f"CAND-{year}-{str(idx).zfill(3)}"


def create_candidate(
    db: Session,
    name: str,
    tech=str,
    email=str,
    resume: str = "",
    job_code: str = "",
    job_description: str = "",
) -> Candidate:
    code = _next_candidate_code(db)
    resume_hash = hashlib.sha256(resume.encode()).hexdigest()
    existing_resume_content = (
        db.query(Candidate).filter(Candidate.resume_hash == resume_hash).first()
    )
    if existing_resume_content:
        raise ValueError("A Resume with this content has already been uploaded.")
    cand = Candidate(
        candidate_code=code,
        job_code=job_code,
        email=email,
        name=name,
        resume=resume,
        resume_hash=resume_hash,
        tech=tech,
        job_description=job_description,
        created_at=_now_iso(),
    )
    db.add(cand)
    db.commit()
    db.refresh(cand)
    return cand
