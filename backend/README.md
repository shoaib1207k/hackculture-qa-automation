# QA automation backend

Scores a sale against its retailer's checklist before it can submit.

Run everything from this folder. Put `OPENAI_API_KEY` in `.env`.

```bash
uv sync                                                        # install
uv run pytest -q                                               # offline tests, no API calls
uv run python -m hackathon_qa_automation.cli score 3613792     # score a lead
uv run python -m hackathon_qa_automation.cli score 3613793 --json
```

API (docs at http://localhost:8000/docs):

```bash
uv run uvicorn hackathon_qa_automation.api.app:app --reload
curl -X POST localhost:8000/api/leads/3613792/score     # run the workflow for a lead
```

| Endpoint | What it does |
| --- | --- |
| `GET /api/leads` | Every lead with customer, retailer, call date and its latest score (null until processed) |
| `GET /api/leads/{lead_id}` | CRM record, transcript (card numbers redacted) and latest saved score |
| `POST /api/leads/{lead_id}/score?force=false` | Runs the workflow. Returns the saved score if there is one; `force=true` re-runs it. Unknown lead: 404 |
| `GET /api/health` | Liveness |

Scores are saved as JSON in `var/scores/` (gitignored). A scoring failure is returned
with `error` set and is not saved, so the next request retries.

Frontend (from `frontend/`, with the API running on port 8000):

```bash
npm install
npm run dev        # http://localhost:5173, proxies /api to the backend
```

Fixture leads in `data/leads/`:

| Lead | Scenario | Expected decision |
| --- | --- | --- |
| 3613792 | Clean call, customer clearly consents | AUTO_PASS |
| 3613793 | Customer refuses recording | HOLD |
| 3613791 | Three CRM defects (price, email, delivery address) | HOLD |
| 3613790 | Original call, consent buried in the agent's turn | HUMAN_QA |

Live try-outs of individual agents are in `scripts/`. `LOG_LEVEL=DEBUG` shows values,
quotes and reasoning.
