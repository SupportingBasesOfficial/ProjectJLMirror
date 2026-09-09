#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any

import validate_adversarial_learning as base

HEAD_STATUS_WORKFLOW = Path('.github/workflows/adversarial-learning-reconciliation.yml')
MATERIAL_RE = re.compile(r'(?:\bP[012]\s+Badge\b|\[P[012]\])')
NEGATIVE_HELPERS = {
    Path('tools/assurance/test_validate_adversarial_learning.py'): {'expect_failure'},
    Path('tools/assurance/test_validate_d4d_trace_context_source.py'): {'mutate_and_expect_failure'},
}


def _flatten(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, list):
            out.extend(_flatten(item))
        elif isinstance(item, dict):
            out.append(item)
    return out


def _has_negative_check(function: ast.AST, helpers: set[str]) -> bool:
    for node in ast.walk(function):
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in helpers:
            return True
    return False


def _validate_falsifier_effects(root: Path) -> list[str]:
    errors: list[str] = []
    for rel, helpers in NEGATIVE_HELPERS.items():
        path = root / rel
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except Exception as exc:
            errors.append(f'cannot parse strict falsifier file {rel}: {type(exc).__name__}: {exc}')
            continue
        functions = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        credited, credited_errors = base._reachable_main_falsifiers(path)
        errors.extend(credited_errors)
        for name in sorted(credited):
            function = functions.get(name)
            if function is None or not _has_negative_check(function, helpers):
                errors.append(f'credited falsifier performs no negative check: {rel}:{name}')
    return errors


def _validate_head_status_workflow(root: Path) -> list[str]:
    path = root / HEAD_STATUS_WORKFLOW
    if not path.is_file():
        return [f'head-associated reconciliation workflow missing: {HEAD_STATUS_WORKFLOW}']
    text = path.read_text(encoding='utf-8')
    markers = {
        'issue_comment trigger': 'issue_comment:',
        'status write permission': 'statuses: write',
        'resolved PR head lookup': 'pulls/${PR_NUMBER}',
        'head status endpoint': 'statuses/${PR_HEAD_SHA}',
        'stable status context': 'JLMIRROR / adversarial-learning-reconciliation',
        'pending publication': 'state=pending',
        'always final publication': 'if: always()',
        'job result binding': 'JOB_STATUS: ${{ job.status }}',
        'strict reconciliation': 'validate_adversarial_learning_strict.py',
    }
    return [f'head-associated reconciliation workflow missing {name}' for name, marker in markers.items() if marker not in text]


def _strict_material_ids(review_comments: Path) -> set[int]:
    comments = _flatten(json.loads(review_comments.read_text(encoding='utf-8')))
    return {
        row['id']
        for row in comments
        if isinstance(row.get('id'), int)
        and isinstance(row.get('body'), str)
        and MATERIAL_RE.search(row['body'])
    }


def validate(root: Path, review_comments: Path | None = None) -> list[str]:
    root = root.resolve()
    errors = list(base.validate(root, review_comments))
    errors.extend(_validate_head_status_workflow(root))
    errors.extend(_validate_falsifier_effects(root))

    if review_comments is not None:
        entries, ledger_errors = base._load_ledger_entries(root)
        errors.extend(ledger_errors)
        review_ids = {
            row.get('review_comment_id')
            for row in entries
            if isinstance(row, dict)
            and row.get('source') == 'external_review'
            and isinstance(row.get('review_comment_id'), int)
        }
        exception_ids, exception_errors = base.validate_bootstrap_exceptions(root)
        errors.extend(exception_errors)
        missing = sorted(_strict_material_ids(review_comments) - review_ids - exception_ids)
        if missing:
            errors.append('strict material PR findings missing from learning ledger or bootstrap exception: ' + ','.join(map(str, missing)))
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--review-comments', type=Path)
    args = parser.parse_args()
    errors = validate(args.root, args.review_comments)
    for error in errors:
        print('ADVERSARIAL_LEARNING_STRICT_ERROR:', error)
    if errors:
        raise SystemExit(1)
    print('adversarial_learning_strict=PASS head_status=bound material_formats=badge+priority-prefix falsifier_effects=verified')


if __name__ == '__main__':
    main()
