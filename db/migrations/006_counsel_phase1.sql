-- Counsel Phase 1: fit profiles, fit bands, best-fit queue support

CREATE TABLE IF NOT EXISTS fit_profiles (
    id                  BIGSERIAL PRIMARY KEY,
    slug                TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    capabilities        TEXT,
    naics_codes         JSONB NOT NULL DEFAULT '[]'::jsonb,
    psc_prefixes        JSONB NOT NULL DEFAULT '[]'::jsonb,
    include_keywords    JSONB NOT NULL DEFAULT '[]'::jsonb,
    exclude_keywords    JSONB NOT NULL DEFAULT '[]'::jsonb,
    exclude_set_asides  JSONB NOT NULL DEFAULT '[]'::jsonb,
    eligible_set_asides JSONB NOT NULL DEFAULT '[]'::jsonb,
    weights             JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_default          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_fit_profiles_default
    ON fit_profiles (is_default) WHERE is_default = TRUE;

ALTER TABLE match_scores
    ADD COLUMN IF NOT EXISTS fit_band TEXT
    CHECK (fit_band IS NULL OR fit_band IN ('strong', 'good', 'stretch', 'none'));

CREATE OR REPLACE FUNCTION compute_fit_band(p_score SMALLINT, p_reasons JSONB)
RETURNS TEXT AS $$
BEGIN
    IF p_reasons IS NULL
       OR jsonb_array_length(p_reasons) = 0
       OR p_reasons @> '["set_aside_excluded"]'::jsonb THEN
        RETURN 'none';
    END IF;
    IF p_score >= 50 THEN
        RETURN 'strong';
    ELSIF p_score >= 25 THEN
        RETURN 'good';
    ELSE
        RETURN 'stretch';
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

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
    INSERT INTO match_scores (opportunity_id, rule_score, match_reasons, fit_band)
    SELECT
        o.id,
        s.score,
        s.reasons,
        compute_fit_band(s.score, s.reasons)
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
        fit_band = EXCLUDED.fit_band,
        scored_at = NOW();

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;
