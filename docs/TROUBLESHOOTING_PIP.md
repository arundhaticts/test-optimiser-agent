# Troubleshooting — pip `403 Forbidden` behind a corporate proxy

A short field guide for the install error most likely to hit you on a corporate
network (e.g. Cognizant). Applies to **any** package (`spacy`,
`sentence-transformers`, `chromadb`, …), not just the one that first failed.

---

## Symptom

`pip install <anything>` fails with a 403 on a `.metadata` URL, even though the
package clearly exists:

```
ERROR: HTTP error 403 while getting
https://files.pythonhosted.org/packages/.../spacy-3.8.14-cp313-cp313-win_amd64.whl.metadata
ERROR: 403 Client Error: Forbidden for url: .../spacy-...whl.metadata
```

## Root cause

This is **not** a package problem, a Python-version problem, or a broken wheel.
The corporate proxy/WAF blocks PyPI's **PEP 658 `.metadata` sidecar files** by
extension. The real wheels download fine; only the `.metadata` companion files
are forbidden.

Confirm it in ~10 seconds — the wheel returns `200`, its sidecar returns `403`:

```bash
WHL="https://files.pythonhosted.org/packages/.../spacy-3.8.14-cp313-cp313-win_amd64.whl"
curl -s -o /dev/null -w "%{http_code}\n" "$WHL"            # -> 200  (wheel OK)
curl -s -o /dev/null -w "%{http_code}\n" "$WHL.metadata"   # -> 403  (sidecar blocked)
```

pip's default (2020+) resolver fetches those `.metadata` files during dependency
resolution, so it dies — while the wheels themselves were always reachable.

## Fix — use the legacy resolver

The legacy resolver downloads full wheels instead of the blocked sidecars:

```bash
.venv/Scripts/python.exe -m pip install --use-deprecated=legacy-resolver <package>
```

Make it permanent so you don't have to remember the flag:

```bash
.venv/Scripts/python.exe -m pip config set global.use-deprecated legacy-resolver
```

## Installing models / packages served off GitHub

Direct wheel URLs (e.g. spaCy models on GitHub) are **not** proxied and install
normally — no sidecar involved:

```bash
.venv/Scripts/python.exe -m pip install --use-deprecated=legacy-resolver \
  https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
```

## Gotchas

- **`ModuleNotFoundError: No module named 'click'` when importing spaCy** — the
  `typer` version pulled in may not bring `click`. Just add it:
  `pip install --use-deprecated=legacy-resolver click`.
- **Don't upgrade pip past the point where `--use-deprecated=legacy-resolver` is
  removed** until the network team whitelists `*.metadata` on
  `files.pythonhosted.org` — that whitelist is the real long-term fix.
- These heavy ML deps are **opt-in** for this project (`SPACY_NER=1`,
  `EMBED_ALLOW_DOWNLOAD=1`). The agent runs fully offline with deterministic
  fallbacks and needs none of them for a default run.

## Side effect: legacy resolver can install an incompatible version

The legacy resolver **does not backtrack on version conflicts** — if it can't
find a package's `.metadata`, it also won't enforce that package's pins as
strictly as the modern resolver. So it occasionally installs a slightly-too-new
dependency, which then fails at *import* time with a version-mismatch error:

```
ImportError: tokenizers>=0.22.0,<=0.23.0 is required for a normal functioning
of this module, but found tokenizers==0.23.1.
```

**Fix:** pin the offending package to the highest compatible version *that has a
cp313 Windows wheel*. Note the required version may have no Windows wheel at all
(that's often why the resolver jumped past it) — pick the next one down that
does:

```bash
# transformers wanted <=0.23.0; 0.23.0 has no Windows wheel, so use 0.22.2
.venv/Scripts/python.exe -m pip install "tokenizers==0.22.2"
```

To find which versions have a Windows wheel:

```bash
curl -s https://pypi.org/simple/tokenizers/ \
  | grep -oE "tokenizers-0\.2[23]\.[0-9]+-[a-z0-9_-]*win_amd64\.whl" | sort -uV
```

Same pattern for any other `ImportError` about a required version range: pin that
one package, don't touch the rest.

## Verify spaCy works

```bash
.venv/Scripts/python.exe -c "import spacy; nlp=spacy.load('en_core_web_sm'); \
print([(e.text,e.label_) for e in nlp('Apple opened a London office in 2020.').ents])"
# -> [('Apple', 'ORG'), ('London', 'GPE'), ('2020', 'DATE')]
```
