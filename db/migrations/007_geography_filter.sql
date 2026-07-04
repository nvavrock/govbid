-- Geography preferences on fit profiles; work mode on opportunities

ALTER TABLE fit_profiles
    ADD COLUMN IF NOT EXISTS home_states JSONB NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS include_remote BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS include_unknown_location BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE opportunities
    ADD COLUMN IF NOT EXISTS work_mode TEXT
    CHECK (work_mode IS NULL OR work_mode IN ('remote', 'onsite', 'unknown'));

CREATE INDEX IF NOT EXISTS idx_opportunities_state_code
    ON opportunities (state_code)
    WHERE state_code IS NOT NULL AND active = TRUE;

CREATE INDEX IF NOT EXISTS idx_opportunities_work_mode
    ON opportunities (work_mode)
    WHERE active = TRUE;
