# `src/nlp/` — Deterministic text backbone

## 1. Purpose

The **deterministic NLP layer** that does all matching, deduplication, gap detection, and log
triage — embeddings, similarity, clustering, and extraction. It is the "cheap, reproducible
brain": no per-item LLM cost, and it runs fully **offline** with hashing/lexical fallbacks.

## 2. Why this folder exists

The spec splits **NLP (deterministic)** from **LLM (judgement)**. Structural work — "does this
test cover this criterion?", "are these two tests duplicates?", "is this a real gap?" — must be
fast, free, and identical every run. Keeping it here means the agent still produces correct
coverage/redundancy findings with no API key.

## 3. How it fits into the overall architecture

```
 src/nodes/coverage   → similarity.match_tests_to_criteria / find_gaps
 src/nodes/redundancy → clustering.cluster_duplicates
 src/nodes/intake     → extraction.extract_entities
 src/tools/vector_store → embeddings.embed / cosine

     similarity ──▶ embeddings ──▶ extraction.normalise
        │                              ▲
        └────────── clustering ────────┘   (extraction also does log triage)
```

## 4. Files inside the folder

`__init__.py`, `embeddings.py`, `similarity.py`, `clustering.py`, `extraction.py`.

## 5. Responsibilities of each file

- **`embeddings.py`** — `load_embedder()` (sentence-transformers if `USE_ST_EMBEDDINGS`, else
  `None`), `embed(texts)` (real vectors or deterministic MD5-bucket `_hash_vector`), `cosine(a,b)`
  in `[0,1]`, `nearest_neighbours(query, corpus, k)`.
- **`similarity.py`** — `test_text(test)`, `semantic_sim(a,b)` (embeddings if available, else
  `lexical_sim` token overlap), `match_tests_to_criteria(tests, criteria, threshold)` →
  `{coverage_map, links}`, `find_gaps(criteria, tests, gap_threshold)` → uncovered criteria.
- **`clustering.py`** — `cluster_duplicates(tests, threshold=DUPLICATE_THRESHOLD)`: greedy
  single-linkage grouping; returns only clusters with ≥2 members.
- **`extraction.py`** — `normalise(text)` (tokenise/stopword/lemmatise), `extract_entities(text)`
  (spaCy NER if `USE_SPACY`, else sorted tokens), `classify_failure_logs(logs)` → flaky-vs-real
  triage via keyword signals; `_load_spacy`, `_tokens`, `_lemmatise` helpers.

## 6. Inputs

Test dicts (`name`, `docstring`, `id`), criteria dicts (`id`, `text`), free text / CI logs, and
config thresholds (`CRITERIA_MATCH_THRESHOLD`, `GAP_THRESHOLD`, `DUPLICATE_THRESHOLD`,
`EMBEDDING_MODEL`, `USE_ST_EMBEDDINGS`, `USE_SPACY`).

## 7. Outputs

Embedding vectors + cosine scores; `coverage_map` + `links` + `gaps`; duplicate clusters;
normalised tokens / entities; log-classification counts.

## 8. Dependencies

`src.config`; optional `sentence-transformers` and `spacy` (both degrade gracefully to
deterministic fallbacks); stdlib `re`, `hashlib`, `math`.

## 9. Which folders call/use it

`src/nodes/` (coverage, redundancy, intake) and `src/tools/vector_store.py`.

## 10. Which folders it calls/uses

Nothing outside `src/nlp/` except `src.config` — this is a leaf layer (internally,
`similarity`→`embeddings`→`extraction`, and `clustering`→`similarity`).

## 11. Runtime execution flow

```
coverage_node:
  match_tests_to_criteria → for each criterion: semantic_sim(criterion, each test)
      → link where sim ≥ CRITERIA_MATCH_THRESHOLD  ⇒ coverage_map
  find_gaps → criterion is a gap where best sim < GAP_THRESHOLD
redundancy_node:
  cluster_duplicates → join tests where semantic_sim ≥ DUPLICATE_THRESHOLD (single-linkage)
intake_node:
  extract_entities → spaCy NER or normalise() tokens
semantic_sim path: embeddings.embed available? cosine() : lexical_sim()
```

## 12. Common debugging locations

- **Too many/few coverage links** → `CRITERIA_MATCH_THRESHOLD` and `semantic_sim`.
- **False/missing gaps** → `GAP_THRESHOLD` and `find_gaps`.
- **Bad duplicate clusters** → `DUPLICATE_THRESHOLD` and `cluster_duplicates` (single-linkage).
- **Different results online vs offline** → `embeddings.load_embedder` / `_hash_vector` fallback.
- **Entities empty/odd** → `extraction._load_spacy` and `USE_SPACY`.
