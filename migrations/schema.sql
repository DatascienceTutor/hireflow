-- =================================================================
-- Hire Flow - New Database Schema (for refactored models)
-- =================================================================
-- This script creates all tables from scratch.
-- It is designed for SQLite.
-- -----------------------------------------------------------------

-- Drop tables in reverse order of creation (if they exist)
-- This allows for a clean re-run of the script
DROP TABLE IF EXISTS candidate_answers;
DROP TABLE IF EXISTS interviews;
DROP TABLE IF EXISTS questions;
DROP TABLE IF EXISTS knowledge_questions;
DROP TABLE IF EXISTS candidates;
DROP TABLE IF EXISTS jobs;
DROP TABLE IF EXISTS email_verifications;
DROP TABLE IF EXISTS users;

-- -----------------------------------------------------------------
-- Table: users
-- Stores login information for all user types.
-- -----------------------------------------------------------------
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    is_confirmed BOOLEAN NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

-- -----------------------------------------------------------------
-- Table: email_verifications
-- Stores one-time codes for signup/reset.
-- -----------------------------------------------------------------
CREATE TABLE email_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    expires_at DATETIME NOT NULL,
    consumed BOOLEAN NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    user_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- -----------------------------------------------------------------
-- Table: jobs
-- Stores job postings created by managers.
-- -----------------------------------------------------------------
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_code TEXT NOT NULL UNIQUE,
    tech TEXT NOT NULL,
    title TEXT,
    manager_email TEXT NOT NULL,
    description TEXT,
    description_hash TEXT UNIQUE,
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

-- -----------------------------------------------------------------
-- Table: candidates
-- Stores candidate profiles.
-- -----------------------------------------------------------------
CREATE TABLE candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    tech TEXT NOT NULL,
    resume TEXT,
    resume_hash TEXT UNIQUE,
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

-- -----------------------------------------------------------------
-- Table: knowledge_questions
-- The "Master Bank" of all possible questions.
-- -----------------------------------------------------------------
CREATE TABLE knowledge_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    technology TEXT NOT NULL,
    question_text TEXT NOT NULL,
    model_answer TEXT,
    keywords TEXT, -- Stored as a JSON string
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

-- -----------------------------------------------------------------
-- Table: questions
-- Stores *specific* questions assigned to a *specific* interview.
-- -----------------------------------------------------------------
CREATE TABLE questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_text TEXT NOT NULL,
    model_answer TEXT,
    keywords TEXT, -- Stored as a JSON string
    model_answer_embedding TEXT, -- Stored as a JSON string
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    
    -- Link to the Interview (if Interview is deleted, these questions are deleted)
    interview_id INTEGER NOT NULL,
    
    -- Optional link to the master bank (if master is deleted, set this to NULL)
    knowledge_question_id INTEGER,
    
    FOREIGN KEY (interview_id) REFERENCES interviews(id) ON DELETE CASCADE,
    FOREIGN KEY (knowledge_question_id) REFERENCES knowledge_questions(id) ON DELETE SET NULL
);

-- -----------------------------------------------------------------
-- Table: interviews
-- The central "junction" table linking Jobs and Candidates.
-- -----------------------------------------------------------------
CREATE TABLE interviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL DEFAULT 'Pending',
    evaluation_status TEXT NOT NULL DEFAULT 'Not Evaluated',
    final_score REAL,
    scheduled_at TEXT,
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    
    -- Link to the Job (if Job is deleted, this interview is deleted)
    job_id INTEGER NOT NULL,
    
    -- Link to the Candidate (if Candidate is deleted, this interview is deleted)
    candidate_id INTEGER NOT NULL,
    
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
);

-- -----------------------------------------------------------------
-- Table: candidate_answers
-- Stores a specific candidate's answer for a specific question
-- in a specific interview.
-- -----------------------------------------------------------------
CREATE TABLE candidate_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    answer_text TEXT NOT NULL,
    answer_embedding TEXT, -- Stored as a JSON string
    semantic_similarity REAL,
    llm_score REAL,
    feedback TEXT,
    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    
    -- Link to the Candidate (if Candidate is deleted, this answer is deleted)
    candidate_id INTEGER NOT NULL,
    
    -- Link to the Question (if Question is deleted, this answer is deleted)
    question_id INTEGER NOT NULL,
    
    -- Link to the Interview (if Interview is deleted, this answer is deleted)
    interview_id INTEGER NOT NULL,
    
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
    FOREIGN KEY (interview_id) REFERENCES interviews(id) ON DELETE CASCADE
);

-- -----------------------------------------------------------------
-- Indexes
-- Create indexes for fields that are frequently used in 'WHERE' clauses
-- (PKs, UNIQUE columns, and Foreign Keys are often auto-indexed,
-- but explicit indexes for other common filters are good practice).
-- -----------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_jobs_manager_email ON jobs (manager_email);
CREATE INDEX IF NOT EXISTS ix_knowledge_questions_technology ON knowledge_questions (technology);
CREATE INDEX IF NOT EXISTS ix_questions_interview_id ON questions (interview_id);
CREATE INDEX IF NOT EXISTS ix_interviews_job_id ON interviews (job_id);
CREATE INDEX IF NOT EXISTS ix_interviews_candidate_id ON interviews (candidate_id);
CREATE INDEX IF NOT EXISTS ix_interviews_status ON interviews (status);
CREATE INDEX IF NOT EXISTS ix_candidate_answers_candidate_id ON candidate_answers (candidate_id);
CREATE INDEX IF NOT EXISTS ix_candidate_answers_question_id ON candidate_answers (question_id);
CREATE INDEX IF NOT EXISTS ix_candidate_answers_interview_id ON candidate_answers (interview_id);
