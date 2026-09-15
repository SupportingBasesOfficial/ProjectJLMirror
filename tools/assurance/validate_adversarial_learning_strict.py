#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import validate_adversarial_learning as base

HEAD_STATUS_WORKFLOW = Path('.github/workflows/adversarial-learning-reconciliation.yml')
MATERIAL_RE = re.compile(r'(?:\bP[012]\s+Badge\b|\[P[012]\])')
MAINTAINER_LOGINS = {'SupportingBasesOfficial'}
D4C_SELECTION_TEST = Path('tools/assurance/test_validate_d4c_selection.py')
G1_AUTHORIZATION_TEST = Path('tools/assurance/test_validate_g1_identity_tenant_shell_authorization.py')
G1_SCOPE_TEST = Path('tools/assurance/test_validate_g1_identity_tenant_shell_implementation_scope.py')
G1_READINESS_TEST = Path('tools/assurance/test_validate_g1_identity_tenant_shell_scope_readiness.py')
G1_SCOPE_PROBES = (
    'falsify_real_git_diff_gate',
    'falsify_candidate_metadata_fail_closed',
    'falsify_all_voluntary_metadata_omission',
    'falsify_runtime_workflow_semantics',
)
G1_AUTHORIZATION_READINESS_PROBE = 'falsify_trusted_scope_readiness_execution'
G1_READINESS_PROBE = 'falsify_live_readiness_guards'
G1_AUTHORIZATION_SCOPE_PROBE = 'falsify_implementation_scope_gate_execution'
G1_RUNTIME_SCOPE_PROBE = 'falsify_runtime_workflow_semantics'
NEGATIVE_HELPERS = {
    Path('tools/assurance/test_validate_d4d_selection.py'): {'must_fail'},
    D4C_SELECTION_TEST: {'must_fail', '_delivery_must_fail'},
    Path('tools/assurance/d4b_wire_schema/test_source_evidence.py'): {'must_fail'},
    Path('tools/assurance/test_validate_adversarial_learning.py'): {'expect_failure', 'expect_repository_failure'},
    Path('tools/assurance/test_validate_d4d_trace_context_source.py'): {'mutate_and_expect_failure'},
    G1_AUTHORIZATION_TEST: {'must_fail'},
}
D4C_CURRENT_WORKFLOWS = (
    Path('.github/workflows/d4-eventing-async-entry-gate.yml'),
    Path('.github/workflows/d4-d-profile-selection.yml'),
)
D4C_STALE_CURRENT_MARKERS = (
    "d4c['candidate'] is None", 'd4c["candidate"] is None',
    "tracks['D4-C']['candidate'] is None", 'tracks["D4-C"]["candidate"] is None',
    "d4c['candidate_status']=='not_selected'", 'd4c["candidate_status"]=="not_selected"',
    "tracks['D4-C']['candidate_status']=='not_selected'", 'tracks["D4-C"]["candidate_status"]=="not_selected"',
    "d4c['state']=='candidate_selection_open'", 'd4c["state"]=="candidate_selection_open"',
    "tracks['D4-C']['state']=='candidate_selection_open'", 'tracks["D4-C"]["state"]=="candidate_selection_open"',
)


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
            if isinstance(statement.value.func, ast.Name) and statement.value.func.id in helpers:
                return True
    return False


def _statements_have_negative_check(statements: list[ast.stmt], helpers: set[str]) -> bool:
    for statement in statements:
        if isinstance(statement, (ast.Return, ast.Raise)):
            return False
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            if isinstance(statement.value.func, ast.Name) and statement.value.func.id in helpers:
                return True
        if isinstance(statement, ast.For) and isinstance(statement.iter, (ast.List, ast.Tuple)) and statement.iter.elts:
            if _direct_negative_helper(statement.body, helpers):
                return True
    return False


def _has_negative_check(function: ast.AST, helpers: set[str]) -> bool:
    return isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) and _statements_have_negative_check(function.body, helpers)


def _load_module(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f'cannot load module: {path}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _validate_delivery_negative_helper(root: Path, path: Path) -> list[str]:
    module_name = '_jlmirror_delivery_negative_helper_probe'
    errors: list[str] = []
    try:
        module = _load_module(path, module_name)
        helper = getattr(module, '_delivery_must_fail', None)
        if not callable(helper):
            return ['registered delivery negative helper missing: _delivery_must_fail']
        def corrupt_manifest(probe_root: Path) -> None:
            manifest = probe_root / 'implementation/e2e-delivery/EXECUTION_MANIFEST.json'
            data = json.loads(manifest.read_text(encoding='utf-8'))
            data['required_layers'][0] = '__strict_invalid_layer__'
            manifest.write_text(json.dumps(data), encoding='utf-8')
        try:
            helper(corrupt_manifest, 'manifest_e2e16_exact_layers')
        except Exception as exc:
            errors.append(f'registered delivery negative helper rejects known-invalid probe incorrectly: {type(exc).__name__}: {exc}')
        def no_op(_probe_root: Path) -> None:
            return None
        try:
            helper(no_op, '__strict_acceptance_probe__')
        except AssertionError as exc:
            if 'delivery mutation unexpectedly accepted' not in str(exc):
                errors.append('registered delivery negative helper acceptance-path failure is not authoritative')
        except Exception as exc:
            errors.append(f'registered delivery negative helper acceptance probe failed unexpectedly: {type(exc).__name__}: {exc}')
        else:
            errors.append('registered delivery negative helper does not fail when mutation is accepted')
    except Exception as exc:
        errors.append(f'registered delivery negative helper could not execute: {type(exc).__name__}: {exc}')
    finally:
        sys.modules.pop(module_name, None)
    return errors


def _validate_g1_negative_helper(root: Path, path: Path) -> list[str]:
    module_name = '_jlmirror_g1_negative_helper_probe'
    dependency_name = 'validate_g1_identity_tenant_shell_authorization'
    saved_dependency = sys.modules.pop(dependency_name, None)
    fake_dependency = type(sys)(dependency_name)
    fake_dependency.load = lambda: {'effective_rule': 'expected'}
    def fake_validate_manifest(data: dict[str, Any]) -> None:
        if data.get('effective_rule') != 'expected':
            raise AssertionError('effective rule drift')
    fake_dependency.validate_manifest = fake_validate_manifest
    sys.modules[dependency_name] = fake_dependency
    errors: list[str] = []
    try:
        module = _load_module(path, module_name)
        helper = getattr(module, 'must_fail', None)
        if not callable(helper):
            return ['registered G1 negative helper missing: must_fail']
        def corrupt_effective_rule(data: dict[str, Any]) -> None:
            data['effective_rule'] = '__strict_invalid_effective_rule__'
        try:
            helper(corrupt_effective_rule, 'effective rule drift')
        except Exception as exc:
            errors.append(f'registered G1 negative helper rejects known-invalid probe incorrectly: {type(exc).__name__}: {exc}')
        def no_op(_data: dict[str, Any]) -> None:
            return None
        try:
            helper(no_op, '__strict_acceptance_probe__')
        except AssertionError as exc:
            if 'mutation unexpectedly accepted' not in str(exc):
                errors.append('registered G1 negative helper acceptance-path failure is not authoritative')
        except Exception as exc:
            errors.append(f'registered G1 negative helper acceptance probe failed unexpectedly: {type(exc).__name__}: {exc}')
        else:
            errors.append('registered G1 negative helper does not fail when mutation is accepted')
    except Exception as exc:
        errors.append(f'registered G1 negative helper could not execute: {type(exc).__name__}: {exc}')
    finally:
        sys.modules.pop(module_name, None)
        sys.modules.pop(dependency_name, None)
        if saved_dependency is not None:
            sys.modules[dependency_name] = saved_dependency
    return errors


def _validate_g1_scope_probe_effects(root: Path) -> list[str]:
    path = root / G1_SCOPE_TEST
    module_name = '_jlmirror_g1_scope_probe_effects'
    errors: list[str] = []
    try:
        module = _load_module(path, module_name)
        original_validate = module.scope.validate
        module.scope.validate = lambda *args, **kwargs: (True, [])
        try:
            for probe_name in G1_SCOPE_PROBES:
                probe = getattr(module, probe_name, None)
                if not callable(probe):
                    errors.append(f'credited G1 scope probe missing: {probe_name}')
                    continue
                try:
                    probe()
                except AssertionError:
                    pass
                except Exception as exc:
                    errors.append(f'credited G1 scope probe failed unexpectedly under permissive evaluator: {probe_name}:{type(exc).__name__}:{exc}')
                else:
                    errors.append(f'credited G1 scope probe does not reject permissive evaluator/no-op body: {probe_name}')
        finally:
            module.scope.validate = original_validate
    except Exception as exc:
        errors.append(f'credited G1 scope probes could not execute: {type(exc).__name__}: {exc}')
    finally:
        sys.modules.pop(module_name, None)
    return errors


def _direct_delegation_line(path: Path, outer_probe: str, delegated_module: str, inner_probe: str) -> tuple[int | None, list[str]]:
    try:
        source = path.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=str(path))
    except Exception as exc:
        return None, [f'cannot parse credited G1 outer probe: {type(exc).__name__}: {exc}']
    function = next((node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == outer_probe), None)
    if function is None:
        return None, [f'credited G1 outer probe missing: {outer_probe}']
    alias: str | None = None
    matches: list[ast.Expr] = []
    for statement in function.body:
        if isinstance(statement, ast.Import):
            for imported in statement.names:
                if imported.name == delegated_module:
                    alias = imported.asname or imported.name
        if alias and isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call = statement.value
            if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) and call.func.value.id == alias and call.func.attr == inner_probe and not call.args and not call.keywords:
                matches.append(statement)
    if alias is None or len(matches) != 1:
        return None, [f'credited G1 outer probe must contain exactly one direct delegation: {outer_probe}->{inner_probe}']
    statement = matches[0]
    segment = ast.get_source_segment(source, statement)
    expected = f'{alias}.{inner_probe}()'
    if segment is None or segment.strip() != expected:
        return None, [f'credited G1 outer delegation statement must be isolated exact call: {expected}']
    return statement.lineno, []


def _validate_outer_delegation_effect(root: Path, *, outer_probe: str, delegated_module: str, inner_probe: str, sibling_noops: tuple[str, ...], label: str) -> list[str]:
    path = root / G1_AUTHORIZATION_TEST
    expected_line, errors = _direct_delegation_line(path, outer_probe, delegated_module, inner_probe)
    if expected_line is None:
        return errors
    module_name = f'_jlmirror_{label}_outer_effect'
    saved_delegated = sys.modules.pop(delegated_module, None)
    sentinel_module = type(sys)(delegated_module)
    audit_state: dict[str, Any] = {'phase': 'import', 'codes': []}
    audit_event = f'jlmirror.g1.{label}.delegation'

    def audit_hook(event: str, _args: tuple[Any, ...]) -> None:
        if event == audit_event:
            audit_state['codes'].append((audit_state['phase'], sys._getframe(1).f_code))
    sys.addaudithook(audit_hook)

    if label == 'readiness':
        def delegated_probe() -> None:
            sys.audit('jlmirror.g1.readiness.delegation')
            raise RuntimeError('strict G1 readiness delegation sentinel')
    else:
        def delegated_probe() -> None:
            sys.audit('jlmirror.g1.scope.delegation')
            raise RuntimeError('strict G1 scope delegation sentinel')

    sentinel_code = delegated_probe.__code__
    if delegated_probe.__closure__ is not None or delegated_probe.__defaults__:
        errors.append(f'strict G1 {label} sentinel unexpectedly exposes closure/default state')
    for name in sibling_noops:
        setattr(sentinel_module, name, lambda: None)
    setattr(sentinel_module, inner_probe, delegated_probe)
    sys.modules[delegated_module] = sentinel_module
    try:
        module = _load_module(path, module_name)
        import_hits = [code for phase, code in audit_state['codes'] if phase == 'import' and code is sentinel_code]
        if import_hits:
            errors.append(f'credited G1 {label} outer module invoked delegated sentinel during import: {len(import_hits)}')
        audit_state['codes'].clear()
        audit_state['phase'] = 'invocation'
        setattr(sentinel_module, inner_probe, delegated_probe)
        probe = getattr(module, outer_probe, None)
        if not callable(probe):
            return errors + [f'credited G1 outer probe missing at runtime: {outer_probe}']
        try:
            probe()
        except BaseException as exc:
            tb = exc.__traceback__
            callsite_authenticated = False
            while tb is not None and tb.tb_next is not None:
                if tb.tb_frame.f_code is probe.__code__ and tb.tb_lineno == expected_line and tb.tb_next.tb_frame.f_code is sentinel_code:
                    callsite_authenticated = True
                    break
                tb = tb.tb_next
            if not callsite_authenticated:
                errors.append(f'credited G1 {label} delegation did not originate at exact authenticated attribute call site line {expected_line}')
        else:
            errors.append(f'credited G1 {label} outer probe did not execute delegated sentinel')
        invocation_hits = [code for phase, code in audit_state['codes'] if phase == 'invocation' and code is sentinel_code]
        if len(invocation_hits) != 1:
            errors.append(f'credited G1 {label} sentinel invocation count drift: {len(invocation_hits)}')
    except Exception as exc:
        errors.append(f'credited G1 {label} outer probe could not execute: {type(exc).__name__}: {exc}')
    finally:
        sys.modules.pop(module_name, None)
        sys.modules.pop(delegated_module, None)
        if saved_delegated is not None:
            sys.modules[delegated_module] = saved_delegated
    return errors


def _validate_g1_readiness_probe_effects(root: Path) -> list[str]:
    path = root / G1_READINESS_TEST
    errors: list[str] = []
    repo = 'SupportingBasesOfficial/ProjectJLMirror'; default_branch = 'main'; base_sha = 'a' * 40; head_sha = 'b' * 40
    head_ref = 'impl/g1-identity-tenant-protected-shell-demo'; run_id = 123456789; server = 'https://github.com'; pr_number = 1530
    trusted_login = 'github-actions[bot]'; trusted_id = 41898282; required_label = 'jlmirror-slice:g1-identity-tenant-shell'
    workflow_name = 'JLMIRROR G1 Identity Tenant Shell Implementation Scope'; workflow_path = '.github/workflows/g1-identity-tenant-shell-implementation-scope.yml'
    scope_context = 'JLMIRROR / g1-identity-tenant-shell-implementation-scope'; ready_context = 'JLMIRROR / g1-identity-tenant-shell-merge-readiness'
    def clone(value: Any) -> Any:
        return json.loads(json.dumps(value))
    def publisher_name(*, pr: int = pr_number, mode: str = 'attest', ref: str = head_ref) -> str:
        return f'g1-publish-final pr={pr} mode={mode} base={base_sha} head={head_sha} ref={ref}'
    repository = {'default_branch': default_branch, 'full_name': repo}
    pr = {'state':'open','base':{'ref':default_branch,'sha':base_sha,'repo':{'full_name':repo}},'head':{'ref':head_ref,'sha':head_sha,'repo':{'full_name':repo}},'labels':[{'name':required_label}]}
    branch = {'commit':{'sha':base_sha}}
    run = {'id':run_id,'name':workflow_name,'path':workflow_path,'event':'issue_comment','status':'completed','conclusion':'success','head_branch':default_branch,'head_sha':base_sha,'repository':{'full_name':repo}}
    def status(context: str, description: str) -> dict[str, Any]:
        return {'context':context,'state':'success','description':description,'target_url':f'{server}/{repo}/actions/runs/{run_id}','created_at':'2026-09-14T20:00:00Z','creator':{'login':trusted_login,'id':trusted_id}}
    def jobs(mode: str = 'attest', *, prn: int = pr_number, ref: str = head_ref) -> dict[str, Any]:
        return {'jobs':[{'name':publisher_name(pr=prn, mode=mode, ref=ref),'status':'completed','conclusion':'success'}]}
    def call(*, evidence: str = 'scope') -> dict[str, Any]:
        context = scope_context if evidence == 'scope' else ready_context
        description = f'G1 scope PASS base={base_sha} head={head_sha}' if evidence == 'scope' else f'G1 ready PASS base={base_sha} head={head_sha}'
        mode = 'attest' if evidence == 'scope' else 'ready'
        return {'repository':clone(repository),'pr':clone(pr),'branch':clone(branch),'statuses':clone([status(context, description)]),'run':clone(run),'jobs':clone(jobs(mode)),'repo':repo,'pr_number':pr_number,'server_url':server,'evidence':evidence}
    expected_calls = [call(), call(evidence='ready')]
    spoof = call(); spoof['statuses'][0]['creator'] = {'login':'contributor','id':999}; expected_calls.append(spoof)
    spoof_bot = call(); spoof_bot['statuses'][0]['creator'] = {'login':trusted_login,'id':999}; expected_calls.append(spoof_bot)
    wrong_pr = call(); wrong_pr['jobs'] = jobs(prn=9999); expected_calls.append(wrong_pr)
    wrong_mode = call(); wrong_mode['jobs'] = jobs(mode='ready'); expected_calls.append(wrong_mode)
    wrong_ref = call(); wrong_ref['jobs'] = jobs(ref='impl/g1-identity-tenant-protected-shell-other'); expected_calls.append(wrong_ref)
    stale_base = call(); stale_base['statuses'][0]['description'] = f'G1 scope PASS base={"c" * 40} head={head_sha}'; expected_calls.append(stale_base)
    stale_tip = call(); stale_tip['branch']['commit']['sha'] = 'd' * 40; expected_calls.append(stale_tip)
    missing_label = call(); missing_label['pr']['labels'] = []; expected_calls.append(missing_label)
    renamed_head = call(); renamed_head['pr']['head']['ref'] = 'feature/renamed'; expected_calls.append(renamed_head)
    changed_default = call(); changed_default['repository']['default_branch'] = 'trunk'; expected_calls.append(changed_default)
    wrong_event = call(); wrong_event['run']['event'] = 'push'; expected_calls.append(wrong_event)
    wrong_path = call(); wrong_path['run']['path'] = '.github/workflows/other.yml'; expected_calls.append(wrong_path)
    wrong_base_run = call(); wrong_base_run['run']['head_sha'] = 'e' * 40; expected_calls.append(wrong_base_run)
    failed_publisher = call(); failed_publisher['jobs']['jobs'][0]['conclusion'] = 'failure'; expected_calls.append(failed_publisher)
    malformed_target = call(); malformed_target['statuses'][0]['target_url'] = 'https://example.invalid/run/123'; expected_calls.append(malformed_target)
    untrusted_newer = call(); untrusted_newer['statuses'].append({'context':scope_context,'state':'success','description':f'G1 scope PASS base={base_sha} head={head_sha}','target_url':f'{server}/{repo}/actions/runs/999999999','created_at':'2026-09-14T21:00:00Z','creator':{'login':'contributor','id':999}}); expected_calls.append(untrusted_newer)

    module1_name = '_jlmirror_g1_readiness_probe_effects_sequence'
    try:
        module1 = _load_module(path, module1_name)
        original_validate = module1.readiness.validate_live_readiness
        original_must_reject = module1.must_reject
        state: dict[str, Any] = {'calls': [], 'negative_boundaries': [], 'invalid_deltas': []}
        def permissive_verifier(**kwargs: Any) -> tuple[str, str, int]:
            state['calls'].append(clone(kwargs)); return (base_sha, head_sha, run_id)
        def instrumented_must_reject(fn: Any, _fragment: str) -> None:
            before = len(state['calls']); fn(); after = len(state['calls'])
            state['negative_boundaries'].append((before, after))
            if after != before + 1: state['invalid_deltas'].append((before, after))
        module1.readiness.validate_live_readiness = permissive_verifier
        module1.must_reject = instrumented_must_reject
        probe = getattr(module1, G1_READINESS_PROBE, None)
        if not callable(probe):
            errors.append(f'credited G1 readiness probe missing: {G1_READINESS_PROBE}')
        else:
            try:
                probe()
            except Exception as exc:
                errors.append(f'credited G1 readiness probe aborted before completing authenticated semantic cases: {type(exc).__name__}:{exc}')
            if state['calls'] != expected_calls:
                mismatches = [i for i in range(max(len(state['calls']), len(expected_calls))) if i >= len(state['calls']) or i >= len(expected_calls) or state['calls'][i] != expected_calls[i]]
                errors.append(f'credited G1 readiness probe semantic call sequence drift: calls={len(state["calls"])} expected={len(expected_calls)} mismatches={mismatches}')
            expected_boundaries = [(i, i + 1) for i in range(2, 17)]
            if state['negative_boundaries'] != expected_boundaries:
                errors.append(f'credited G1 readiness negative-case boundaries drift: actual={state["negative_boundaries"]} expected={expected_boundaries}')
            if state['invalid_deltas']:
                errors.append(f'credited G1 readiness negative case did not invoke permissive verifier exactly once: {state["invalid_deltas"]}')
        module1.readiness.validate_live_readiness = original_validate
        module1.must_reject = original_must_reject
    except Exception as exc:
        errors.append(f'credited G1 readiness semantic sequence could not execute: {type(exc).__name__}: {exc}')
    finally:
        sys.modules.pop(module1_name, None)

    module2_name = '_jlmirror_g1_readiness_probe_effects_fresh_rejection'
    try:
        module2 = _load_module(path, module2_name)
        rejection_calls: list[dict[str, Any]] = []
        def rejection_verifier(**kwargs: Any) -> tuple[str, str, int]:
            rejection_calls.append(clone(kwargs)); return (base_sha, head_sha, run_id)
        module2.readiness.validate_live_readiness = rejection_verifier
        probe2 = getattr(module2, G1_READINESS_PROBE, None)
        if not callable(probe2):
            errors.append(f'fresh credited G1 readiness probe missing: {G1_READINESS_PROBE}')
        else:
            try:
                probe2()
            except AssertionError as exc:
                if len(rejection_calls) != 3:
                    errors.append(f'fresh G1 readiness permissive-rejection failed at wrong boundary: calls={len(rejection_calls)} expected=3')
                if 'readiness mutation unexpectedly accepted:' not in str(exc):
                    errors.append(f'fresh G1 readiness permissive-rejection failure is not authoritative: {exc}')
            except Exception as exc:
                errors.append(f'fresh G1 readiness permissive-rejection failed unexpectedly: {type(exc).__name__}:{exc}')
            else:
                errors.append('fresh G1 readiness probe accepts a permissive verifier when real must_reject semantics are preserved')
    except Exception as exc:
        errors.append(f'fresh G1 readiness rejection module could not execute: {type(exc).__name__}: {exc}')
    finally:
        sys.modules.pop(module2_name, None)
    return errors


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
        if rel == D4C_SELECTION_TEST:
            errors.extend(_validate_delivery_negative_helper(root, path))
        if rel == G1_AUTHORIZATION_TEST:
            errors.extend(_validate_g1_negative_helper(root, path))
            errors.extend(_validate_g1_scope_probe_effects(root))
            errors.extend(_validate_outer_delegation_effect(
                root,
                outer_probe=G1_AUTHORIZATION_READINESS_PROBE,
                delegated_module='test_validate_g1_identity_tenant_shell_scope_readiness',
                inner_probe=G1_READINESS_PROBE,
                sibling_noops=(),
                label='readiness',
            ))
            errors.extend(_validate_outer_delegation_effect(
                root,
                outer_probe=G1_AUTHORIZATION_SCOPE_PROBE,
                delegated_module='test_validate_g1_identity_tenant_shell_implementation_scope',
                inner_probe=G1_RUNTIME_SCOPE_PROBE,
                sibling_noops=('falsify_real_git_diff_gate', 'falsify_candidate_metadata_fail_closed', 'falsify_all_voluntary_metadata_omission'),
                label='scope',
            ))
            errors.extend(_validate_g1_readiness_probe_effects(root))
        credited, credited_errors = base._reachable_main_falsifiers(path)
        errors.extend(credited_errors)
        for name in sorted(credited):
            function = functions.get(name)
            if function is None or not _has_negative_check(function, helpers):
                errors.append(f'credited falsifier performs no guaranteed registered negative check: {rel}:{name}')
    return errors


def _validate_d4c_current_workflow_projections(root: Path) -> list[str]:
    errors: list[str] = []
    for rel in D4C_CURRENT_WORKFLOWS:
        path = root / rel
        if not path.is_file():
            errors.append(f'governed D4-C current-state workflow missing: {rel}')
            continue
        text = path.read_text(encoding='utf-8')
        for marker in D4C_STALE_CURRENT_MARKERS:
            if marker in text:
                errors.append(f'stale D4-C current-state workflow projection: {rel}:{marker}')
    return errors


def _validate_head_status_workflow(root: Path) -> list[str]:
    path = root / HEAD_STATUS_WORKFLOW
    if not path.is_file():
        return [f'head-associated reconciliation workflow missing: {HEAD_STATUS_WORKFLOW}']
    text = path.read_text(encoding='utf-8')
    markers = {
        'issue_comment trigger':'issue_comment:',
        'per-PR concurrency':'group: adversarial-learning-${{ github.event.issue.number }}',
        'superseded-run cancellation':'cancel-in-progress: true',
        'zero workflow-level permissions':'permissions: {}',
        'trusted resolve job':'  resolve:',
        'isolated pending publisher':'  publish-pending:',
        'read-only analysis job':'  analyze:',
        'isolated final publisher':'  publish-final:',
        'resolved PR head lookup':'pulls/${PR_NUMBER}',
        'head status endpoint':'statuses/${PR_HEAD_SHA}',
        'stable status context':'JLMIRROR / adversarial-learning-reconciliation',
        'strict reconciliation':'validate_adversarial_learning_strict.py',
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
    for key in ('user','author'):
        value = row.get(key)
        if isinstance(value, dict) and isinstance(value.get('login'), str):
            return value['login']
    return None


def _strict_material_ids(review_comments: Path) -> set[int]:
    comments = _flatten(json.loads(review_comments.read_text(encoding='utf-8')))
    return {row['id'] for row in comments if isinstance(row.get('id'), int) and isinstance(row.get('body'), str) and MATERIAL_RE.search(row['body']) and _reviewer_login(row) not in MAINTAINER_LOGINS}


def validate(root: Path, review_comments: Path | None = None) -> list[str]:
    root = root.resolve()
    errors = list(base.validate(root, None))
    errors.extend(_validate_head_status_workflow(root))
    errors.extend(_validate_d4c_current_workflow_projections(root))
    errors.extend(_validate_falsifier_effects(root))
    if review_comments is not None:
        entries, ledger_errors = base._load_ledger_entries(root)
        errors.extend(ledger_errors)
        review_ids = {row.get('review_comment_id') for row in entries if isinstance(row, dict) and row.get('source') == 'external_review' and isinstance(row.get('review_comment_id'), int)}
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
    print('adversarial_learning_strict=PASS head_status=isolated+fresh reviewer_identity=external-only material_formats=badge+priority-prefix d4c_current_projection=terminal-governed-surfaces falsifier_effects=executed-negative-helper g1_negative_helper=executed-reject+accept g1_scope_probes=permissive-evaluator-rejected+runtime-workflow-semantics g1_outer_delegation=ast+exact-callsite-traceback g1_readiness_probe=exact-semantic-call-sequence+negative-boundaries+fresh-permissive-rejection')


if __name__ == '__main__':
    main()
