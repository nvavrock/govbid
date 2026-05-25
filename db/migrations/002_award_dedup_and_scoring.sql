-- Award deduplication + clearer keyword scoring (safe to re-run)

CREATE UNIQUE INDEX IF NOT EXISTS idx_award_enrichment_usaspending_id
    ON award_enrichment (usaspending_award_id)
    WHERE usaspending_award_id IS NOT NULL;

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

    IF p_naics IS NOT NULL AND p_naics = ANY (p_naics_list) THEN
        v_score := v_score + 40;
        v_reasons := v_reasons || jsonb_build_array('naics_match');
    END IF;

    IF p_psc IS NOT NULL AND EXISTS (
        SELECT 1 FROM unnest(p_psc_prefixes) AS prefix
        WHERE p_psc LIKE prefix || '%'
    ) THEN
        v_score := v_score + 20;
        v_reasons := v_reasons || jsonb_build_array('psc_match');
    END IF;

    FOREACH v_kw IN ARRAY p_include_keywords LOOP
        IF position(lower(v_kw) IN v_text) > 0 THEN
            v_kw_score := v_kw_score + 10;
            v_reasons := v_reasons || jsonb_build_array('keyword:' || v_kw);
        END IF;
    END LOOP;
    v_score := v_score + LEAST(v_kw_score, 30);

    FOREACH v_kw IN ARRAY p_exclude_keywords LOOP
        IF position(lower(v_kw) IN v_text) > 0 THEN
            v_score := GREATEST(0, v_score - 50);
            v_reasons := v_reasons || jsonb_build_array('exclude:' || v_kw);
        END IF;
    END LOOP;

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
