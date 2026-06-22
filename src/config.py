"""
All tunable constants in one place (no magic numbers scattered in nodes).

Quantifies 'flaky', 'slow', 'redundant', and the coverage floor so they're not
vibes. Every node imports its thresholds from here.
"""

import os

# Load .env (key + model overrides) before any os.getenv below. config is imported by
# every module, so this guarantees the environment is populated first. No-op if
# python-dotenv isn't installed or there's no .env file.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Use the OS (Windows) certificate store for TLS so corporate proxies / TLS-inspection
# root CAs are trusted — otherwise the Gemini HTTPS call fails CERTIFICATE_VERIFY_FAILED.
# No-op if truststore isn't installed.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

# Keep the embedding layer offline by default: if sentence-transformers is installed
# but the model isn't cached locally, do NOT reach out to huggingface.co (a blocked /
# TLS-inspected corporate network makes that hang for minutes on retries). With these
# set, an uncached model raises immediately and embeddings.py falls back to its
# deterministic hashing vector. Set EMBED_ALLOW_DOWNLOAD=1 to permit a one-time download.
USE_ST_EMBEDDINGS = os.getenv("EMBED_ALLOW_DOWNLOAD", "0") == "1"
if not USE_ST_EMBEDDINGS:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

# spaCy NER is optional too (heavy import + model load). Off by default → deterministic
# keyword extraction. Set SPACY_NER=1 to use spaCy entities.
USE_SPACY = os.getenv("SPACY_NER", "0") == "1"

# --- Loop & coverage controls ---
MAX_GEN_RETRIES = 3                 # bounds the validate -> gap_gen loop (Blocker #1)
MAX_REVISE_ITERS = 10               # defensive cap on the coverage-floor revise loop
DEFAULT_COVERAGE_TARGET = 0.80      # the hard floor (Blocker #2)

# --- Semantic similarity thresholds (cosine, 0..1) ---
CRITERIA_MATCH_THRESHOLD = 0.45     # >= this links a test to an acceptance criterion
DUPLICATE_THRESHOLD = 0.80          # >= this groups two tests as near-duplicates
GAP_THRESHOLD = 0.45                # criterion with max-similarity < this is a gap

# --- Flakiness / slow thresholds ---
FLAKY_FAIL_RATE = 0.10              # fails/runs >= this => flaky
SLOW_TEST_SECONDS = 10.0            # avg run time >= this => slow

# --- Coverage model (prototype) ---
# Projected coverage = COVERAGE_BASE + COVERAGE_PER_UNIT * (distinct units still
# covered), capped at COVERAGE_CAP. Near-duplicate tests share one "unit", so removing
# a redundant duplicate costs no coverage while removing a unique test does — which is
# exactly what the coverage-floor gate must protect.
COVERAGE_BASE = 0.70
COVERAGE_PER_UNIT = 0.06
COVERAGE_CAP = 0.98

# --- Tool retry settings (Blocker #3) ---
TOOL_RETRIES = 3
BACKOFF_BASE = 2                    # exponential backoff: BACKOFF_BASE ** attempt

# --- Models (pulled from env; see .env.example) ---
# Provider: Google Gemini (Gemini 2.5 Flash). The SDK reads GEMINI_API_KEY (or the
# legacy GOOGLE_API_KEY) from the environment.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
REASONING_MODEL = os.getenv("REASONING_MODEL", "gemini-2.5-flash")
FAST_MODEL = os.getenv("FAST_MODEL", "gemini-2.5-flash")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# --- Offline demo mode ---
# When no GEMINI_API_KEY / embedding model is available, the NLP and scoring layers
# fall back to deterministic logic so the graph still runs end-to-end. A configured
# key enables the LLM by default; force offline with OFFLINE_MODE=1.
OFFLINE_MODE = os.getenv("OFFLINE_MODE", "0") == "1" or not GEMINI_API_KEY
