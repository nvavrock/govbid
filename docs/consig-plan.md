# Consig implementation plan

**Owner:** Rocksteady Analytics  
**Status:** On `main` — Phase A/B done; Phase C fit survey + feedback loop done; Phase C/D polish remaining (see below)

---

## Vision

Consig is a **capture copilot**, not only a transcript FAQ:

- Reads **today’s review queue** (scores, `match_reasons`, deadlines, SAM links).
- **Guides** pass/bid/review decisions and writes `review_status` + `notes` in Postgres.
- Answers strategy questions from **RAG** (training corpus + playbooks + SAM docs).
- **Remembers** session context and org preferences; over time, surfaces rule-tuning suggestions from your labels (human-approved).

Pipeline position:

```
review queue → Consig ↔ you (scores, picks, chat) → bid/reviewing → Research → Proposal
```

---

## What exists today (do not rebuild)

| Asset | Location |
|-------|----------|
| Opportunities + scores | `opportunities`, `match_scores` |
| Review workflow states | `review_status`: `pending`, `reviewing`, `bid`, `pass`, `expired` |
| Reviewer notes column | `match_scores.notes` |
| Queue query | `db/queries/review_queue.sql` |
| Match profile | `config/match-profile.yaml` |
| Corpus | `transcripts/corpus/combined.txt`, `docs/*.md`, `docs/reference/*.pdf` |
| CLI queue | `scripts/review_queue.py` |

---

## Architecture (target)

```
┌─────────────────────────────────────────────────────────────┐
│  UI (v1): Streamlit or CLI `consig chat`                    │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP
┌────────────────────────────▼────────────────────────────────┐
│  consig/ (FastAPI)                                          │
│  POST /chat          — message + optional notice_id/session   │
│  GET  /queue         — same filters as review_queue.sql       │
│  POST /review        — set review_status + notes              │
│  Tools: search_corpus, get_opportunity, get_preferences       │
└─────┬──────────────────┬──────────────────┬───────────────────┘
      │                  │                  │
      ▼                  ▼                  ▼
  Postgres          Vector store       LLM API
  (govbid)          (pgvector or       (Anthropic/OpenAI
                     Chroma local)      via .env)
```

**Docker:** `consig-api` and `consig-ui` services in `docker-compose.yml` (ports 8000 / 8501).

---

## Data model additions (migration `003_consig.sql`)

| Table | Purpose |
|-------|---------|
| `consig_sessions` | `id`, `created_at`, `title`, `metadata` jsonb |
| `consig_messages` | `session_id`, `role`, `content`, `notice_id` nullable, `created_at` |
| `consig_feedback` | `notice_id`, `action`, `user_reason`, `helpful` bool, `created_at` |
| `capture_preferences` | `key`, `value` jsonb — org-level (“avoid WOSB-only”, min score override) |

Optional: enable **pgvector** extension + `consig_chunks` (`content`, `embedding`, `source`, `metadata`).

---

## Implementation phases

### Phase A — Spike (2–3 days)

**Goal:** Prove RAG + Postgres context in one process.

- [x] Add deps: `fastapi`, `uvicorn`, `httpx`, embedding client, Chroma-based retrieval
- [x] Chunk script: `scripts/build_consig_index.py` — markdown + txt first; PDF later
- [x] `consig/db.py` — read queue + opportunity by `notice_id`
- [x] `consig/rag.py` — embed query, top-k retrieval
- [x] `consig/chat.py` — single-turn: user message + injected queue summary
- [x] `.env.example`: `OPENAI_API_KEY` + embedding model
- [x] Manual test: queue-based score explanations (Phase 1/2 verification)

**Exit:** Answer “What is sources sought?” with citation; answer “Why is notice X score 60?” using live DB row.

### Phase B — Interactive queue coach (3–5 days)

**Goal:** Two-way workflow on scores and picks.

- [x] `POST /chat` with `session_id` persistence (`consig_messages`)
- [x] System prompt: capture-advisor tone + use `match_reasons` + never invent FAR
- [x] Tools / structured outputs:
  - `get_review_queue(limit, min_score, days_ahead)`
  - `get_opportunity(notice_id)`
  - `set_review_status(notice_id, status, notes)`
- [x] Opening turn: proactive daily briefing from queue
- [x] Minimal Streamlit (`consig/ui.py`)

**Exit:** User marks 3 opps pass/bid via chat; DB reflects status; next queue excludes `pass`.

### Phase C — Memory and learning loop (2–4 days)

**Goal:** Strengthen advice over time without blind auto-tuning.

- [ ] `capture_preferences` CRUD via chat (“remember I don’t chase EDWOSB”)
- [x] On `pass`/`bid`, prompt for short reason → `notes` + `consig_feedback`
- [x] Structured fit survey: `POST /fit-survey`, `consig_fit_surveys` migration, Streamlit tab, and Chroma indexing
- [x] `scripts/consig_feedback_report.py` — aggregate pass reasons + fit-survey patterns (human applies)
- [ ] Session summary stored on close (for long threads)

**Exit:** Second session references preference; weekly report lists top false-positive patterns.

### Phase D — Platform integration (2–3 days)

**Goal:** Fit the rest of the stack.

- [x] Docker services `consig-api` + `consig-ui` in compose; healthcheck `/health`
- [ ] n8n `04-review-digest.json` — HTTP node calls Consig for one-line summaries (optional)
- [x] README + gameplan link to this doc
- [ ] Handoff JSON stub for Research agent (`notice_id`, `review_status=bid`)

---

## API sketch

### `POST /chat`

```json
{
  "session_id": "uuid-or-null",
  "message": "Walk me through today's top 5",
  "notice_id": null
}
```

Response: `{ "session_id", "reply", "citations": [...], "actions_taken": [...] }`

### `POST /review`

```json
{
  "notice_id": "abc...",
  "status": "pass",
  "notes": "Hardware-only scope"
}
```

### `GET /queue`

Query params mirror `review_queue.sql` (`min_score`, `days_ahead`, `top_n`).

---

## Scoring integration

Consig **explains** `refresh_match_scores()` output; it does not replace SQL rules in v1.

| User says | Consig does |
|-----------|-------------|
| “Why 60?” | Expand `match_reasons` + weights from profile |
| “This should be higher” | Show what keyword/NAICS would add points; suggest profile edit |
| “Stop showing X” | `pass` + note → feedback report → **you** edit `match-profile.yaml` |

Auto-changing SQL weights from LLM is **out of scope** for v1.

---

## Environment variables

| Variable | Purpose |
|----------|---------|
| `POSTGRES_*` | Same as pipeline (port 5433 on host) |
| `CONSIG_LLM_PROVIDER` | `anthropic` \| `openai` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | LLM |
| `CONSIG_EMBEDDING_MODEL` | e.g. `text-embedding-3-small` |
| `CONSIG_DATA_DIR` | Optional Chroma persist path |

---

## Success criteria (Phase B done)

| Test | Pass |
|------|------|
| Daily briefing | Lists ≤25 pending opps with score + deadline + link |
| Score explain | Correct breakdown for a known `notice_id` |
| Status update | `pass`/`bid` persists; queue query excludes passes |
| Grounded Q&A | 20 playbook questions with chunk citations |
| Guardrails | Refuses invented FAR; flags CO engagement when appropriate |

---

## Suggested file layout

```
consig/
  __init__.py
  main.py          # FastAPI app
  chat.py          # orchestration
  rag.py           # retrieval
  db.py            # Postgres helpers
  prompts.py       # system prompts
  tools.py         # queue / opportunity / review
scripts/
  build_consig_index.py
  consig_cli.py
db/migrations/
  003_consig.sql
docs/
  consig-plan.md   # this file
```

---

## Order of work (remaining)

1. `capture_preferences` CRUD via chat (Phase C).
2. Session summary on close (Phase C).
3. Optional: n8n digest → Consig one-line summaries (Phase D).
4. Research agent handoff JSON stub (Phase D).

---

## References

- [Game plan](gameplan.md) — Phase 3–4
- [Data dictionary](../db/DATA_DICTIONARY.md) — `match_scores.review_status`
- [Review queue SQL](../db/queries/review_queue.sql)
