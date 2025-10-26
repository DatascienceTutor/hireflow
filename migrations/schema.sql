CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    role TEXT NOT NULL,
    is_confirmed INTEGER NOT NULL DEFAULT 0,
    confirmation_code TEXT,
    reset_code TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_code TEXT NOT NULL UNIQUE,
    tech TEXT NOT NULL,              -- one of the 10 technologies
    title TEXT,
    description TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    email TEXT,
    resume TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS interviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    candidate_id INTEGER NOT NULL,
    status TEXT DEFAULT 'Pending',   -- Pending, Completed, Evaluated, etc.
    evaluation_status TEXT DEFAULT 'Not evaluated', -- Not evaluated, Evaluated
    final_score REAL DEFAULT NULL,   -- 1.0 - 10.0 (final normalized score)
    scheduled_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (candidate_id) REFERENCES candidates(id)
);

CREATE TABLE IF NOT EXISTS knowledge_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tech TEXT NOT NULL,              -- technology tag
    question_prompt TEXT NOT NULL,
    reference_answer TEXT,           -- optional reference / canonical answer (populated by GPT later)
    keywords TEXT,                   -- comma-separated keywords (optional)
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    source_knowledge_id INTEGER,     -- optional link back to knowledge_questions.id
    approved INTEGER DEFAULT 0,      -- 0/1 (manager approved)
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (interview_id) REFERENCES interviews(id),
    FOREIGN KEY (source_knowledge_id) REFERENCES knowledge_questions(id)
);

CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    answer_text TEXT,
    ai_score REAL,
    validated INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (question_id) REFERENCES questions(id)
);
