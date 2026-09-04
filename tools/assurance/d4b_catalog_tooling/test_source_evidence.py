#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'cannot load {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evaluator = load_module('d4b_catalog_evaluator', HERE / 'evaluate_candidates.py')
validator = load_module('d4b_catalog_validator', HERE / 'validate_source_evidence.py')


def expect_violation(fn, label: str) -> None:
    try:
        fn()
    except evaluator.EvidenceViolation:
        return
    raise AssertionError(f'{label} was not blocked')


def behavior_falsification() -> None:
    profile, reviewer, reader, v1, v2 = evaluator.candidate_fixture('registry_backed_catalog')
    assert profile.registry is not None

    # Registry cannot manufacture authority for an unreviewed revision.
    unreviewed = evaluator.ContractRevision(
        identity=v1.identity,
        revision='unreviewed-r9',
        payload_schema=v1.payload_schema,
        semantic_manifest=v1.semantic_manifest,
        historical_metadata=v1.historical_metadata,
        reviewed_provenance='git:not-reviewed',
    )
    expect_violation(
        lambda: profile.registry.publish(reviewer, unreviewed, 'subject', '9', 'vendor-9'),
        'unreviewed registry authority',
    )

    # Same payload syntax cannot hide a protected semantic break.
    assert v1.payload_schema_sha256 == v2.payload_schema_sha256
    assert evaluator.compatibility(v1, v2) == 'semantic_review_required_breaking_until_proven_otherwise'

    # Existing reviewed revision cannot be rebound to different content.
    rebound = evaluator.ContractRevision(
        identity=v1.identity,
        revision=v1.revision,
        payload_schema=v1.payload_schema,
        semantic_manifest='{"tenant_authority":"provider_tenant"}',
        historical_metadata=v1.historical_metadata,
        reviewed_provenance='git:rebind',
    )
    expect_violation(lambda: profile.history.commit(reviewer, rebound), 'history overwrite')

    # Authentication and authorization remain independent gates.
    expect_violation(
        lambda: profile.resolve(evaluator.Principal('', (), authenticated=False), v1.identity, v1.revision),
        'anonymous read',
    )
    expect_violation(
        lambda: profile.registry.publish(reader, v1, 'subject', '20', 'vendor-20'),
        'reader registry publish',
    )

    # Tool outage cannot reinterpret committed content.
    before = profile.resolve(reader, v1.identity, v1.revision).reviewed_content_sha256
    profile.registry.available = False
    during = profile.resolve(reader, v1.identity, v1.revision).reviewed_content_sha256
    assert before == during == v1.reviewed_content_sha256
    profile.registry.available = True

    # Product replacement changes physical IDs only.
    replacement = evaluator.RegistryMirror('registry-fixture-replacement', profile.history)
    replacement.publish(reviewer, v1, 'other-subject', '1', 'other-vendor')
    old = profile.registry.mapping(reader, v1)
    new = replacement.mapping(reader, v1)
    assert old.product != new.product and old.vendor_id != new.vendor_id
    assert old.reviewed_content_sha256 == new.reviewed_content_sha256 == v1.reviewed_content_sha256
    assert v1.identity.canonical() == 'monitoring/event.created/canonical'


def prepare_tree(tmp: Path) -> None:
    for rel in (validator.MANIFEST, validator.PLAN, validator.LEDGER, validator.STATE):
        src = ROOT / rel
        dst = tmp / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def mutate_manifest(tmp: Path, mutator) -> list[str]:
    path = tmp / validator.MANIFEST
    value = json.loads(path.read_text())
    mutator(value)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return validator.validate(tmp)


def validator_falsification() -> None:
    mutations = (
        ('hidden selection', lambda m: m.__setitem__('selection_state', 'selected')),
        ('authority grant', lambda m: m.__setitem__('selection_authority', 'granted')),
        ('auto credit', lambda m: m.__setitem__('current_run_auto_credit', True)),
        ('ledger credit', lambda m: m.__setitem__('ledger_credit', ['catalog_tooling'])),
        ('candidate promotion', lambda m: m['candidate_results'].__setitem__('reviewed_git_catalog', 'selected')),
        ('proof weakening', lambda m: m.__setitem__('required_proofs', m['required_proofs'][:-1])),
        ('product authority', lambda m: m['non_authority'].__setitem__('canonical_product_implementation_authority', 'granted')),
        ('wire coupling', lambda m: m['non_authority'].__setitem__('d4b_wire_selection', 'protobuf_profile')),
        ('contract-version coupling', lambda m: m['non_authority'].__setitem__('d4b_contract_version_selection', 'semantic_version_like_contract_revision')),
    )
    for label, mutation in mutations:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prepare_tree(root)
            errors = mutate_manifest(root, mutation)
            if not errors:
                raise AssertionError(f'validator did not reject {label}')


def main() -> None:
    behavior_falsification()
    validator_falsification()
    print(
        'd4b_catalog_tooling_falsification=PASS '
        'unreviewed_publish=blocked semantic_only_break=detected history_rebind=blocked '
        'authz=blocked outage_reinterpretation=blocked product_identity_coupling=blocked '
        'selection_credit_authority_coupling=blocked'
    )


if __name__ == '__main__':
    main()
