-- Government contracts pipeline — initial schema

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- Ingest audit
-- ---------------------------------------------------------------------------
CREATE TABLE ingest_runs (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'success', 'failed')),
    rows_processed  INTEGER DEFAULT 0,
    rows_inserted   INTEGER DEFAULT 0,
    rows_updated    INTEGER DEFAULT 0,
    error_message   TEXT,
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX idx_ingest_runs_source_started ON ingest_runs (source, started_at DESC);

-- ---------------------------------------------------------------------------
-- Opportunities (federal + state)
-- ---------------------------------------------------------------------------
CREATE TABLE opportunities (
    id                  BIGSERIAL PRIMARY KEY,
    notice_id           TEXT NOT NULL,
    source              TEXT NOT NULL DEFAULT 'federal:sam',
    solicitation_number TEXT,
    title               TEXT,
    posted_date         DATE,
    response_deadline   TIMESTAMPTZ,
    naics               TEXT,
    psc                 TEXT,
    set_aside           TEXT,
    set_aside_code      TEXT,
    procurement_type    TEXT,
    agency              TEXT,
    office              TEXT,
    place_of_performance TEXT,
    state_code          TEXT,
    ui_link             TEXT,
    description_url     TEXT,
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    raw_data            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (notice_id, source)
);

CREATE INDEX idx_opportunities_deadline ON opportunities (response_deadline)
    WHERE active AND response_deadline IS NOT NULL;
CREATE INDEX idx_opportunities_naics ON opportunities (naics);
CREATE INDEX idx_opportunities_posted ON opportunities (posted_date DESC);
CREATE INDEX idx_opportunities_source ON opportunities (source);

-- ---------------------------------------------------------------------------
-- Point of contact
-- ---------------------------------------------------------------------------
CREATE TABLE opportunity_contacts (
    id              BIGSERIAL PRIMARY KEY,
    opportunity_id  BIGINT NOT NULL REFERENCES opportunities (id) ON DELETE CASCADE,
    contact_type    TEXT,
    name            TEXT,
    email           TEXT,
    phone           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_opportunity_contacts_opp ON opportunity_contacts (opportunity_id);

-- ---------------------------------------------------------------------------
-- Attachments / resource links
-- ---------------------------------------------------------------------------
CREATE TABLE opportunity_attachments (
    id              BIGSERIAL PRIMARY KEY,
    opportunity_id  BIGINT NOT NULL REFERENCES opportunities (id) ON DELETE CASCADE,
    url             TEXT NOT NULL,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_opportunity_attachments_opp ON opportunity_attachments (opportunity_id);

-- ---------------------------------------------------------------------------
-- Match scores and human review
-- ---------------------------------------------------------------------------
CREATE TABLE match_scores (
    id              BIGSERIAL PRIMARY KEY,
    opportunity_id  BIGINT NOT NULL REFERENCES opportunities (id) ON DELETE CASCADE,
    rule_score      SMALLINT NOT NULL DEFAULT 0 CHECK (rule_score BETWEEN 0 AND 100),
    match_reasons   JSONB DEFAULT '[]',
    review_status   TEXT NOT NULL DEFAULT 'pending'
                    CHECK (review_status IN ('pending', 'reviewing', 'bid', 'pass', 'expired')),
    reviewed_at     TIMESTAMPTZ,
    notes           TEXT,
    scored_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (opportunity_id)
);

CREATE INDEX idx_match_scores_rule ON match_scores (rule_score DESC);
CREATE INDEX idx_match_scores_review ON match_scores (review_status)
    WHERE review_status = 'pending';

-- ---------------------------------------------------------------------------
-- USAspending award enrichment
-- ---------------------------------------------------------------------------
CREATE TABLE award_enrichment (
    id                  BIGSERIAL PRIMARY KEY,
    opportunity_id      BIGINT REFERENCES opportunities (id) ON DELETE SET NULL,
    awarding_agency     TEXT,
    naics_code          TEXT,
    psc_code            TEXT,
    recipient_name      TEXT,
    award_amount        NUMERIC(18, 2),
    award_date          DATE,
    usaspending_award_id TEXT,
    raw_data            JSONB DEFAULT '{}',
    enriched_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_award_enrichment_agency_naics ON award_enrichment (awarding_agency, naics_code);
CREATE INDEX idx_award_enrichment_opp ON award_enrichment (opportunity_id);

-- ---------------------------------------------------------------------------
-- updated_at trigger
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_opportunities_updated_at
    BEFORE UPDATE ON opportunities
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ---------------------------------------------------------------------------
-- Scoring function (used by review query and can be called from app)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION compute_rule_score(
    p_naics TEXT,
    p_psc TEXT,
    p_title TEXT,
    p_set_aside TEXT,
    p_naics_list TEXT[],
    p_psc_prefixes TEXT[],
    p_include_keywords TEXT[],
    p_exclude_keywords TEXT[],
    p_exclude_set_asides TEXT[]
)
RETURNS TABLE (score SMALLINT, reasons JSONB) AS $$
DECLARE
    v_score SMALLINT := 0;
    v_reasons JSONB := '[]'::JSONB;
    v_text TEXT;
    v_kw TEXT;
    v_kw_score SMALLINT := 0;
BEGIN
    v_text := lower(coalesce(p_title, ''));

    -- NAICS match (+40)
    IF p_naics IS NOT NULL AND p_naics = ANY (p_naics_list) THEN
        v_score := v_score + 40;
        v_reasons := v_reasons || jsonb_build_array('naics_match');
    END IF;

    -- PSC prefix (+20)
    IF p_psc IS NOT NULL AND EXISTS (
        SELECT 1 FROM unnest(p_psc_prefixes) AS prefix
        WHERE p_psc LIKE prefix || '%'
    ) THEN
        v_score := v_score + 20;
        v_reasons := v_reasons || jsonb_build_array('psc_match');
    END IF;

    -- Include keywords (+10 each, max 30 from keywords)
    FOREACH v_kw IN ARRAY p_include_keywords LOOP
        IF position(lower(v_kw) IN v_text) > 0 THEN
            v_kw_score := v_kw_score + 10;
            v_reasons := v_reasons || jsonb_build_array('keyword:' || v_kw);
        END IF;
    END LOOP;
    v_score := v_score + LEAST(v_kw_score, 30);

    -- Exclude keywords (-50)
    FOREACH v_kw IN ARRAY p_exclude_keywords LOOP
        IF position(lower(v_kw) IN v_text) > 0 THEN
            v_score := GREATEST(0, v_score - 50);
            v_reasons := v_reasons || jsonb_build_array('exclude:' || v_kw);
        END IF;
    END LOOP;

    -- Set-aside exclusion
    IF p_set_aside IS NOT NULL AND EXISTS (
        SELECT 1 FROM unnest(p_exclude_set_asides) AS ex
        WHERE lower(p_set_aside) LIKE '%' || lower(ex) || '%'
    ) THEN
        v_score := 0;
        v_reasons := v_reasons || jsonb_build_array('set_aside_excluded');
    END IF;

    score := LEAST(100, v_score);
    reasons := v_reasons;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Refresh match_scores for all active opportunities (called after ingest)
CREATE OR REPLACE FUNCTION refresh_match_scores(
    p_naics_list TEXT[] DEFAULT ARRAY['541511','541512','541519','518210','511210'],
    p_psc_prefixes TEXT[] DEFAULT ARRAY['D3','7E'],
    p_include_keywords TEXT[] DEFAULT ARRAY['software','application','cloud','devsecops','cybersecurity','api','modernization','saas','database','agile'],
    p_exclude_keywords TEXT[] DEFAULT ARRAY['construction','janitorial','landscaping','hardware only','furniture','vehicles'],
    p_exclude_set_asides TEXT[] DEFAULT ARRAY['8(a)','HUBZone','SDVOSB','WOSB','EDWOSB']
)
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    INSERT INTO match_scores (opportunity_id, rule_score, match_reasons)
    SELECT o.id, s.score, s.reasons
    FROM opportunities o
    CROSS JOIN LATERAL compute_rule_score(
        o.naics, o.psc, o.title, o.set_aside,
        p_naics_list, p_psc_prefixes, p_include_keywords,
        p_exclude_keywords, p_exclude_set_asides
    ) AS s(score, reasons)
    WHERE o.active = TRUE
    ON CONFLICT (opportunity_id) DO UPDATE SET
        rule_score = EXCLUDED.rule_score,
        match_reasons = EXCLUDED.match_reasons,
        scored_at = NOW();

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;
