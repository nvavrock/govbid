-- Rename Consig tables to Counsel (rebrand; idempotent where already renamed).

DO $$
BEGIN
  IF to_regclass('public.consig_sessions') IS NOT NULL
     AND to_regclass('public.counsel_sessions') IS NULL THEN
    ALTER TABLE consig_sessions RENAME TO counsel_sessions;
  END IF;
  IF to_regclass('public.consig_messages') IS NOT NULL
     AND to_regclass('public.counsel_messages') IS NULL THEN
    ALTER TABLE consig_messages RENAME TO counsel_messages;
  END IF;
  IF to_regclass('public.consig_feedback') IS NOT NULL
     AND to_regclass('public.counsel_feedback') IS NULL THEN
    ALTER TABLE consig_feedback RENAME TO counsel_feedback;
  END IF;
  IF to_regclass('public.consig_fit_surveys') IS NOT NULL
     AND to_regclass('public.counsel_fit_surveys') IS NULL THEN
    ALTER TABLE consig_fit_surveys RENAME TO counsel_fit_surveys;
  END IF;
END
$$;

-- Rename indexes that still carry the old prefix (ignore if absent).
DO $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN
    SELECT indexname
    FROM pg_indexes
    WHERE schemaname = 'public'
      AND indexname LIKE 'idx_consig_%'
  LOOP
    EXECUTE format(
      'ALTER INDEX %I RENAME TO %I',
      r.indexname,
      replace(r.indexname, 'idx_consig_', 'idx_counsel_')
    );
  END LOOP;
END
$$;
