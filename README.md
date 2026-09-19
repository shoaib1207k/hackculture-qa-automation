# QA Automation

**Score the sale before it ships.**

Every sale is checked automatically against its retailer's checklist before it can be
submitted. If every critical check passes, the sale goes through untouched. If any check
fails, the sale is held, and the person reviewing it sees exactly which check failed, the
line from the call transcript, the timestamp, and the reason, without listening to the call.

This replaces a manual process: an auditor pulls a recording, listens end to end, fills in an
Excel form, and the sale waits.

## Contents

- [How it works](#how-it-works)
- [The checks](#the-checks)
- [The gate: what happens to the sale](#the-gate-what-happens-to-the-sale)
- [Guardrails](#guardrails)
- [Repository layout](#repository-layout)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [API](#api)
- [Data and the checklist](#data-and-the-checklist)
- [The frontend](#the-frontend)
- [Testing](#testing)
- [Design decisions](#design-decisions)
- [Known limitations and next steps](#known-limitations-and-next-steps)

## How it works

```
 Lead (CRM record) + call transcript + retailer checklist
        │  the checklist version is the one live on the call date, not today's
        ▼
 ┌─ Script checks   the agent said the recording disclaimer; the customer agreed
 ├─ Fact checks     price, email, addresses, modem cost match the CRM
 └─ Behaviour       dead air, interruptions           (three nodes, run in parallel)
        │
        ▼
 Gate (plain Python, no model)  ──►  AUTO_PASS  |  HOLD  |  HUMAN_QA
        │
        ▼
 Score saved as JSON  ──►  API  ──►  web UI
```

The model reads and quotes; code decides. For each check an agent finds the relevant line and
quotes it. Plain Python then verifies that the quote really exists in the transcript, that the
right person said it, and takes the timestamp from the transcript itself, never from the model.
Anything the model cannot back with a real, quoted line becomes **uncertain** and is routed to
a human. It is never an automatic pass.

The agents run on [Strands Agents](https://strandsagents.com) with OpenAI models. The three
check types run in parallel as nodes of a Strands graph that feeds one gate node.

## The checks

Retailer 1's checklist has 10 checks. Each one has a short human name, a type, and a critical
flag.

| Type | Check | Critical | How it is judged |
| --- | --- | --- | --- |
| Script | Recording disclaimer | yes | An agent decides whether the **agent** conveyed every part of the required statement. |
| Script | Recording consent | yes | An agent decides whether the **customer** agreed, refused, or gave no clear answer. |
| Facts | Introductory plan price | yes | Compared with the CRM by a second agent. |
| Facts | Standard plan price | yes | Same. |
| Facts | Customer email | yes | Same; a single wrong character is a mismatch. |
| Facts | Service address | yes | Same; a missing unit number is a mismatch. |
| Facts | Delivery address | yes | Same. |
| Facts | Modem upfront cost | yes | Same. |
| Behaviour | Dead air | no | Computed from timestamps: longest silence over 10 s. |
| Behaviour | Interruptions | no | Computed from timestamps: more than 2 overlapping turns. |

### How a fact check works

1. An **extraction agent** finds the value the agent stated (it never sees the CRM value) and
   quotes the exact words and the segment they came from.
2. **Python** checks that the segment exists and the quote is really in it, and looks up the
   real timestamps.
3. A **comparison agent** (it never sees the transcript) judges whether the spoken value and
   the CRM value state the same fact. Number words versus digits, currency formatting, and
   abbreviations such as Dr and Drive are the same. A different number, a wrong or missing
   character in an email, or a missing unit number is a mismatch.

Keeping the two agents apart means neither can be nudged toward a match by seeing both sides.

### How a consent check works

The consent agent returns one of three outcomes, and Python then verifies its evidence:

| Outcome | Verdict |
| --- | --- |
| The customer clearly agreed | pass |
| The customer refused | fail |
| No clear answer, or the answer is buried inside the agent's own turn | uncertain |

Python confirms that the agent's statement was made by the agent, that the answer was spoken by
the customer, and that it came after the statement.

### When a verdict is "uncertain"

- the model cites a segment that does not exist;
- the quoted words are not in the cited segment;
- the value was never stated, or the CRM has no value to compare with;
- the cited speaker is wrong (for example a customer line counted as the agent's disclaimer);
- for consent, no clear customer answer was found.

## The gate: what happens to the sale

The gate is plain Python in `backend/src/hackathon_qa_automation/graph/gate.py`. Rules are
applied in order and the first that applies wins.

| Situation | Decision | Goes to |
| --- | --- | --- |
| A critical check failed with confidence of at least 0.75 | `HOLD` | Team leader queue |
| Any check is uncertain, or below 0.75 confidence (including an unsure critical fail) | `HUMAN_QA` | QA |
| All critical checks pass, but the lead falls in the 5% clean-call sample | `HUMAN_QA` | QA |
| All critical checks pass | `AUTO_PASS` | Submits untouched |

- The 5% sample is chosen by hashing the lead ID, so re-scoring the same lead never changes it.
- A failure while scoring (a model error, a timeout) never crashes and never auto-passes: the
  lead becomes `HUMAN_QA`, or `HOLD` if a check that had already finished found a critical fail.

## Guardrails

The handout treats these as non-negotiable. Status of each:

| Guardrail | Status |
| --- | --- |
| Test data only | Done. Every lead in the repo is synthetic. |
| Consent is a check, not an assumption | Done. The disclaimer and the customer's answer are both checked. |
| Scored against the rules that were live | Done. Every score records the checklist version chosen by call date. |
| No card data surfaced | Partly. Card-like numbers (13 to 19 digits) are masked in everything the API sends. Saved score files are not yet redacted, and card numbers spoken as words are not caught. |
| No advice, no auto-correction | Done. The system reports what failed and where; it changes nothing and contacts no one. |
| Respect the override | Not built yet. There is no override log. |

## Repository layout

```
.
├── README.md
├── backend/                      Python: scoring pipeline and API
│   ├── src/hackathon_qa_automation/
│   │   ├── models.py             Shared schemas: transcript, lead, checklist, verdict
│   │   ├── pipeline.py           score_lead(): the single entry point
│   │   ├── llm.py                Builds the Strands OpenAI model, per-agent reasoning effort
│   │   ├── store.py              Latest score per lead, saved as JSON
│   │   ├── cli.py                Command line scorer
│   │   ├── checks/
│   │   │   ├── factual/          extraction + comparison agents, scoring
│   │   │   ├── verbatim/         disclaimer and consent agents, scoring
│   │   │   └── behaviour/        dead air and interruptions (no model)
│   │   ├── graph/                Strands graph: nodes, builder, gate
│   │   ├── common/               evidence checks, verdict builder, loaders, redaction, logging
│   │   └── api/                  FastAPI app, routes, response schemas
│   ├── tests/                    Mirrors the package; none call the model
│   ├── scripts/                  Live try-outs of individual agents
│   ├── data/
│   │   ├── retailers/retailer1/checklist.json
│   │   └── leads/<lead_id>/{crm.json, transcript.json}
│   └── var/scores/               Saved scores (created at runtime, gitignored)
├── frontend/                     React + MUI web app
└── docs/                         Presentation material
```

## Getting started

### Prerequisites

- Python 3.12 or newer and [uv](https://docs.astral.sh/uv/)
- Node.js 20.19 or newer
- An OpenAI API key with access to the model named in [Configuration](#configuration)

### Install and run

```bash
# 1. Backend: create backend/.env containing  OPENAI_API_KEY=sk-...  then start the API on port 8000
cd backend
uv sync
uv run uvicorn hackathon_qa_automation.api.app:app --reload

# 2. Frontend, in a second terminal: serves http://localhost:5173 and proxies /api to port 8000
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, click **Process** on a lead, then click the lead to read its verdicts.
The interactive API docs are at http://localhost:8000/docs.

### Score from the command line

```bash
cd backend
uv run python -m hackathon_qa_automation.cli score 3613792          # readable report
uv run python -m hackathon_qa_automation.cli score 3613793 --json   # full result
LOG_LEVEL=DEBUG uv run python -m hackathon_qa_automation.cli score 3613792   # values, quotes, reasoning
```

## Configuration

All settings are environment variables, read from `backend/.env` or the shell.

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | none, required | OpenAI key. `OPEN_AI_API_KEY` is also accepted. |
| `OPENAI_MODEL` | `gpt-5.6-luna` | Model used by every agent. |
| `OPENAI_REASONING_EFFORT` | unset | Overrides every agent's reasoning effort (`none`, `low`, `medium`, `high`, `xhigh`, `max`) for experiments. |
| `LOG_LEVEL` | `INFO` for the API, `WARNING` for the CLI | `DEBUG` adds extracted values, quotes and reasoning. Those are personal data on real calls, so they stay out of INFO. |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Origins allowed to call the API directly. |

Every agent runs with reasoning effort `none`: these are lookups against short inputs, and on
the test cases `none` was faster, cited tighter evidence, and passed the same tests as `low`.
Each agent sets its own value at the top of its `agents.py`.

`gpt-5.6` models allow tool calls (which Strands uses for structured output) only with
reasoning off on Chat Completions, or on the Responses API. `llm.py` picks the right provider
for the effort you set.

## API

All routes are under `/api`. The lead ID is limited to letters, digits, `_` and `-`, because it
becomes part of a file path.

| Method and path | What it does |
| --- | --- |
| `GET /api/leads` | Every lead with customer, retailer, call date, and its latest score (`null` until processed). |
| `GET /api/leads/{lead_id}` | The CRM record, the transcript (card numbers redacted), and the latest score. `404` if unknown. |
| `POST /api/leads/{lead_id}/score?force=false` | Runs the workflow and saves the result. Returns the saved score if there is one; `force=true` re-runs it. About 3 seconds. |
| `GET /api/health` | Liveness check. |

A scoring failure is not an HTTP error: the lead comes back as `HUMAN_QA` (or `HOLD`) with
`error` set. It is not saved, so the next request tries again.

```jsonc
// POST /api/leads/3613793/score   (abbreviated)
{
  "lead_id": "3613793",
  "retailer_id": "retailer1",
  "call_date": "2026-09-19",
  "checklist_version": "R1-v3",
  "decision": "HOLD",
  "reasons": ["Critical check failed: Recording consent"],
  "confidence_threshold": 0.75,
  "error": null,
  "verdicts": [
    {
      "check_id": "recording_consent",
      "check_name": "Recording consent",
      "check_type": "verbatim",
      "critical": true,
      "verdict": "fail",                      // pass | fail | uncertain
      "confidence": 1.0,
      "evidence_segment_ids": ["S004a"],
      "timestamp_start": 38.4,
      "timestamp_end": 40.0,
      "evidence_text": "No, I would rather you didn't record this call.",
      "reasoning": "The customer refused: ..."
    }
  ]
}
```

Scores are saved as one file per lead in `backend/var/scores/<lead_id>.json`. Delete
`backend/var` to reset every lead to "not processed".

## Data and the checklist

### Sample leads

All leads are synthetic, built from one redacted real call with dummy names and details.

| Lead | Scenario | Expected decision |
| --- | --- | --- |
| `3613792` | Clean call; the customer clearly says "Yes, that's fine." | `AUTO_PASS` |
| `3613793` | The customer refuses to be recorded | `HOLD` |
| `3613791` | CRM defects: wrong intro price, email typo, delivery address missing its unit | `HOLD` |
| `3613790` | The original transcript, where the customer's reply is buried inside the agent's turn | `HUMAN_QA` (consent unclear) |

Timestamps in the sample transcripts are synthetic estimates, not audio timestamps.

### The checklist

`backend/data/retailers/<retailer>/checklist.json` holds a list of versions. Each has an
`effective_from` date, and a call is scored against the version live on its call date.

```json
{
  "retailer_id": "retailer1",
  "versions": [
    {
      "version": "R1-v3",
      "effective_from": "2026-01-01",
      "checks": {
        "recording_consent": {
          "name": "Recording consent",
          "description": "The customer explicitly agrees to the call being recorded, ...",
          "type": "verbatim",
          "critical": true,
          "spoken_by": "CUSTOMER",
          "required_elements": ["Customer agrees to the call being recorded"]
        },
        "plan_price_intro": {
          "name": "Introductory plan price",
          "description": "The monthly price the agent quotes for the PROMOTIONAL period ...",
          "type": "factual",
          "critical": true,
          "crm_field": "introductory_monthly_price"
        }
      }
    }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `name` | Short label shown to people. Defaults to a tidied `check_id`. |
| `description` | What exactly the check is, and what it is not. The factual agent is given this text, so it is what stops it picking a related field (connection address versus delivery address). |
| `type` | `verbatim`, `factual` or `behaviour`. |
| `critical` | A critical fail blocks the sale. Required for `verbatim` and `factual` checks. |
| `required_elements` | Verbatim: what must be conveyed. Every part must be present. |
| `spoken_by` | Verbatim: `AGENT` (default) or `CUSTOMER`. `CUSTOMER` makes it a consent check. |
| `crm_field` | Factual: the CRM field to compare with. |

A checklist with a config error (a factual check with no `crm_field`, a verbatim check with no
elements) fails when it is loaded, not once per lead.

To add a retailer, add `data/retailers/<retailer_id>/checklist.json` and leads whose CRM record
names that retailer. To change the rules, add a new version with a later `effective_from`;
calls made before that date keep being scored against the old version.

## The frontend

`frontend/` is a React + MUI app built with Vite. It proxies `/api` to the backend on port 8000.

- **Overview.** Every lead in a table with a **Process** button. A lead can only be opened once
  it has been processed. Totals and a chart summarise the decisions.
- **Lead detail.** The decision in plain words ("Held", "Passed", "Needs human review") and the
  reasons behind it. Checks are grouped into **Needs attention** and **Passed**. Opening a
  check shows why, what was said, and a button that scrolls to and highlights that line in the
  transcript.
- **Transcript.** Each evidence line is coloured by the worst result among the checks that cite
  it: red failed, orange unclear, blue note, green passed. The CRM record sits beside it in
  grouped, readable form.
- **Low confidence.** A check below the confidence threshold is shown as **Unclear**, matching
  the gate, with a note saying what it came out as.

## Testing

```bash
cd backend
uv run pytest -q          # 98 tests, offline: no API calls, run in about a second
```

The tests fake the model, so they check the code around it: grounding, the speaker and order
guards, the gate rules, the graph and the failure fallback, the API, redaction and the store.

Scripts in `backend/scripts/` call the real model on the sample call, doctored into cases with a
known answer. They need `OPENAI_API_KEY`.

```bash
uv run python scripts/factual/try_compare.py       # comparison agent: 17 cases
uv run python scripts/verbatim/try_verbatim.py     # disclaimer: 7 cases (removed, half-said, negated, ...)
uv run python scripts/verbatim/try_consent.py      # consent: 8 cases (agreed, refused, a question, ...)
uv run python scripts/factual/score_factual.py --defect   # the factual path with a tampered CRM
```

## Design decisions

- **The model extracts and cites; code verifies and decides.** Timestamps, speakers and
  segment IDs are never taken from the model on trust. This is what keeps a made-up quote from
  becoming a pass.
- **Uncertain beats wrong.** Where evidence is missing or untrustworthy the answer is
  "uncertain", which routes to a person. The brief asks for no false criticals and no false
  passes on critical checks.
- **Value comparison is done by an agent, not by parsing rules.** Rule-based normalisers
  (money, email, phone, address) do not generalise across about 30 retailers, so a strict
  comparison prompt handles equivalence. The old normalisers are kept in
  `checks/factual/normalisation.py`, unused and marked as parked.
- **Behaviour checks are measurements, not judgements.** A model cannot reliably measure
  seconds of silence, so dead air and interruptions are computed from timestamps.
- **A graph per lead.** Strands graphs keep run state on the instance, so a fresh graph is
  built for each scored lead. That is cheap, since agents are created per call.
- **A fresh agent per call.** A Strands agent keeps its message history, which would otherwise
  leak one check's transcript and answer into the next.

## Known limitations and next steps

- **Accuracy is measured on hand-made cases, not a labelled set.** There are no answer keys
  yet, and no report of agreement with human auditors.
- **The model's self-reported confidence is rarely low** (0.98 to 1.0 on nearly every call), so
  the 0.75 threshold seldom fires. The Python guards are the real safety net.
- **Timestamps are coarse.** Sample segments are whole turns, up to 100 seconds long, so a
  timestamp can span a long stretch. Word-level timestamps from real transcription would narrow it.
- **Meaning, not the script.** Script checks judge whether every required part was conveyed. They
  do not match word for word against an approved script (for example a DMO or VDO read).
- **Consent means an affirmative reply.** "Yeah okay" passes. If a retailer needs a stricter
  phrase, that is a prompt change.
- **Rate limits.** Each check sends the whole transcript, an estimated 47,000 tokens per lead. On a
  500,000 tokens-per-minute account that is roughly 10 leads a minute before calls start to
  queue and retry. Extracting all facts in one call would cut this by about 4 times.
- **Storage is a stand-in.** One JSON file per lead, overwritten on re-score, with no history
  and no processed-at time. Saved files are not redacted.
- **Not built yet:** the override log, real recording ingestion and transcription (the
  transcripts are supplied), the dashboards from the brief (first-pass yield, repeat offences,
  auditor agreement), and qualitative behaviour checks such as rapport or objection handling.
