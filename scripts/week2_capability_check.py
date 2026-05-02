#!/usr/bin/env python3
"""Week 2 Day 1 - Gemini capability check (PLAN.md).

Runs **outside** Prompt Opinion: calls Google AI Studio (``GOOGLE_API_KEY``) with
``GEMINI_MODEL`` (default from .env) at **temperature 0**, using the real
``demo/clinical_notes/patient_{a,b,c}.md`` sources.

Pass criteria for a quick human review:
- **Patient A**: decision should lean **approve** (documented conservative course).
- **Patient B**: **needs_info** / incomplete PT (not a full approve).
- **Patient C**: **red_flag_fast_track** or urgent escalation (cauda-equina pattern).

Exit 0 always if the API calls succeed (this is a qualitative check); exit 1 on
config or API errors.
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path
from typing import Any

import google.generativeai as genai
from dotenv import load_dotenv

# google.generativeai is deprecated in favor of google.genai; keep until repo migrates.
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_note(relpath: str) -> str:
    p = _repo_root() / relpath
    if not p.is_file():
        raise FileNotFoundError(f"Missing demo note: {p}")
    return p.read_text(encoding="utf-8")


CRITERIA_AND_LETTER_PROMPT = "\n".join(
    [
        "You are helping validate an automated prior-authorization assistant for",
        "**outpatient lumbar MRI (CPT 72148)**.",
        "",
        "Read the clinical note below. Act as a **structured prior-auth analyst**",
        "(not a treating clinician). Use only what is documented in the note.",
        "",
        "## Task 1 - Criteria-style decision",
        "Assume a typical US commercial medical-necessity framework: persistent",
        "low back pain with adequate duration where required, documented conservative",
        "therapy where required, appropriate evaluation of red flags, and clear",
        "documentation gaps where the chart is incomplete.",
        "",
        "Respond with a section **### Task 1 - Decision** containing:",
        "- **decision**: exactly one of `approve` | `needs_info` | `deny`",
        "- **red_flag_fast_track**: `yes` or `no` (yes if emergent red-flag",
        "  pathway is warranted from the note)",
        "- **criteria_met**: bullet list (short phrases)",
        "- **criteria_missing**: bullet list (short phrases; empty if none)",
        "- **reasoning_trace**: 2-4 sentences tying the bullets to the note",
        "",
        "## Task 2 - Letter-style output",
        "Respond with a section **### Task 2 - Letter snippet** containing EITHER:",
        "- If **needs_info**: a numbered list of **3-5** specific documentation",
        "  requests a payer would accept.",
        "- If **approve** or **red_flag_fast_track**: a **brief** PA letter",
        "  paragraph (3-5 sentences) with clinical justification tied to the note;",
        "  if red-flag, start with one **URGENT:** sentence.",
        "",
        "Keep the entire response under 600 words. Be concise.",
    ]
)


def run_case(model: Any, title: str, note_text: str) -> str:
    """Call Gemini; return text."""
    full_prompt = f"{CRITERIA_AND_LETTER_PROMPT}\n---\n## Clinical note ({title})\n\n{note_text}\n"
    generation_config = genai.types.GenerationConfig(
        temperature=0,
        max_output_tokens=2048,
    )
    resp = model.generate_content(
        full_prompt,
        generation_config=generation_config,
    )
    text = getattr(resp, "text", None)
    if not text:
        raise RuntimeError(f"Empty response for {title!r}")
    return str(text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Week 2 Day 1 Flash Lite capability check")
    parser.add_argument(
        "--patient",
        choices=("a", "b", "c", "all"),
        default="all",
        help="Run a single demo patient or all three (default: all)",
    )
    args = parser.parse_args()

    load_dotenv(_repo_root() / ".env")
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        print(
            "ERROR: GOOGLE_API_KEY is not set. Add it to .env (see .env.example).", file=sys.stderr
        )
        return 1

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite").strip()

    genai.configure(api_key=api_key)  # type: ignore[attr-defined]
    model = genai.GenerativeModel(model_name)  # type: ignore[attr-defined]

    cases: list[tuple[str, str, str]] = [
        (
            "Patient A - happy path (documented PT + meds)",
            "demo/clinical_notes/patient_a.md",
            "a",
        ),
        (
            "Patient B - needs-info (incomplete PT)",
            "demo/clinical_notes/patient_b.md",
            "b",
        ),
        (
            "Patient C - red-flag / cauda equina concern",
            "demo/clinical_notes/patient_c.md",
            "c",
        ),
    ]

    selected = {args.patient} if args.patient != "all" else {"a", "b", "c"}

    print(f"Model: {model_name}")
    print("Temperature: 0")
    print("=" * 72)

    for title, rel, key in cases:
        if key not in selected:
            continue
        note = _load_note(rel)
        print(f"\n>>> {title}\n")
        try:
            out = run_case(model, title, note)
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(out)
        print("-" * 72)

    print(
        "\nHuman review: confirm A -> approve-leaning, B -> needs_info, "
        "C -> urgent/red-flag.\n"
        "If outputs are shallow or wrong, escalate GEMINI_MODEL per PLAN.md before Week 2 polish."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
