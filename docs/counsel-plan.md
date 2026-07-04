# Counsel — product plan

**Owner:** Rocksteady Analytics  
**Last updated:** 2026-07-04  
**Status:** Rebrand from Consig complete; multi-user fit dashboard is the next product phase.

---

## Vision

**Counsel** is a capture advisor for **any** contractor profile — not a single-owner IT pipeline.

Users describe what they are good at (NAICS, capabilities, certifications, geography, contract size, set-asides). Counsel surfaces **best-fit** federal opportunities from the full SAM bulk extract, ranked by relevance — not a rigid pass/fail grade.

```
SAM bulk CSV (all opportunities) → Postgres
         ↓
User / org fit profile(s)  →  match reasons  →  ranked queue  →  Counsel chat + dashboard
```

**Design principle:** Prefer **“best fit for you”** over **“score ≥ 25.”** Scores become optional ranking signals; the primary output is an ordered list with plain-language reasons.

---

## What exists today

| Piece | Today | Limitation |
|-------|--------|------------|
| Ingest filter | `passes_ingest_filter()` in `scripts/lib/match_profile.py` | **IT-only** — drops most CSV rows before Postgres |
| Match profile | Single file `config/match-profile.yaml` | One global profile, not per user |
| Scoring | `rule_score` 0–100 + `match_reasons` jsonb | Feels like grading; tuned for IT keywords |
| Review queue | `db/queries/review_queue.sql` + `min_score` gate | Hides rows below threshold |
| UI | Streamlit `counsel/ui.py` | Built for one reviewer |
| RAG chat | Chroma + OpenAI | Capture corpus; works for any vertical with right profile |

---

## Target experience

### 1. User fit profile (dashboard input)

Each user (or organization) defines:

- **Business name** and capability statement (free text)
- **NAICS** and **PSC** codes they pursue
- **Include keywords** (what they want)
- **Exclude keywords** (hard no)
- **Set-aside eligibility** (what they can bid, not just what to skip)
- **Optional:** max/min contract size, agencies of interest, states, procurement types

Stored in Postgres (new tables — see below), editable in the dashboard. YAML file remains for CLI/cron until migrated.

### 2. Full-funnel ingest

- Load **all active opportunities** from SAM CSV (or a configurable broad filter, e.g. active + deadline in next N days).
- Stop pre-filtering to IT-only at ingest time.
- Compute fit **per profile** at query time or via a background job — not at ingest.

### 3. Best-fit ranking (not grading)

Replace “you scored 60” with:

- **Rank** (1…N) within the user’s queue
- **Match reasons** (existing jsonb): `naics_match`, `keyword:cloud`, `set_aside_eligible`, etc.
- **Optional fit band:** Strong / Good / Stretch — derived from reason count and user weights, not a fixed 0–100 scale

**User-customizable weights (later):**

| Dimension | Default | User can dial |
|-----------|---------|----------------|
| NAICS exact match | high | slider or priority |
| PSC prefix | medium | |
| Keyword hits | medium | add/remove keywords in UI |
| Set-aside alignment | high | |
| Deadline proximity | low | |

No requirement to expose numeric weights in v1 — **keyword + NAICS picker in the dashboard** may be enough.

### 4. Dashboard (multi-user)

v1 screens:

1. **My fit profile** — edit criteria (form backed by DB)
2. **Best fits** — ranked table: title, agency, deadline, reasons, SAM link
3. **Opportunity detail** — notes, status (`pending` / `reviewing` / `bid` / `pass`), Counsel chat for this notice
4. **Admin (optional)** — ingest status, last run

Auth: start with local/single-tenant; add login when deploying beyond localhost.

---

## Data model (proposed)

```sql
-- One row per user or org
fit_profiles (
  id, name, owner_user_id nullable,
  capabilities text,
  naics_codes jsonb,
  psc_prefixes jsonb,
  include_keywords jsonb,
  exclude_keywords jsonb,
  eligible_set_asides jsonb,
  weights jsonb,          -- optional dimension weights
  created_at, updated_at
)

-- Per-profile scores (replaces single global match_scores semantics)
opportunity_fits (
  opportunity_id, profile_id,
  rank_score,             -- internal sort key, not shown as "grade"
  fit_band,               -- strong | good | stretch
  match_reasons jsonb,
  review_status, notes,
  UNIQUE (opportunity_id, profile_id)
)
```

Migration path: keep `match_scores` for backward compat; add `fit_profiles` + `opportunity_fits`; backfill default profile from `match-profile.yaml`.

---

## Implementation phases

### Phase 1 — Broaden the funnel (1–2 days)

- [x] Ingest: `INGEST_MODE=full|filtered` (default `full`)
- [x] Remove IT-only gate when `full` (active rows only)
- [x] `fit_profiles` table + sync from `match-profile.yaml`
- [x] Best-fit queue: `fit_band` + `require_match_reasons` (no hard min_score)
- [x] Re-ingest full SAM CSV after migration 006 (76,824 active rows, 2026-07-04)

### Phase 2 — Fit profile in UI (3–5 days)

- [x] CRUD API + Streamlit page for `fit_profiles`
- [x] “Best fits” tab ranks by `fit_band` (uses `match_scores` until `opportunity_fits` exists)
- [x] Drop min_score slider in UI; sort by fit band + relevance

### Phase 2.5 — Cut the fat (geography + NAICS UX) — in progress

- [x] `home_states`, `include_remote`, `include_unknown_location` on `fit_profiles`
- [x] Ingest/backfill `state_code`, `place_of_performance`, `work_mode` from SAM PopState + remote keywords
- [x] Review queue filters: local state(s) OR remote (optional unknown location)
- [x] NAICS 2022 Census structure labels + sector picker in UI (`config/naics2022.json`)

### Phase 3 — Custom weights (optional, paused)

- [ ] Weight sliders → `fit_profiles.weights`
- [ ] Scoring function reads weights instead of fixed +20 / +10 rules
- [ ] Preview: “if I add keyword X, these 5 opps move up”

### Phase 4 — Multi-user auth

- [ ] Login, profile per user, shared org profiles

---

## Scoring philosophy (draft)

**Today:** additive points capped at 100, hard `min_score` filter.

**Counsel direction:**

1. **Ingest never grades** — only stores opportunities.
2. **Fit is relative** — “top 25 for your profile this week,” not “you failed with 18.”
3. **Reasons are the product** — users trust “matches your NAICS + keyword cloud” more than a number.
4. **Human loop unchanged** — `review_status`, fit surveys, and Counsel chat still refine the profile over time.

---

## Renamed from Consig (2026-07-04)

| Old | New |
|-----|-----|
| `consig/` | `counsel/` |
| `CONSIG_*` env | Removed — use `COUNSEL_*` only |
| `run_counsel.sh` | `run_counsel.sh` (Consig aliases removed 2026-07-04) |
| DB `consig_*` tables | `counsel_*` (migration `005_counsel_rename.sql`) |

Historical implementation notes from the Consig spike live in git history; this doc is the forward plan.

---

## GovBid gaps vs. open-source peers (2026-07-04)

| Capability | GovBid today | Arrow / govcon-scoring / OpenSAM / BidBridge |
|------------|--------------|-----------------------------------------------|
| Full SAM bulk ingest | **Yes** (Phase 1: `full` mode) | Arrow yes; others often API-only |
| Multi-user fit profiles | **DB + UI** — single active scorer (`match_scores`); per-profile rows in `opportunity_fits` later | BidBridge onboarding; bd-opportunity-monitor multi-tenant |
| Profile editor in dashboard | **Yes** — Counsel “My fit profile” tab + geography filter | Most have web forms |
| Best-fit ranking + reasons | **Yes** (`fit_band`, `match_reasons`) | govcon-scoring breakdown; Arrow rank |
| Custom weight sliders | **No** — fixed SQL weights | Ceradon config; govcon-scoring tunable in code |
| Set-aside *eligibility* match | Exclude only | govcon-scoring positive cert points |
| Deadline proximity in score | **No** | govcon-scoring penalty |
| USAspending / award enrichment | Stub table | GovIntel, MCP servers, BidBridge |
| SAM API delta / live search | n8n workflow (optional) | samgov-sdk, OpenSAM semantic search |
| Semantic search over opps | **No** — SQL keywords only | OpenSAM, Arrow+Ollama |
| Auth / multi-tenant | **No** | bd-opportunity-monitor, BidBridge |
| Proposal / compliance AI | Fit survey only | bd-opportunity-monitor compliance matrix |
| MCP agent tools | **No** | gov-contracts-mcp, mcp-govcon |
| Email digest | Slack script | Ceradon, BidBridge |
| Local LLM (Ollama) | **No** — OpenAI for RAG | Arrow, Ceradon |

**Priority closes the gap:** Phase 2 profile UI → Phase 3 weights → USAspending enrichment → auth.

---

## Related

- [gameplan.md](gameplan.md) — overall roadmap  
- [dashboard.md](dashboard.md) — current UI ops  
- [config/match-profile.example.yaml](../config/match-profile.example.yaml) — legacy single profile  
