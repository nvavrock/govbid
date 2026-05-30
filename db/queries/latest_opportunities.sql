-- Most recently posted opportunities

SELECT
    notice_id,
    source,
    title,
    agency,
    naics,
    posted_date,
    response_deadline,
    active,
    ui_link
FROM opportunities
ORDER BY posted_date DESC NULLS LAST, created_at DESC
LIMIT 25;
