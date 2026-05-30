-- Latest workflow ingest runs (status, row counts, errors)

SELECT
    id,
    source,
    started_at,
    finished_at,
    status,
    rows_processed,
    rows_inserted,
    rows_updated,
    error_message
FROM ingest_runs
ORDER BY started_at DESC
LIMIT 10;
