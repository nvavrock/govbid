-- Consig sessions, chat history, feedback, and capture preferences

CREATE TABLE IF NOT EXISTS consig_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS consig_messages (
    id          BIGSERIAL PRIMARY KEY,
    session_id  UUID NOT NULL REFERENCES consig_sessions (id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content     TEXT NOT NULL,
    notice_id   TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_consig_messages_session ON consig_messages (session_id, created_at);

CREATE TABLE IF NOT EXISTS consig_feedback (
    id           BIGSERIAL PRIMARY KEY,
    notice_id    TEXT NOT NULL,
    action       TEXT NOT NULL,
    user_reason  TEXT,
    helpful      BOOLEAN,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_consig_feedback_notice ON consig_feedback (notice_id);
CREATE INDEX IF NOT EXISTS idx_consig_feedback_created ON consig_feedback (created_at DESC);

CREATE TABLE IF NOT EXISTS capture_preferences (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL DEFAULT '{}',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
