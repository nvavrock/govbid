-- Top opportunities for human review (Adminer / run-query.sh defaults).
-- CLI and Consig use config/match-profile.yaml via scripts/lib/review_queue_lib.py.
-- Keep params CTE roughly in sync with match-profile.yaml → review:

WITH params AS (
    SELECT
        30  AS days_ahead,
        25  AS min_score,
        25  AS top_n
)
SELECT
    o.notice_id,
    o.solicitation_number,
    o.title,
    o.agency,
    o.naics,
    o.psc,
    o.set_aside,
    o.posted_date,
    o.response_deadline,
    o.ui_link,
    o.description_url,
    m.rule_score,
    m.match_reasons,
    m.review_status,
    (
        SELECT COUNT(*)
        FROM award_enrichment ae
        WHERE ae.naics_code = o.naics
          AND ae.awarding_agency = o.agency
    ) AS related_awards_count
FROM opportunities o
JOIN match_scores m ON m.opportunity_id = o.id
CROSS JOIN params p
WHERE o.active = TRUE
  AND o.source LIKE 'federal:%'
  AND m.review_status = 'pending'
  AND m.rule_score >= p.min_score
  AND (
      o.response_deadline IS NULL
      OR o.response_deadline >= NOW()
  )
  AND (
      o.response_deadline IS NULL
      OR o.response_deadline <= NOW() + (p.days_ahead || ' days')::INTERVAL
  )
ORDER BY m.rule_score DESC, o.response_deadline ASC NULLS LAST
LIMIT (SELECT top_n FROM params);
