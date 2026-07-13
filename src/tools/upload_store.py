"""
Upload store — safely persist test files sent from another platform (benchmarking).

Receives uploaded test files (and optionally a .zip, plus acceptance-criteria / CI-history
JSON) from the HTTP layer, validates and sanitises them, and writes them to a per-upload
directory under ``uploads/<token>/`` that a run can then point ``suite_path`` at. Returns a
manifest of what was written and what was skipped (and why).

Architecture position:
    Integration layer (tools/). Called by the API's ``POST /uploads`` endpoint (api.py). It
    only writes files to disk under the repo's ``uploads/`` dir — it never parses or executes
    them (parsing happens later, on disk, via ``test_parser`` when a run reads ``suite_path``).
Called by:
    ``store_upload`` <- api.upload_suite.
Data in:  in-memory (filename, bytes) pairs for suite files / zip archives, and optional
    criteria / CI-history JSON bytes.
Data out: a manifest dict {token, suite_path, criteria_path, ci_history_path, written[],
    skipped[]}; side effect: files written under ``uploads/<token>/``.

Security: filenames are reduced to safe names (no traversal / absolute paths); only known
test/source extensions are accepted; per-file, total-size and file-count caps are enforced;
zip extraction is zip-slip protected (members are confined under the upload dir).
"""

import io
import json
import os
import uuid
import zipfile
from pathlib import Path

# WHY: write under a single dedicated, gitignored dir at the repo root so uploads never
# escape the project and are trivially disposable.
_UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads"

# WHY: only accept recognised test/source extensions — matches the languages test_parser
# can extract, and blocks arbitrary file writes (executables, archives-in-archives, etc.).
TEST_EXTS = {".py", ".java", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
             ".go", ".rb", ".cs"}

MAX_FILE_BYTES = 2_000_000      # per-file cap (2 MB) — test files are text, not fixtures/blobs
MAX_TOTAL_BYTES = 50_000_000    # total upload cap (50 MB)
MAX_FILES = 2_000               # file-count cap — a runaway zip can't create millions of files


def _safe_basename(name: str) -> str | None:
    """
    Reduce an uploaded filename to a safe basename.

    Purpose:  strip any directory components so a flat upload can't write outside the dir.
    Inputs:   ``name`` — the client-supplied filename.
    Outputs:  the basename, or None if it's empty / a traversal token.
    Side effects: None (pure).
    Called by: ``store_upload``.
    Calls:    ``os.path.basename``.
    """
    # WHY: take only the final path component and reject empties / '.'/'..' so a crafted
    # name like "../../etc/x" collapses to a harmless basename or is rejected.
    base = os.path.basename(name.replace("\\", "/")).strip()
    if not base or base in {".", ".."}:
        return None
    return base


def _accept_bytes(name: str, data: bytes, dest_dir: Path, rel: str,
                  state: dict, written: list, skipped: list) -> None:
    """
    Validate one (name, bytes) payload and write it under ``dest_dir`` if it passes.

    Purpose:  enforce the extension / size / count caps for a single file, then write it.
    Inputs:   display ``name``; ``data`` bytes; ``dest_dir`` (the suite dir); ``rel`` relative
              target path under dest_dir; ``state`` running-total dict; ``written``/``skipped``
              accumulators.
    Outputs:  None (mutates ``written`` / ``skipped`` / ``state``).
    Side effects: writes a file under ``dest_dir`` on success.
    Called by: ``store_upload``, ``_extract_zip``.
    Calls:    ``Path.write_bytes``, ``Path.mkdir``.
    """
    ext = Path(rel).suffix.lower()
    # WHY: extension whitelist — anything we can't parse (or shouldn't store) is skipped.
    if ext not in TEST_EXTS:
        skipped.append({"name": name, "reason": f"extension {ext or '(none)'} not accepted"})
        return
    # WHY: per-file cap guards against oversized payloads.
    if len(data) > MAX_FILE_BYTES:
        skipped.append({"name": name, "reason": "file exceeds per-file size cap"})
        return
    # WHY: count + total-size caps bound a whole upload (esp. a malicious/huge zip).
    if len(written) >= MAX_FILES:
        skipped.append({"name": name, "reason": "file-count cap reached"})
        return
    if state["total"] + len(data) > MAX_TOTAL_BYTES:
        skipped.append({"name": name, "reason": "total upload size cap reached"})
        return
    target = dest_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    state["total"] += len(data)
    written.append(rel.replace("\\", "/"))


def _extract_zip(name: str, data: bytes, suite_dir: Path,
                 state: dict, written: list, skipped: list) -> None:
    """
    Zip-slip-safe extraction of a .zip's test files into the suite dir.

    Purpose:  unpack an archived suite, preserving folder structure but confined to the dir.
    Inputs:   archive ``name``; ``data`` bytes; ``suite_dir``; ``state``/``written``/``skipped``.
    Outputs:  None (mutates accumulators).
    Side effects: writes extracted files under ``suite_dir``.
    Called by: ``store_upload``.
    Calls:    ``zipfile.ZipFile``, ``_accept_bytes``.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        skipped.append({"name": name, "reason": "not a valid zip archive"})
        return
    root = suite_dir.resolve()
    for info in zf.infolist():
        if info.is_dir():
            continue
        member = info.filename.replace("\\", "/")
        rel = Path(member)
        # WHY: reject absolute paths and any '..' segment — classic zip-slip vectors.
        if rel.is_absolute() or ".." in rel.parts:
            skipped.append({"name": member, "reason": "unsafe path in zip (blocked)"})
            continue
        # WHY: belt-and-braces — resolve the final target and confirm it stays under the
        # suite dir even after path normalisation, before writing anything.
        target = (suite_dir / rel).resolve()
        if root != target and not str(target).startswith(str(root) + os.sep):
            skipped.append({"name": member, "reason": "zip-slip blocked"})
            continue
        with zf.open(info) as fh:
            _accept_bytes(member, fh.read(), suite_dir, member, state, written, skipped)


def _write_data_file(base: Path, filename: str, data: bytes,
                     skipped: list) -> str | None:
    """
    Validate and write an uploaded JSON data file (criteria / CI history).

    Purpose:  persist an optional acceptance-criteria or CI-history JSON for the run.
    Inputs:   ``base`` (the upload dir); ``filename`` (e.g. "criteria.json"); ``data`` bytes;
              ``skipped`` accumulator.
    Outputs:  the absolute path written, or None if invalid.
    Side effects: writes ``base/filename`` on success.
    Called by: ``store_upload``.
    Calls:    ``json.loads``, ``Path.write_bytes``.
    """
    # WHY: validate it parses as JSON before accepting — a malformed data file should be
    # reported now, not silently used (and then degrade to fixture) later.
    try:
        json.loads(data.decode("utf-8", errors="strict"))
    except (ValueError, UnicodeDecodeError):
        skipped.append({"name": filename, "reason": "not valid JSON"})
        return None
    if len(data) > MAX_FILE_BYTES:
        skipped.append({"name": filename, "reason": "file exceeds per-file size cap"})
        return None
    target = base / filename
    target.write_bytes(data)
    return str(target.resolve())


def store_upload(suite_files, archives=None, criteria=None, ci_history=None,
                 expected_findings=None) -> dict:
    """
    Persist an uploaded suite (and optional criteria / CI-history / expected-findings) to a
    per-run upload dir.

    Purpose:  the entry point the API calls — validate, sanitise, and write everything, and
              return a manifest describing what landed on disk.
    Inputs:
        suite_files       — list[(filename, bytes)] of individual test files.
        archives          — optional list[(filename, bytes)] of .zip archives to extract.
        criteria          — optional (filename, bytes) acceptance-criteria JSON.
        ci_history        — optional (filename, bytes) CI-history JSON.
        expected_findings — optional (filename, bytes) expected-findings (golden) JSON, used
                            by ``report`` to benchmark the run.
    Outputs:
        manifest dict: {token, suite_path (absolute), criteria_path|None,
        ci_history_path|None, expected_findings_path|None, written[relative names],
        skipped[{name, reason}]}.
    Side effects: creates ``uploads/<token>/suite/`` and writes the accepted files there;
        writes ``criteria.json`` / ``ci_history.json`` / ``expected_findings.json`` when supplied.
    Called by: api.upload_suite.
    Calls:    ``_accept_bytes``, ``_extract_zip``, ``_write_data_file``, ``_safe_basename``.
    """
    # WHY: a random token isolates each upload so concurrent benchmark runs never collide.
    token = uuid.uuid4().hex[:12]
    base = _UPLOAD_ROOT / token
    suite_dir = base / "suite"
    suite_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    skipped: list[dict] = []
    state = {"total": 0}  # running total-bytes across flat files + zip members

    # WHY: flat individual files are stored by safe basename (no folder structure to keep).
    for name, data in suite_files or []:
        safe = _safe_basename(name)
        if safe is None:
            skipped.append({"name": name, "reason": "unsafe or empty filename"})
            continue
        _accept_bytes(name, data, suite_dir, safe, state, written, skipped)

    # WHY: archives may carry a nested suite — extract (zip-slip safe) preserving structure.
    for name, data in archives or []:
        _extract_zip(name, data, suite_dir, state, written, skipped)

    # WHY: optional per-run data files let a benchmark supply its own criteria / CI history
    # so coverage & flaky/slow detection reflect the uploaded suite, not the sample fixtures.
    criteria_path = None
    if criteria is not None:
        criteria_path = _write_data_file(base, "criteria.json", criteria[1], skipped)
    ci_history_path = None
    if ci_history is not None:
        ci_history_path = _write_data_file(base, "ci_history.json", ci_history[1], skipped)
    # WHY: the expected-findings golden key is a benchmark reference (graded by report), not
    # an analysis input — stored the same way and returned so the run can be scored against it.
    expected_findings_path = None
    if expected_findings is not None:
        expected_findings_path = _write_data_file(
            base, "expected_findings.json", expected_findings[1], skipped)

    return {
        "token": token,
        "suite_path": str(suite_dir.resolve()),
        "criteria_path": criteria_path,
        "ci_history_path": ci_history_path,
        "expected_findings_path": expected_findings_path,
        "written": written,
        "skipped": skipped,
    }
