#!/usr/bin/env python3
"""Week 2 Day 1 — Option A: Flash Lite capability check + live MCP→PO FHIR smoke.

PLAN.md `week2_model_capability_check`: sanity-check Gemini 3.1 Flash Lite on
criteria-style and letter-style prompts using the three demo patient *scenarios*
(happy-path / needs-info / red-flag), before investing in full tool wiring.

Live smoke: POST the same JSON-RPC shape as `make mcp-fetch-patient` to a
local MCP server on :8000 with SHARP headers, so we exercise the real
`fetch_patient_context` path against the PO workspace FHIR API.

Usage (from repo root, with `.env` containing GOOGLE_API_KEY + GEMINI_MODEL)::

    uv run python scripts/week2_option_a.py flash
    uv run python scripts/week2_option_a.py fhir   # requires MCP on :8000 + env below
    uv run python scripts/week2_option_a.py all

FHIR smoke requires in the environment (or pass as env vars in the shell)::

    FHIR_URL   — e.g. https://app.promptopinion.ai/api/workspaces/<ws>/fhir
    FHIR_TOKEN — short-lived JWT from PO (A2A fhir-context bridge), not browser cookies
    PATIENT_ID — logical id from PO Patients list (UUID), e.g. Anna Demo

Start MCP first: ``uv run --package mcp_server uvicorn mcp_server.main:app --port 8000``
(or ``make mcp`` on Unix with make installed).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import google.generativeai as genai
import httpx
from dotenv import load_dotenv

# repo root = parent of scripts/
_REPO_ROOT = Path(__file__).resolve().parent.parent

_CRITERIA_PREVIEW_LEN = 1200
_LETTER_PREVIEW_LEN = 2000
_JSON_PREVIEW_LEN = 8000


def _load_dotenv() -> None:
    env_path = _REPO_ROOT / ".env"
    if env_path.is_file():
        load_dotenv(env_path)


# One-line scenario anchors (not full PHI; align with demo/clinical_notes themes).
_PATIENT_SCENARIOS: dict[str, str] = {
    "demo-patient-a": (
        "47F, 12 weeks mechanical LBP; 8 PT sessions (CPT 97110); completed "
        "NSAID + muscle-relaxant trials; radicular symptoms; payor Cigna; "
        "no structured red-flag ICDs; progress note states no saddle numbness."
    ),
    "demo-patient-b": (
        "52M, LBP; documented NSAID trial; only one PT intake visit and three "
        "no-shows; payor Cigna; progress note describes home stretches instead "
        "of completing PT course."
    ),
    "demo-patient-c": (
        "61F, hx breast cancer (Z85.3); acute urinary retention, saddle "
        "anesthesia, bilateral weakness documented in progress note; "
        "ServiceRequest priority stat; payor Aetna; red-flag fast-track narrative."
    ),
}


def _run_flash_checks() -> int:
    """Two prompt classes; three patients (criteria-style) + one letter prompt."""
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        print(
            "ERROR: GOOGLE_API_KEY is not set. Add it to .env (see .env.example).",
            file=sys.stderr,
        )
        return 1

    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite-preview").strip()

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    gen_cfg = genai.types.GenerationConfig(temperature=0)

    print(f"Model: {model_name}\n")

    # --- Criteria-style: one call per demo patient (structured JSON-ish output)
    for key, summary in _PATIENT_SCENARIOS.items():
        prompt = (
            "You are a prior-authorization assistant for outpatient lumbar spine MRI "
            "(CPT 72148). Given the patient summary below, respond in JSON only with "
            'keys: "conservative_therapy_status" (one of met, not_met, unclear), '
            '"red_flag_signal" (one of none, possible, urgent), '
            '"rationale" (array of up to 4 short strings).\n\n'
            f"Patient summary ({key}): {summary}"
        )
        t0 = time.perf_counter()
        resp = model.generate_content(prompt, generation_config=gen_cfg)
        elapsed = time.perf_counter() - t0
        text = (resp.text or "").strip()
        print(f"--- Criteria-style / {key} ({elapsed:.1f}s) ---")
        clip = _CRITERIA_PREVIEW_LEN
        print(text[:clip] + ("…" if len(text) > clip else ""))
        print()

    # --- Letter-style: hardest case (red-flag)
    letter_prompt = (
        "Draft the opening two paragraphs of a prior authorization request letter "
        "for outpatient lumbar MRI CPT 72148. Use a professional clinical tone. "
        "Do not invent a patient name or MRN; refer to 'the patient'. "
        "Base the clinical urgency on this summary:\n\n"
        f"{_PATIENT_SCENARIOS['demo-patient-c']}"
    )
    t0 = time.perf_counter()
    resp = model.generate_content(letter_prompt, generation_config=gen_cfg)
    elapsed = time.perf_counter() - t0
    text = (resp.text or "").strip()
    print(f"--- Letter-style / patient_c ({elapsed:.1f}s) ---")
    clip = _LETTER_PREVIEW_LEN
    print(text[:clip] + ("…" if len(text) > clip else ""))
    print()

    print(
        "Pass criteria (manual): JSON valid enough for the three criteria calls; "
        "letter is coherent and does not fabricate specific identifiers. "
        "If outputs are empty, garbled, or clearly hallucinated, escalate GEMINI_MODEL "
        "per AGENTS.md before Week 2 tool PRs."
    )
    return 0


def _run_fhir_smoke() -> int:
    base = os.environ.get("MCP_URL", "http://localhost:8000/mcp").rstrip("/")
    if not base.endswith("/mcp"):
        base = f"{base.rstrip('/')}/mcp"

    fhir_url = os.environ.get("FHIR_URL", "").strip()
    token = os.environ.get("FHIR_TOKEN", "").strip()
    patient_id = os.environ.get("PATIENT_ID", "").strip()

    missing = [
        n
        for n, v in [("FHIR_URL", fhir_url), ("FHIR_TOKEN", token), ("PATIENT_ID", patient_id)]
        if not v
    ]
    if missing:
        print(
            "ERROR: Set these in the environment (or .env): " + ", ".join(missing),
            file=sys.stderr,
        )
        print(
            "Tip: Use the fhirToken + fhirUrl + patientId from a PO A2A round-trip "
            "or from agent logs — not browser session cookies.",
            file=sys.stderr,
        )
        return 1

    body = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "fetch_patient_context",
            "arguments": {"patient_id": patient_id, "service_code": "72148"},
        },
    }
    print(f"POST {base}")
    print(f"patient_id={patient_id[:8]}…\n")
    t0 = time.perf_counter()
    r = httpx.post(
        base,
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "x-fhir-server-url": fhir_url,
            "x-fhir-access-token": token,
        },
        json=body,
        timeout=60.0,
    )
    elapsed = time.perf_counter() - t0
    print(f"HTTP {r.status_code} ({elapsed:.1f}s)\n")
    try:
        data = r.json()
    except json.JSONDecodeError:
        print(r.text[:2000])
        return 1

    print(json.dumps(data, indent=2)[:_JSON_PREVIEW_LEN])
    if not r.is_success:
        return 1
    # JSON-RPC error object
    if isinstance(data, dict) and data.get("error"):
        return 1
    return 0


def main() -> int:
    _load_dotenv()
    p = argparse.ArgumentParser(description=__doc__.split("Usage")[0].strip())
    p.add_argument(
        "command",
        choices=["flash", "fhir", "all"],
        help="flash=Gemini checks only; fhir=MCP tool call only; all=flash then fhir",
    )
    args = p.parse_args()

    if args.command == "flash":
        return _run_flash_checks()
    if args.command == "fhir":
        return _run_fhir_smoke()
    # all
    c1 = _run_flash_checks()
    if c1 != 0:
        return c1
    return _run_fhir_smoke()


if __name__ == "__main__":
    raise SystemExit(main())
