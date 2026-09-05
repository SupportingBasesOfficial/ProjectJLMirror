#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'cannot load {path}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
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

    expect_violation(
        lambda: evaluator.LogicalContractIdentity('monitoring/legacy', 'event.created', 'canonical').canonical(),
        'ambiguous logical contract identity delimiter',
    )

    unreviewed = evaluator.ContractRevision(v1.identity, 'unreviewed-r9', v1.payload_schema, v1.semantic_manifest, v1.historical_metadata, 'git:not-reviewed')
    expect_violation(lambda: profile.registry.publish(reviewer, unreviewed, 'subject', '9', 'vendor-9'), 'unreviewed registry authority')

    forged_provenance = evaluator.ContractRevision(v1.identity, v1.revision, v1.payload_schema, v1.semantic_manifest, v1.historical_metadata, 'git:forged-provenance')
    assert forged_provenance.reviewed_content_sha256 != v1.reviewed_content_sha256
    expect_violation(lambda: profile.registry.publish(reviewer, forged_provenance, 'subject', '10', 'vendor-forged'), 'forged reviewed provenance')

    reformatted = evaluator.ContractRevision(v1.identity, 'format-only', v1.payload_schema, '{ "delivery": "at_least_once", "tenant_authority": "tenant_id", "event_identity": "message_id" }', v1.historical_metadata, 'git:format-only')
    assert reformatted.semantic_manifest_sha256 == v1.semantic_manifest_sha256

    numeric_1 = evaluator.ContractRevision(v1.identity, 'n1', v1.payload_schema, '{"threshold":1}', v1.historical_metadata, 'git:n1')
    numeric_10 = evaluator.ContractRevision(v1.identity, 'n10', v1.payload_schema, '{"threshold":1.0}', v1.historical_metadata, 'git:n10')
    numeric_1e0 = evaluator.ContractRevision(v1.identity, 'n1e0', v1.payload_schema, '{"threshold":1e0}', v1.historical_metadata, 'git:n1e0')
    assert numeric_1.semantic_manifest_sha256 == numeric_10.semantic_manifest_sha256 == numeric_1e0.semantic_manifest_sha256

    duplicate_manifest = evaluator.ContractRevision(v1.identity, 'duplicate-semantic', v1.payload_schema, '{"tenant_authority":"tenant_id","tenant_authority":"other"}', v1.historical_metadata, 'git:duplicate-semantic')
    expect_violation(lambda: profile.history.commit(reviewer, duplicate_manifest), 'duplicate semantic manifest member')

    frame_a = evaluator.ContractRevision(v1.identity, 'frame', v1.payload_schema, v1.semantic_manifest, evaluator.HistoricalMetadata('reader', 'upcaster', 'c\np'), 'q')
    frame_b = evaluator.ContractRevision(v1.identity, 'frame', v1.payload_schema, v1.semantic_manifest, evaluator.HistoricalMetadata('reader', 'upcaster', 'c'), 'p\nq')
    assert frame_a.reviewed_content_sha256 != frame_b.reviewed_content_sha256

    assert v1.payload_schema_sha256 == v2.payload_schema_sha256
    assert evaluator.compatibility(v1, v2) == 'semantic_review_required_breaking_until_proven_otherwise'

    rebound = evaluator.ContractRevision(v1.identity, v1.revision, v1.payload_schema, '{"tenant_authority":"provider_tenant"}', v1.historical_metadata, 'git:rebind')
    expect_violation(lambda: profile.history.commit(reviewer, rebound), 'history overwrite')

    anonymous = evaluator.Principal('', (), authenticated=False)
    no_role = evaluator.Principal('reader-no-role', ())
    expect_violation(lambda: profile.history.read(anonymous, v1.identity, v1.revision), 'anonymous direct history read')
    expect_violation(lambda: profile.history.read(no_role, v1.identity, v1.revision), 'unauthorized direct history read')
    expect_violation(lambda: profile.resolve(anonymous, v1.identity, v1.revision), 'anonymous catalog read')
    expect_violation(lambda: profile.registry.publish(reader, v1, 'subject', '20', 'vendor-20'), 'reader registry publish')

    original = profile.registry.publish(reviewer, v1, 'event-created', '17', 'vendor-abc')
    assert original == profile.registry.mapping(reader, v1)
    expect_violation(lambda: profile.registry.publish(reviewer, v1, 'changed-subject', '99', 'changed-vendor'), 'registry mapping provenance overwrite')

    before = profile.resolve(reader, v1.identity, v1.revision).reviewed_content_sha256
    profile.registry.available = False
    during = profile.resolve(reader, v1.identity, v1.revision).reviewed_content_sha256
    assert before == during == v1.reviewed_content_sha256
    profile.registry.available = True

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
        ('provenance assertion weakening', lambda m: m.__setitem__('source_assertions', [x for x in m['source_assertions'] if not x.startswith('reviewed_provenance_is_bound_')])),
        ('digest frame assertion weakening', lambda m: m.__setitem__('source_assertions', [x for x in m['source_assertions'] if not x.startswith('reviewed_content_digest_uses_')])),
        ('semantic canonical assertion weakening', lambda m: m.__setitem__('source_assertions', [x for x in m['source_assertions'] if not x.startswith('semantic_manifest_digest_uses_')])),
        ('semantic numeric assertion weakening', lambda m: m.__setitem__('source_assertions', [x for x in m['source_assertions'] if not x.startswith('semantic_manifest_numeric_equivalence_')])),
        ('mapping history assertion weakening', lambda m: m.__setitem__('source_assertions', [x for x in m['source_assertions'] if not x.startswith('registry_mapping_metadata_is_')])),
        ('product authority', lambda m: m['non_authority'].__setitem__('canonical_product_implementation_authority', 'granted')),
        ('wire coupling', lambda m: m['non_authority'].__setitem__('d4b_wire_selection', 'protobuf_profile')),
        ('contract-version coupling', lambda m: m['non_authority'].__setitem__('d4b_contract_version_selection', 'semantic_version_like_contract_revision')),
    )
    for label, mutation in mutations:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prepare_tree(root)
            if not mutate_manifest(root, mutation):
                raise AssertionError(f'validator did not reject {label}')


def main() -> None:
    behavior_falsification()
    validator_falsification()
    print(
        'd4b_catalog_tooling_falsification=PASS identity_delimiter_collision=blocked '
        'unreviewed_publish=blocked forged_provenance=blocked digest_frame_alias=blocked '
        'semantic_formatting=canonical semantic_numeric_spellings=canonical duplicate_semantic_member=blocked '
        'semantic_only_break=detected history_rebind=blocked direct_history_authz=blocked mapping_rebind=blocked '
        'outage_reinterpretation=blocked product_identity_coupling=blocked selection_credit_authority_coupling=blocked'
    )


if __name__ == '__main__':
    main()
