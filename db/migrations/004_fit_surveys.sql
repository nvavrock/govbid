-- Opportunity fit surveys for RAG + human-in-the-loop scoring feedback

CREATE TABLE IF NOT EXISTS consig_fit_surveys (
    id              BIGSERIAL PRIMARY KEY,
    notice_id       TEXT NOT NULL,
    opportunity_id  BIGINT REFERENCES opportunities (id) ON DELETE SET NULL,
    review_status   TEXT NOT NULL
                    CHECK (review_status IN ('pending', 'reviewing', 'bid', 'pass', 'expired')),
    rule_score      INT,
    fit_rating      INT NOT NULL CHECK (fit_rating >= 1 AND fit_rating <= 5),
    score_accurate  BOOLEAN,
    score_direction TEXT CHECK (
                        score_direction IS NULL
                        OR score_direction IN ('too_high', 'too_low', 'about_right')
                    ),
    good_tags       JSONB NOT NULL DEFAULT '[]'::jsonb,
    bad_tags        JSONB NOT NULL DEFAULT '[]'::jsonb,
    good_notes      TEXT,
    bad_notes       TEXT,
    lessons_learned TEXT,
    indexed_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fit_surveys_notice ON consig_fit_surveys (notice_id);
CREATE INDEX IF NOT EXISTS idx_fit_surveys_created ON consig_fit_surveys (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_fit_surveys_unindexed ON consig_fit_surveys (indexed_at) WHERE indexed_at IS NULL;
