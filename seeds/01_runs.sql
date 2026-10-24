-- Schema for Celesto Run Ledger
CREATE TABLE IF NOT EXISTS runs (
    run_id VARCHAR(128) PRIMARY KEY,
    sandbox_name VARCHAR(128) NOT NULL UNIQUE,
    problem_id VARCHAR(128) NOT NULL,
    state VARCHAR(64) NOT NULL,
    execution_target VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed row for verification: sandbox name sbx-seeddemo1, state deleted, execution target celesto_sandbox
-- Re-running the SQL does not duplicate it
INSERT INTO runs (run_id, sandbox_name, problem_id, state, execution_target)
VALUES ('run-seeddemo1', 'sbx-seeddemo1', 'job-hunt-research', 'deleted', 'celesto_sandbox')
ON CONFLICT (sandbox_name) DO NOTHING;
