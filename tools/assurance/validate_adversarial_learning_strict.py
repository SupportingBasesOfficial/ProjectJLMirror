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
MAINTAINER_LOGINS = {'SupportingBasesOfficial'}
NEGATIVE_HELPERS = {
    Path('tools/assurance/test_validate_d4d_selection.py'): {'must_fail'},
    Path('tools/assurance/d4b_wire_schema/test_source_evidence.py'): {'must_fail'},

    Path('tools/assurance/test_validate_adversarial_learning.py'): {'expect_failure', 'expect_repository_failure'},
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


def _direct_negative_helper(statements: list[ast.stmt], helpers: set[str]) -> bool:
    for statement in statements:
        if isinstance(statement, (ast.Return, ast.Raise)):
            return False
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call = statement.value
            if isinstance(call.func, ast.Name) and call.func.id in helpers:
                return True
    return False


def _statements_have_negative_check(statements: list[ast.stmt], helpers: set[str]) -> bool:
    for statement in statements:
        if isinstance(statement, (ast.Return, ast.Raise)):
            return False
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call = statement.value
            if isinstance(call.func, ast.Name) and call.func.id in helpers:
                return True
        if isinstance(statement, ast.For) and isinstance(statement.iter, (ast.List, ast.Tuple)) and len(statement.iter.elts) > 0:
            if _direct_negative_helper(statement.body, helpers):
                return True
    return False


def _has_negative_check(function: ast.AST, helpers: set[str]) -> bool:
    return isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) and _statements_have_negative_check(function.body, helpers)


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
                errors.append(f'credited falsifier performs no guaranteed registered negative check: {rel}:{name}')
    return errors


def _validate_head_status_workflow(root: Path) -> list[str]:
    path = root / HEAD_STATUS_WORKFLOW
    if not path.is_file():
        return [f'head-associated reconciliation workflow missing: {HEAD_STATUS_WORKFLOW}']
    text = path.read_text(encoding='utf-8')
    markers = {
        'issue_comment trigger': 'issue_comment:',
        'per-PR concurrency': 'group: adversarial-learning-${{ github.event.issue.number }}',
        'superseded-run cancellation': 'cancel-in-progress: true',
        'zero workflow-level permissions': 'permissions: {}',
        'trusted resolve job': '  resolve:',
        'isolated pending publisher': '  publish-pending:',
        'read-only analysis job': '  analyze:',
        'isolated final publisher': '  publish-final:',
        'resolved PR head lookup': 'pulls/${PR_NUMBER}',
        'head status endpoint': 'statuses/${PR_HEAD_SHA}',
        'stable status context': 'JLMIRROR / adversarial-learning-reconciliation',
        'strict reconciliation': 'validate_adversarial_learning_strict.py',
    }
    errors = [f'head-associated reconciliation workflow missing {name}' for name, marker in markers.items() if marker not in text]
    if 'workflow_dispatch:' in text:
        errors.append('head-associated reconciliation must not expose an unbound manual dispatch path')
    if text.count('statuses/${PR_HEAD_SHA}') != 2:
        errors.append('head-associated reconciliation must publish pending and final status to the resolved PR head exactly twice')
    if 'statuses/${GITHUB_SHA}' in text:
        errors.append('head-associated reconciliation must never publish review status to the event/default-branch SHA')
    return errors


def _reviewer_login(row: dict[str, Any]) -> str | None:
    for key in ('user', 'author'):
        value = row.get(key)
        if isinstance(value, dict) and isinstance(value.get('login'), str):
            return value['login']
    return None


def _strict_material_ids(review_comments: Path) -> set[int]:
    comments = _flatten(json.loads(review_comments.read_text(encoding='utf-8')))
    return {
        row['id']
        for row in comments
        if isinstance(row.get('id'), int)
        and isinstance(row.get('body'), str)
        and MATERIAL_RE.search(row['body'])
        and _reviewer_login(row) not in MAINTAINER_LOGINS
    }


def validate(root: Path, review_comments: Path | None = None) -> list[str]:
    root = root.resolve()
    # Static graph validation is delegated to the base validator. Dynamic review
    # reconciliation is performed only here so renderer formats and reviewer
    # identity have one strict source of truth.
    errors = list(base.validate(root, None))
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
            errors.append('strict external material PR findings missing from learning ledger or bootstrap exception: ' + ','.join(map(str, missing)))
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
    print('adversarial_learning_strict=PASS head_status=isolated+fresh reviewer_identity=external-only material_formats=badge+priority-prefix falsifier_effects=guaranteed-negative-helper')


if __name__ == '__main__':
    main()
