# GovBid Game Plan

**Owner:** Rocksteady Analytics  
**Last updated:** May 2026  
**Status:** Phase 0 complete — ingest, knowledge corpus, and pipeline stack merged into this repo

---

## Executive summary

Build a modular federal contracting system that:

1. **Ingests** the full SAM.gov contract opportunities bulk extract daily (~230 MB CSV).
2. **Filters and scores** opportunities against your IT/software capabilities (NAICS, PSC, keywords, set-asides).
3. **Surfaces** a review dashboard with direct SAM.gov links and enriched context.
4. **Assists capture and proposals** through modular AI agents, starting with **Consig** — a RAG chatbot trained on GovClose transcripts and official SAM documentation.

The GovClose corpus (400+ videos, ~287k lines in `govclose_all.txt`) and your playbooks encode the operating model: **research before RFP**, target specific acquisition offices, build a pipeline (not a spreadsheet wish list), and treat proposals as compliance exercises against Section L / Section M.

This repo includes lightweight ingest, the GovClose knowledge corpus, and the full Docker pipeline (Postgres, n8n, scoring workflows) in one place.

---

## Strategic foundation

### What the GovClose training emphasizes

| Principle | Implication for this build |
|-----------|---------------------------|
| **12–18 month first contract cycle** | Automate research and pipeline tracking; don't optimize for speed on proposal day one |
| **Federal sales roadmap first** | Confirm agencies buy what you sell (USAspending, FPDS → SAM awards, competitor benchmarking) before bidding |
| **Pipeline ≠ spreadsheet** | Repeatable capture process tied to targeted buyers and contract vehicles |
| **Win before the RFP** | Prioritize sources sought, presolicitation, and forecast meetings — not cold RFP responses |
| **Capability statement is the front door** | Agent should help tailor capability statements per agency/opportunity |
| **Section L = outline, Section M = score sheet** | Proposal agent must parse solicitation structure, not free-write |
| **SAM.gov replaces paid tools** | Bulk CSV + saved searches + API; build on official extracts, never scrape |

### Your capability profile (starting point)

From `config/match-profile.yaml` — customize as certifications and past performance evolve:

- **NAICS:** 541511, 541512, 541519, 518210, 511210
- **PSC prefixes:** D3 (IT services), 7E (IT equipment, optional)
- **Keywords:** software, application, cloud, DevSecOps, cybersecurity, API, modernization, SaaS, database, agile
- **Exclude:** construction, janitorial, landscaping, hardware-only, furniture, vehicles
- **Set-asides to skip** (until certified): 8(a), HUBZone, SDVOSB, WOSB, EDWOSB

---

## System architecture (target state)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA LAYER (Phase 0–1)                          │
│  SAM bulk CSV ──► Postgres ──► match scores ──► review queue           │
│  SAM API delta ──► enrich / dedupe                                        │
│  USAspending ──► award history by agency + NAICS                          │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      REVIEW LAYER (Phase 2)                             │
│  Dashboard / Adminer / n8n digest ──► human picks opportunities         │
│  Each row: title, score, deadline, set-aside, NAICS, SAM.gov link       │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      AGENT LAYER (Phase 3–4)                            │
│                                                                         │
│  ┌──────────┐    handoff    ┌──────────┐    handoff    ┌──────────┐   │
│  │  Consig  │ ────────────► │ Research │ ────────────► │ Proposal │   │
│  │  (RAG)   │               │  Agent   │               │  Agent   │   │
│  └──────────┘               └──────────┘               └──────────┘   │
│       │                          │                            │         │
│       └──────────────────────────┴────────────────────────────┘         │
│                    Modular Docker containers / n8n workflows            │
└─────────────────────────────────────────────────────────────────────────┘
```

**Design rules**

- Each agent is a **containerized module** with a defined input/output contract (JSON handoff).
- **n8n** orchestrates scheduled jobs (ingest, digest, enrichment) and agent chains.
- **Consig** is the entry point: strategy Q&A, playbook guidance, and opportunity context.
- Agents share Postgres as the system of record; RAG uses a vector store over transcripts + PDFs.

---

## Phase 0 — Foundation ✅ (done)

| Item | Status | Location |
|------|--------|----------|
| SAM.gov daily bulk CSV download | ✅ | `scripts/download_sam_opportunities.py`, `run_download.sh` |
| Cron-ready logging | ✅ | `logs/download.log` |
| GovClose transcript corpus | ✅ | `transcripts/govclose/` (~400 videos) |
| Strategy playbooks | ✅ | `docs/federal_contracting_playbook.md` |
| SAM.gov technical reference | ✅ | `docs/sam_gov_procurement_framework.md` |
| Official reference PDFs | ✅ | `docs/reference/` |
| GitHub remote | ✅ | `nvavrock/govbid` |

**Current data asset:** `data/ContractOpportunitiesFull_YYYYMMDD.csv` — full public extract with NoticeId, Title, agency, NAICS, set-aside, deadline, contacts, award fields, etc.

---

## Phase 1 — Filter, score, and load (weeks 1–2)

**Goal:** Turn the 230 MB CSV into a ranked, queryable opportunity list aligned with your profile.

### 1.1 Stand up the pipeline stack

```bash
cd /home/me/rs
cp .env.example .env          # SAM_API_KEY, Postgres, n8n secrets
cp config/match-profile.example.yaml config/match-profile.yaml
docker compose up -d
bash scripts/provision-n8n.sh
```

### 1.2 Wire bulk ingest

- Point `SAM_BULK_CSV_URL` at the same extract URL used by `download_sam_opportunities.py`.
- Enable workflow `01-sam-bulk-ingest.json` (daily 2 AM ET).
- Optional: keep `govbid` repo cron as backup or retire it once pipeline ingest is stable.

### 1.3 Validate matching

- Tune `config/match-profile.yaml` (NAICS, PSC, keywords, set-asides).
- Run `bash scripts/run-query.sh review_queue` — confirm top opportunities look relevant.
- Inspect false positives/negatives; adjust exclude keywords and set-aside filters.

### 1.4 Deliverable

A **review queue** of 25 opportunities scored ≥25 with deadlines inside 30 days, stored in Postgres with SAM.gov NoticeId for deep links.

---

## Phase 2 — Dashboard and opportunity UI (weeks 2–4)

**Goal:** Browse, filter, and open SAM.gov opportunity pages without writing SQL.

### 2.1 Minimum viable dashboard

Options (pick one for v1):

| Option | Effort | Notes |
|--------|--------|-------|
| **Adminer + saved queries** | Low | Already in pipeline; paste `review_queue.sql` |
| **Streamlit / Dash on Postgres** | Medium | Custom filters, SAM link column, export CSV |
| **Retool / Metabase** | Medium | Faster UI if you already use them |

**Required columns**

- Title, agency/office, posted date, response deadline
- NAICS, PSC, set-aside, type (sources sought / solicitation / award)
- Match score + keyword hits
- **SAM.gov link:** `https://sam.gov/opp/{NoticeId}/view`

### 2.2 n8n daily digest

- Workflow `04-review-digest.json` — email or Slack with top N opportunities.
- Include one-line AI summary per opportunity (Phase 3 prep).

### 2.3 Deliverable

Daily habit: open dashboard → scan queue → star 3–5 opportunities for capture work.

---

## Phase 3 — Consig: RAG advisor (weeks 4–6)

**Goal:** Chatbot that answers federal sales questions using your corpus, grounded in official docs.

### 3.1 Knowledge base

| Source | Path | Use |
|--------|------|-----|
| GovClose combined transcript | `transcripts/govclose/govclose_all.txt` | Tactics, mindset, process |
| Federal contracting playbook | `docs/federal_contracting_playbook.md` | Structured strategy |
| SAM procurement framework | `docs/sam_gov_procurement_framework.md` | Compliance, lifecycle |
| SAM data extract documentation | `docs/reference/Contract Opportunities Data Extract Documentation.pdf` | CSV field definitions |
| Entity checklist | `docs/reference/entity-checklist.pdf` | Registration requirements |

### 3.2 Consig capabilities (v1)

- Q&A: "What is a sources sought?" / "How do I read Section L?"
- Opportunity brief: given NoticeId, summarize title, buyer, deadline, fit score, recommended next step
- Capability statement draft: agency-specific opening paragraph + NAICS/PSC/UEI block
- **Guardrails:** cite sources; refuse to invent FAR clauses; flag when human CO engagement is required

### 3.3 Implementation sketch

```
Chunk corpus → embed → vector DB (pgvector or Chroma)
         │
         ▼
Consig API (FastAPI) ◄── n8n webhook / simple chat UI
         │
         ├── retrieval (top-k chunks)
         ├── LLM (Claude / GPT)
         └── optional: live Postgres lookup for opportunity context
```

### 3.4 Deliverable

Docker container `consig` with `/chat` endpoint; n8n can call it from digest workflow to append summaries.

---

## Phase 4 — Capture and proposal agents (weeks 6–10)

**Goal:** Modular handoffs from opportunity selection → capture plan → compliant proposal outline.

### Agent: Research (`research-agent`)

**Input:** NoticeId, match profile  
**Output:** capture brief JSON

- Agency/office research (USAspending award history for same NAICS)
- Competitor names from recent awards
- Recommended vehicle (GSA MAS, open market, subcontract path)
- Suggested outreach: CO vs. small business liaison
- Go / no-go recommendation

### Agent: Proposal (`proposal-agent`)

**Input:** solicitation PDF/text, capture brief  
**Output:** compliance matrix + outline

- Parse Section L → proposal outline
- Parse Section M → evaluation checklist
- Gap analysis vs. your past performance
- First-draft bullets per section (human edits required)

### Handoff contract (example)

```json
{
  "notice_id": "abc123",
  "phase": "capture",
  "from_agent": "consig",
  "to_agent": "research-agent",
  "context": {
    "title": "...",
    "agency": "...",
    "deadline": "2026-06-15",
    "match_score": 42
  }
}
```

### Deliverable

Two additional containers; n8n workflow chains Consig → Research → Proposal on starred opportunities.

---

## Phase 5 — Capture execution (ongoing)

Aligns with the federal sales roadmap from GovClose:

### 5.1 Market qualification checklist

- [ ] Confirm federal demand for your service (SAM awards + USAspending by NAICS)
- [ ] Identify top 5 contracting offices (not just agencies)
- [ ] Map how those offices buy (vehicles, set-asides, SAP threshold)
- [ ] Benchmark 3–5 peer contractors (last 5–10 years)
- [ ] SAM.gov entity registration active (UEI, reps & certs)
- [ ] Capability statement v1 (hyper-specific, direct contact info, vehicles/NAICS on face)

### 5.2 Pipeline stages

| Stage | Activity | Tool support |
|-------|----------|--------------|
| **Identify** | Sources sought, forecasts, saved searches | Phase 1–2 ingest + dashboard |
| **Qualify** | Go/no-go, set-aside fit, deadline feasibility | Consig + Research agent |
| **Capture** | CO meetings, capability statement, teaming | Consig + manual |
| **Propose** | Section L/M compliance matrix, write | Proposal agent |
| **Win / learn** | Debrief, past performance update | Postgres + playbook update |

### 5.3 Revenue paths (pick primary focus)

1. **Prime contractor** — direct awards on SAM solicitations (longest path, highest upside)
2. **Subcontractor** — build past performance with established primes
3. **Consulting / BD** — leverage Consig + corpus to advise other small businesses
4. **SBIR** — non-dilutive R&D if you have a differentiated technical offering

---

## Technology stack

| Layer | Tool | Repo |
|-------|------|------|
| Bulk download | Python + `requests` | `govbid` |
| Orchestration | n8n Community Edition | `workflows/n8n/` |
| Database | PostgreSQL + migrations | `db/` |
| Matching | SQL + `match-profile.yaml` | `config/` |
| Transcripts | yt-dlp + bash | `transcripts/govclose/` |
| RAG | pgvector / Chroma + FastAPI | new in `scripts/` |
| Agents | Docker containers, JSON handoffs | new |
| UI | Streamlit or Adminer (v1) | TBD |

---

## Immediate next actions (this week)

1. **Finalize match profile** — edit `config/match-profile.yaml` for Rocksteady Analytics.
2. **Start Docker pipeline** — ingest today's CSV; verify `review_queue` output.
3. **Pick dashboard approach** — Adminer for week 1, Streamlit if you want custom UI fast.
4. **Register on SAM.gov** — entity + API key (raises rate limits from ~10 to ~1,000/day).
5. **Spike Consig** — chunk `govclose_all.txt`, embed 100 pages, test 10 questions against playbook answers.

---

## Success metrics

| Milestone | Target |
|-----------|--------|
| Daily ingest running | 7 consecutive days without failure |
| Review queue precision | ≥70% of top-25 are genuinely bidable |
| Consig answer quality | Grounded answers with citations on 20 test questions |
| First capture brief | 1 opportunity researched end-to-end via agents |
| First proposal outline | 1 compliance matrix from a real solicitation |
| First contract action | Sources sought response or capability statement sent to a CO |

---

## References in this repo

- [Federal Contracting Playbook](federal_contracting_playbook.md)
- [SAM.gov Procurement Framework](sam_gov_procurement_framework.md)
- [SAM Data Extract Documentation](reference/Contract%20Opportunities%20Data%20Extract%20Documentation.pdf)
- [Entity Registration Checklist](reference/entity-checklist.pdf)
- GovClose corpus: `../transcripts/govclose/govclose_all.txt`

---

*This plan replaces the original scratch notes. Phases are sequential but overlapping — start Phase 1 while Phase 0 cron jobs keep running.*
