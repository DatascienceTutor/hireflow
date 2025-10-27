-- SQLite
-- UPDATE candidates 
-- SET email = 'mvsreejith2010@gmail.com' 
-- WHERE candidate_code = 'CAND-2025-001';
DELETE FROM questions
-- DELETE FROM candidates
-- ALTER TABLE candidates ADD COLUMN job_description TEXT;
-- CREATE UNIQUE INDEX idx_resume_hash ON candidates(resume_hash);

-- BEGIN TRANSACTION;

-- -- Drop old table if present
-- DROP TABLE IF EXISTS questions;

-- -- Recreate the questions table
-- CREATE TABLE questions (
--     id INTEGER PRIMARY KEY AUTOINCREMENT,
--     job_code TEXT,
--     question_text TEXT NOT NULL,
--     model_answer TEXT,
--     -- SQLite does not have a native JSON type; JSON can be stored as TEXT.
--     -- If your SQLite has the json1 extension, functions like json_valid() are available.
--     keywords TEXT,                 -- store JSON array/object as TEXT (e.g. '["a","b"]' or '{"k":"v"}')
--     model_answer_embedding TEXT,   -- store numeric list as JSON text (e.g. '[0.123, 0.456]')
--     created_at DATETIME DEFAULT (datetime('now'))  -- UTC timestamp
-- );

-- -- Optional: recreate an index to match your SQLAlchemy model's indexed column
-- CREATE INDEX IF NOT EXISTS idx_questions_job_code ON questions(job_code);

-- COMMIT;

