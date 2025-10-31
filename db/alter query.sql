-- SQLite
-- DELETE Records from tables ##START##
-- DELETE FROM answers;
-- DELETE FROM candidate_answers;
-- DELETE FROM candidates;
-- DELETE FROM email_verifications;
DELETE FROM interviews;
-- DELETE FROM jobs;
-- DELETE FROM knowledge_questions;
-- DELETE FROM questions;
-- -- DELETE FROM users;
-- DELETE FROM sqlite_sequence WHERE name='answers';
-- DELETE FROM sqlite_sequence WHERE name='candidate_answers';
-- DELETE FROM sqlite_sequence WHERE name='candidates';
-- DELETE FROM sqlite_sequence WHERE name='email_verifications';
DELETE FROM sqlite_sequence WHERE name='interviews';
-- DELETE FROM sqlite_sequence WHERE name='jobs';
-- DELETE FROM sqlite_sequence WHERE name='questions';
-- DELETE FROM sqlite_sequence WHERE name='knowledge_questions';
-- DELETE FROM sqlite_sequence WHERE name='users';
-- DELETE Records from tables ##END##

-- ALTER TABLE jobs ADD COLUMN manager_email TEXT;

UPDATE interviews 
SET status = 'Completed'
WHERE job_id = 'JD-2025-002' AND candidate_id = 'CAND-2025-001'; 


UPDATE interviews 
SET evaluation_status = 'LLM Evaluvation Completed'
WHERE job_id = 'JD-2025-002' AND candidate_id = 'CAND-2025-001'; 

-- UPDATE jobs 
-- SET manager_email = 'mvsreejith0@gmail.com'
-- WHERE job_code = 'JD-2025-001'; 

-- UPDATE candidates 
-- SET interview_completed = False 
-- WHERE candidate_code = 'CAND-2025-001';

UPDATE candidates 
SET email = 'mvsreejith2010@gmail.com' 
WHERE candidate_code = 'CAND-2025-001';
-- DELETE FROM candidate_answers;
-- DELETE FROM sqlite_sequence WHERE name='candidate_answers';
-- DELETE FROM questions;
-- DELETE FROM sqlite_sequence WHERE name='questions';
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

