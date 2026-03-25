#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="A fake CLI-Anything style document editor for MindLakeVM demos."
    )
    parser.add_argument("--action", required=True, choices=["edit_text", "summarize"])
    parser.add_argument("--input-path", required=True)
    parser.add_argument("--output-path")
    parser.add_argument("--patch", default="")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input_path)
    output_path = Path(args.output_path) if args.output_path else input_path.with_suffix(".edited.txt")
    original_text = input_path.read_text(encoding="utf-8") if input_path.exists() else ""

    if args.action == "summarize":
        result = {
            "summary": _build_summary(original_text),
            "output_path": str(output_path),
            "dry_run": args.dry_run,
        }
        return _emit(result, args.as_json)

    edited_text = _apply_patch(original_text, args.patch)
    if not args.dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(edited_text, encoding="utf-8")

    result = {
        "summary": "Dry run: document would be updated." if args.dry_run else "Document updated successfully.",
        "action": args.action,
        "input_path": str(input_path),
        "output_path": str(output_path),
        "dry_run": args.dry_run,
        "artifacts": [
            {
                "path": str(output_path),
                "type": "document",
            }
        ],
        "preview": edited_text[:240],
    }
    return _emit(result, args.as_json)


def _apply_patch(original_text: str, patch: str) -> str:
    if not original_text.strip():
        base = "# Fake Document\n\nOriginal content is empty.\n"
    else:
        base = original_text
    return f"{base.rstrip()}\n\n---\nApplied Patch:\n{patch.strip() or '(no patch provided)'}\n"


def _build_summary(text: str) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return "Document is empty."
    if len(normalized) <= 120:
        return normalized
    return normalized[:117] + "..."


def _emit(payload: dict, as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(payload.get("summary", "ok"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
