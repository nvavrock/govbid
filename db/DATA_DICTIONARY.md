# GovBid Database — Data Dictionary

**Database:** `govbid` (default)  
**Schema:** `public`  
**Purpose:** Federal (and future state) contract opportunities, matching scores, ingest audit, and USAspending award context.

Canonical DDL: [`migrations/001_initial.sql`](migrations/001_initial.sql), [`migrations/002_award_dedup_and_scoring.sql`](migrations/002_award_dedup_and_scoring.sql).

## Entity relationships

```
ingest_runs (audit, no FK to facts)

opportunities ──┬── opportunity_contacts
                ├── opportunity_attachments
                ├── match_scores (1:1)
                └── award_enrichment (0:N, optional opportunity_id)

award_enrichment may exist with opportunity_id NULL (agency/NAICS context only)
```

---

## `ingest_runs`

Workflow run audit log (SAM bulk, SAM API, USAspending, etc.).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | BIGSERIAL | NO | auto | Primary key |
| `source` | TEXT | NO | — | Pipeline identifier, e.g. `federal:sam-bulk`, `usaspending:enrichment` |
| `started_at` | TIMESTAMPTZ | NO | `NOW()` | Run start |
| `finished_at` | TIMESTAMPTZ | YES | — | Run end (null while running) |
| `status` | TEXT | NO | `'running'` | `running`, `success`, or `failed` |
| `rows_processed` | INTEGER | YES | `0` | Items read or considered |
| `rows_inserted` | INTEGER | YES | `0` | New rows written |
| `rows_updated` | INTEGER | YES | `0` | Updated rows |
| `error_message` | TEXT | YES | — | Failure detail when `status = 'failed'` |
| `metadata` | JSONB | YES | `'{}'` | Extra run context (URLs, filters, etc.) |

**Indexes:** `(source, started_at DESC)`

---

## `opportunities`

Core notice/solicitation records (federal SAM today; state sources in phase 2).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | BIGSERIAL | NO | auto | Internal surrogate key |
| `notice_id` | TEXT | NO | — | External notice ID (SAM notice ID, state ID, etc.) |
| `source` | TEXT | NO | `'federal:sam'` | Origin namespace, e.g. `federal:sam`, `state:CA` |
| `solicitation_number` | TEXT | YES | — | Solicitation / RFQ number |
| `title` | TEXT | YES | — | Opportunity title (used in keyword scoring) |
| `posted_date` | DATE | YES | — | Posted date |
| `response_deadline` | TIMESTAMPTZ | YES | — | Response / due datetime |
| `naics` | TEXT | YES | — | NAICS code |
| `psc` | TEXT | YES | — | Product/Service Code |
| `set_aside` | TEXT | YES | — | Set-aside description (human-readable) |
| `set_aside_code` | TEXT | YES | — | Set-aside code if available |
| `procurement_type` | TEXT | YES | — | SAM procurement type (`o`, `k`, `p`, `r`, etc.) |
| `agency` | TEXT | YES | — | Awarding / issuing agency name |
| `office` | TEXT | YES | — | Sub-agency or office |
| `place_of_performance` | TEXT | YES | — | Place of performance text |
| `state_code` | TEXT | YES | — | US state code when relevant |
| `ui_link` | TEXT | YES | — | Link to notice in source portal |
| `description_url` | TEXT | YES | — | Link to full description / attachments page |
| `active` | BOOLEAN | NO | `TRUE` | `FALSE` when notice is closed or cancelled |
| `raw_data` | JSONB | YES | `'{}'` | Full parsed payload from ingest |
| `created_at` | TIMESTAMPTZ | NO | `NOW()` | First insert time |
| `updated_at` | TIMESTAMPTZ | NO | `NOW()` | Last update (trigger-maintained) |

**Constraints:** `UNIQUE (notice_id, source)`  
**Indexes:** partial on `response_deadline` (active + deadline set); `naics`, `posted_date DESC`, `source`  
**Triggers:** `set_updated_at()` on UPDATE

| `source` value | Meaning |
|----------------|---------|
| `federal:sam` | SAM.gov (bulk or API) |
| `state:XX` | State portal (phase 2) |

---

## `opportunity_contacts`

Points of contact for an opportunity (schema ready; not all workflows populate yet).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | BIGSERIAL | NO | auto | Primary key |
| `opportunity_id` | BIGINT | NO | — | FK → `opportunities.id` (CASCADE delete) |
| `contact_type` | TEXT | YES | — | Role, e.g. primary, contracting officer |
| `name` | TEXT | YES | — | Contact name |
| `email` | TEXT | YES | — | Email |
| `phone` | TEXT | YES | — | Phone |
| `created_at` | TIMESTAMPTZ | NO | `NOW()` | Insert time |

---

## `opportunity_attachments`

Resource links / attachments for an opportunity.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | BIGSERIAL | NO | auto | Primary key |
| `opportunity_id` | BIGINT | NO | — | FK → `opportunities.id` (CASCADE delete) |
| `url` | TEXT | NO | — | Attachment or document URL |
| `description` | TEXT | YES | — | Label or description |
| `created_at` | TIMESTAMPTZ | NO | `NOW()` | Insert time |

---

## `match_scores`

Rule-based fit score and human review state (one row per opportunity).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | BIGSERIAL | NO | auto | Primary key |
| `opportunity_id` | BIGINT | NO | — | FK → `opportunities.id` (CASCADE delete) |
| `rule_score` | SMALLINT | NO | `0` | 0–100 match score |
| `match_reasons` | JSONB | YES | `'[]'` | Array of reason strings (see below) |
| `review_status` | TEXT | NO | `'pending'` | Human workflow status |
| `reviewed_at` | TIMESTAMPTZ | YES | — | When review status last changed |
| `notes` | TEXT | YES | — | Reviewer notes |
| `scored_at` | TIMESTAMPTZ | NO | `NOW()` | Last score computation time |

**Constraints:** `UNIQUE (opportunity_id)`; `rule_score` between 0 and 100  
**`review_status` values:** `pending`, `reviewing`, `bid`, `pass`, `expired`

| `match_reasons` entry | Meaning |
|-----------------------|---------|
| `naics_match` | NAICS in configured list (+40) |
| `psc_match` | PSC matches configured prefix (+20) |
| `keyword:<word>` | Title contains include keyword (+10 each, max +30) |
| `exclude:<word>` | Title contains exclude keyword (−50) |
| `set_aside_excluded` | Set-aside not bidable (score forced to 0) |

Populated/refreshed by `refresh_match_scores()` after ingest.

---

## `award_enrichment`

Historical award context from USAspending (workflow `03`), keyed by agency + NAICS.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | BIGSERIAL | NO | auto | Primary key |
| `opportunity_id` | BIGINT | YES | — | Optional FK → `opportunities.id` (SET NULL on delete) |
| `awarding_agency` | TEXT | YES | — | Awarding agency name |
| `naics_code` | TEXT | YES | — | NAICS on the award |
| `psc_code` | TEXT | YES | — | PSC on the award |
| `recipient_name` | TEXT | YES | — | Awardee / recipient |
| `award_amount` | NUMERIC(18,2) | YES | — | Award dollar amount |
| `award_date` | DATE | YES | — | Award start date |
| `usaspending_award_id` | TEXT | YES | — | USAspending award identifier |
| `raw_data` | JSONB | YES | `'{}'` | Full API row |
| `enriched_at` | TIMESTAMPTZ | NO | `NOW()` | When row was stored or updated |

**Indexes:** `(awarding_agency, naics_code)`; `(opportunity_id)`  
**Unique (migration 002):** `usaspending_award_id` where not null — upserts dedupe weekly runs

Used in [`queries/review_queue.sql`](queries/review_queue.sql) as `related_awards_count`.

---

## Functions

| Function | Returns | Purpose |
|----------|---------|---------|
| `set_updated_at()` | trigger | Sets `opportunities.updated_at` on UPDATE |
| `compute_rule_score(...)` | `score`, `reasons` | Scoring logic for one opportunity |
| `refresh_match_scores(...)` | INTEGER (row count) | Recomputes all active opportunities’ `match_scores` |

**Scoring weights (defaults in `refresh_match_scores`):**

| Rule | Points |
|------|--------|
| NAICS in list | +40 |
| PSC prefix match | +20 |
| Each include keyword in title | +10 (max +30 total) |
| Exclude keyword in title | −50 |
| Excluded set-aside | score → 0 |
| Cap | 100 |

Default arrays mirror [`config/match-profile.example.yaml`](../config/match-profile.example.yaml).

---

## Extensions

| Extension | Use |
|-----------|-----|
| `pgcrypto` | Available for future UUID/crypto needs |
