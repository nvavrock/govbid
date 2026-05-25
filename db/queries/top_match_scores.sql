-- Highest rule scores (broader than review_queue — no deadline/status filters)

SELECT
    o.notice_id,
    o.title,
    o.agency,
    o.naics,
    m.rule_score,
    m.review_status,
    m.match_reasons
FROM opportunities o
JOIN match_scores m ON m.opportunity_id = o.id
ORDER BY m.rule_score DESC
LIMIT 20;
