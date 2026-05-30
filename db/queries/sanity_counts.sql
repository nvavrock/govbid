-- Row counts for main tables (quick sanity check after ingest)

SELECT
    (SELECT COUNT(*) FROM opportunities) AS opportunities,
    (SELECT COUNT(*) FROM match_scores) AS match_scores,
    (SELECT COUNT(*) FROM ingest_runs) AS ingest_runs,
    (SELECT COUNT(*) FROM award_enrichment) AS award_enrichment;
