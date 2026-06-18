# Installation Guide — Test Optimiser Agent

A complete, copy-paste setup. Commands are shown for **Windows PowerShell** first, with the
macOS/Linux equivalent noted. The agent runs **offline by default** (deterministic
fallbacks, no API key), so you can get to a first run before adding any key.

> **Provider:** this project uses **Google Gemini (`gemini-2.5-flash`)**. The required key is
> `GEMINI_API_KEY`.

---

## 1. Prerequisites

- **Python 3.10+** (developed/tested on 3.13).
- **Git**.
- **A Google Gemini API key** — only needed for the live LLM path (scoring rationale +
  gap-test drafting). Without it the agent uses deterministic fallbacks. Create one at
  <https://aistudio.google.com/apikey> (a real key starts with `AIza…`; project-scoped
  keys may differ).
- **spaCy NER model** — *only* if you opt into spaCy (`SPACY_NER=1`):
  ```powershell
  python -m spacy download en_core_web_sm
  ```

---

## 2. Clone & virtual environment

```powershell
git clone <your-repo-url> test-optimiser-agent
cd test-optimiser-agent

python -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Install dependencies

```powershell
pip install -r requirements.txt
```

This installs LangGraph, the Gemini SDK (`google-genai`), FastAPI/uvicorn (demo API),
`python-dotenv`, `truststore` (corporate-TLS fix — see §9), and pytest. The heavier NLP deps
(sentence-transformers, spaCy, chromadb) are optional and off by default.

---

## 4. Environment setup

Create a `.env` file in the repo root (it's gitignored — never commit it) with the variables
below. The minimum is your key:

```powershell
# minimum
Set-Content .env "GEMINI_API_KEY=your-key-here"   # macOS/Linux: echo "GEMINI_API_KEY=your-key-here" > .env
notepad .env                                       # add any of the optional vars below
```

A complete `.env` looks like:

```ini
GEMINI_API_KEY=your-key-here
REASONING_MODEL=gemini-2.5-flash
FAST_MODEL=gemini-2.5-flash
EMBEDDING_MODEL=all-MiniLM-L6-v2
OFFLINE_MODE=0
EMBED_ALLOW_DOWNLOAD=0
SPACY_NER=0
```

| Variable | Required? | Default | What it does |
|----------|-----------|---------|--------------|
| `GEMINI_API_KEY` | **Yes** (for live LLM) | — | Auth for Gemini. Also accepts `GOOGLE_API_KEY`. If unset → `OFFLINE_MODE` and deterministic fallbacks. |
| `REASONING_MODEL` | No | `gemini-2.5-flash` | Model for scoring + gap-test generation (the judgement calls). |
| `FAST_MODEL` | No | `gemini-2.5-flash` | Model for lighter/mechanical passes. |
| `EMBEDDING_MODEL` | No | `all-MiniLM-L6-v2` | sentence-transformers model (only used if `EMBED_ALLOW_DOWNLOAD=1`). |
| `OFFLINE_MODE` | No | `0` | Set `1` to force the deterministic path even with a key present. |
| `EMBED_ALLOW_DOWNLOAD` | No | `0` | Set `1` to use real sentence-transformers embeddings (downloads the model once). Off → fast deterministic hashing embeddings. |
| `SPACY_NER` | No | `0` | Set `1` to use spaCy NER for entity extraction. Off → deterministic keyword extraction. |

> The defaults are tuned for a fast, dependency-light demo. Leave `EMBED_ALLOW_DOWNLOAD` and
> `SPACY_NER` at `0` unless you specifically want the heavier semantic NLP — turning them on
> pulls in PyTorch/spaCy and can be slow to import on some machines.

---

## 5. Verify install

```powershell
python -c "from src.state import TestOptimiserState; print('OK')"
```

Prints `OK` when the package imports cleanly. To confirm the Gemini path (after setting your
key):

```powershell
python -c "from src.llm import llm_available, complete; print('available:', llm_available()); print(complete('Reply with: OK'))"
```

---

## 6. Generate sample data

```powershell
python sample_data/generate_sample_data.py
```

Regenerates the synthetic fixture from a single source of truth. Expect a summary like:

```
Generated 23 tests across 5 files in .../sample_suite
  test_auth.py  5 | test_cart.py 6 | test_checkout.py 5 | test_search.py 4 | test_account.py 3
Planted:
  duplicate clusters : 2  (login pair, cart-add pair)
  flaky              : test_search_returns_results, test_checkout_payment_retry
  slow               : test_payment_gateway_charges_card, test_full_catalog_export
  coverage gaps      : AC-6, AC-7
```

This (re)writes `sample_suite/*.py` (5 files), `mock_ci_history.json`, `sample_criteria.json`,
the golden `expected_findings.json`, and `sample_data/README.md` — all kept in sync. See
[../sample_data/README.md](../sample_data/README.md) for the full, detailed explanation.

---

## 7. Run the learning scripts (in order)

These teach the LangGraph mechanics in isolation. Run them before reading the 10-node graph.

```powershell
python learning/01_counter_graph.py        # state + linear nodes
python learning/02_conditional_branch.py   # routing + loop (gate/validation pattern)
python learning/03_interrupt_resume.py     # checkpointer + interrupt() (the HITL pattern)
```

---

## 8. First real run

```powershell
python main.py --suite sample_data/sample_suite --goal speed
```

The graph pauses **three times** for your approval (interactive mode). At each prompt, press
**Enter** to accept the recommendation, or type a comma-separated list / `none`:

1. **Approve removals** — the flaky/duplicate candidates (with evidence). Enter = accept the
   recommended set.
2. **Approve ranking** — the smoke/regression/full tiering. Enter = accept.
3. **Approve generated tests** — the drafted gap test(s). Enter = accept.

On completion the four deliverables are written to `outputs/` and a summary prints. To run
without prompts: `--run-mode automated` (auto-approves the recommended set).

---

## 9. Run the web UI (React + FastAPI)

The full demo is two processes — the backend API and the React frontend.

**Terminal 1 — backend:**
```powershell
uvicorn api:app --reload          # serves http://127.0.0.1:8000  (docs at /docs)
```

**Terminal 2 — frontend** (first time only: `npm install`):
```powershell
cd frontend
npm install                       # one-time
npm run dev                       # opens http://localhost:5173
```

In the browser: fill the form (defaults: suite `sample_data/sample_suite`, goal `speed`,
coverage `80`, risk areas `payment`) → **Run Analysis** → approve the 3 checkpoints →
read the 4 result tabs. CORS for `localhost:5173` is already enabled in `api.py`.

> First run is ~20–30s at the scoring step (live Gemini) before checkpoint 1 — that's normal.
> `npm run build` produces a production bundle in `frontend/dist/` if you want to serve it statically.

---

## 10. Common install errors & fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `llm_available()` is `False` even with a key | `.env` not loaded, or wrong var name | Ensure the file is named `.env` and uses `GEMINI_API_KEY=...`; `config.py` calls `load_dotenv()` at import. |
| `400 API_KEY_INVALID` / "API key expired" | Wrong/expired credential | Create a fresh key at <https://aistudio.google.com/apikey>. |
| `429 RESOURCE_EXHAUSTED` | Free-tier daily quota hit (20/day on `gemini-2.5-flash`) | Wait for the daily reset, enable billing, or use a project with quota. The agent degrades to deterministic and still completes. |
| `CERTIFICATE_VERIFY_FAILED` on the Gemini/HTTPS call | Corporate proxy / TLS inspection; Python's bundled certs don't trust the corporate root CA | `truststore` (in `requirements.txt`) is injected in `config.py` to use the OS cert store. Ensure it's installed **in the same venv** running the app: `pip install truststore`. |
| spaCy model missing (`Can't find model 'en_core_web_sm'`) | Model not downloaded | Only relevant with `SPACY_NER=1`: `python -m spacy download en_core_web_sm`. Otherwise leave `SPACY_NER=0`. |
| First run hangs for minutes downloading the embedding model | `sentence-transformers` reaching huggingface.co (slow/blocked) | Leave `EMBED_ALLOW_DOWNLOAD=0` (default) → deterministic hashing embeddings, no download. Set `1` only when you want real embeddings and have network access. |
| Chroma path / vector-store error | Optional dependency / path issue | The vector store degrades to empty context; the run continues. Install `chromadb` only if you need persistent semantic retrieval. |
| Very slow imports on Windows | Antivirus scanning large packages (`google-genai`, torch) | One-time per process; the FastAPI backend warms the SDK import at startup so requests stay fast. |
