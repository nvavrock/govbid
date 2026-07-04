# GovBid community standards

**Last updated:** 2026-07-04  
**Owner:** Rocksteady Analytics

This document defines how we work on GovBid — in code, docs, issues, and chat. It applies to everyone contributing or using project artifacts (including AI-assisted work).

Inspired in structure by the [Jellyfin Community Standards](https://jellyfin.org/docs/general/community-standards/).

---

## Mission

- GovBid helps contractors find **best-fit** federal opportunities from official SAM.gov data — not scrape it, not spam it, not gatekeep it behind proprietary black boxes.
- The project is maintained by volunteers on their own time. No contributor owes anyone immediate replies or unlimited support.
- Quality over volume: a small, correct pipeline beats a large pile of brittle automation.

---

## Code of conduct

When interacting anywhere this project lives (GitHub, Slack, email, etc.):

- **Be kind and direct.** Assume good intent. Do not harass, demean, or dogpile.
- **No slurs or sexualized language.** Keep discussions professional.
- **Respect privacy.** Do not share others’ `.env`, credentials, or proprietary corpus without permission.
- **English is the working language**, but many contributors are not native speakers — be patient with wording mistakes.

---

## Quality standards (anti-slop)

We reject **slop**: low-effort, untested, or misleading changes that look finished but aren’t.

### Code

- **Match existing style** — read neighboring files before adding helpers or abstractions.
- **Minimal diff** — fix the problem; don’t refactor unrelated code in the same PR.
- **No dead code** — delete unused imports, scripts, and duplicate modules (e.g. renamed packages left behind).
- **Verify before claiming done** — run the relevant script (`./run_daily.sh`, `scripts/status.sh`, `verify_phase*.sh`) and say what you ran.
- **No secrets in git** — `.env`, API keys, `terraform.tfvars`, and proprietary transcripts stay gitignored.

### Documentation

- **Docs must match runtime** — if Postgres is user-space on `:5432`, don’t document Docker `:5433` as the only path.
- **One source of truth** — [STATUS.md](STATUS.md) for ops; [counsel-plan.md](counsel-plan.md) for product direction.
- **No placeholder walls** — avoid “TODO: fill this in” commits without an issue or plan reference.
- **Changelog mindset** — significant behavior changes get a line in STATUS or the relevant plan doc.

### AI-assisted work

AI tools are welcome; **AI slop is not**.

| Do | Don’t |
|----|--------|
| Read and understand generated code before committing | Paste large blocks you haven’t traced |
| Run ingest/status after pipeline changes | Claim “Phase complete” without row counts or logs |
| Cite official SAM.gov / USASpending APIs | Invent endpoints, field names, or legal advice |
| Keep prompts and vendor branding out of user-facing Counsel text | Ship training-vendor names in UI or RAG output |
| Split large AI drafts into reviewable commits | One 5,000-line “make it work” dump |

If you used AI heavily, say so in the PR/commit body and list what you verified manually.

### Data and compliance

- **SAM.gov:** use the **bulk CSV** and **documented API** only — no scraping behind login walls.
- **Do not commit** proprietary training transcripts or client-specific match profiles.
- **Set-aside and certification logic** affects real bid decisions — prefer transparent rules (`match_reasons`) over opaque scores.

---

## Dispute resolution

1. **Discuss in good faith** — link to this doc or [sdlc.md](sdlc.md) when standards are unclear.
2. **Escalate privately** if needed — repo owner / Rocksteady Analytics contact on file.
3. **Maintainers may** request changes, revert slop, or restrict access for repeated violations.

Warnings follow a second-chance policy: fix the behavior and move on.

---

## Questions

Open a GitHub issue or update [STATUS.md](STATUS.md) if these standards need clarification.

### Changelog

- **2026-07-04** — Initial version (mission, anti-slop, AI-assisted work, data compliance).
