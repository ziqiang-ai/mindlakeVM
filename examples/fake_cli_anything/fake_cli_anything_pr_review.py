#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="A fake CLI-Anything style PR review helper for MindLakeVM demos."
    )
    parser.add_argument("--action", required=True, choices=["review_pr", "publish_review"])
    parser.add_argument("--repo-path", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--focus", default="")
    parser.add_argument("--output-path")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    repo_path = Path(args.repo_path)
    output_path = Path(args.output_path) if args.output_path else Path("/tmp") / f"pr_review_{args.pr_number}.json"

    findings = [
        {
            "title": "数据库迁移缺少回滚说明",
            "severity": "high",
            "file": "migrations/20260325_add_orders_table.sql",
            "rationale": "迁移新增表结构，但没有明确 down/rollback 路径。",
        },
        {
            "title": "接口兼容性需要确认",
            "severity": "medium",
            "file": "api/orders.py",
            "rationale": "响应字段新增后需确认旧客户端兼容策略。",
        },
        {
            "title": "测试覆盖不足",
            "severity": "medium",
            "file": "tests/test_orders.py",
            "rationale": "缺少 migration rollback 和 negative permission case。",
        },
    ]
    draft = {
        "summary": (
            "Dry run: review draft generated."
            if args.dry_run
            else ("Review comments published." if args.action == "publish_review" else "Review draft generated.")
        ),
        "action": args.action,
        "repo_path": str(repo_path),
        "pr_number": args.pr_number,
        "focus": args.focus,
        "dry_run": args.dry_run,
        "findings": findings,
        "artifacts": [
            {
                "path": str(output_path),
                "type": "review_report",
            }
        ],
    }

    if not args.dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")

    return _emit(draft, args.as_json)


def _emit(payload: dict, as_json: bool) -> int:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(payload.get("summary", "ok"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
