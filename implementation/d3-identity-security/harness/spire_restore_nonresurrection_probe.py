#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import time

from jlmirror_authority.model import AdmissionDenied, EnvironmentClass, PrincipalKind
from jlmirror_authority.runtime_profiles import API_AUTH_BOUNDARY
from jlmirror_authority.workload import VerifiedWorkloadPeer, admit_workload_peer

TRUST_DOMAIN = "rotation.validation.d3.jlmirror.invalid"
CANONICAL_SPIFFE_ID = (
    "spiffe://rotation.validation.d3.jlmirror.invalid/"
    "environment.validation@1/runtime.api@1/rotation-evidence"
)
WIRE_SPIFFE_ID = "spiffe://rotation.validation.d3.jlmirror.invalid/runtime/rotation-evidence/v1/workload"
_URI_RE = re.compile(r"URI:([^,\s]+)")


@dataclass(frozen=True)
class CurrentnessState:
    fence_sequence: int
    bundle_generation: str
    credential_generation: str


def _run(*args: str, check: bool = True, timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        args,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            "command failed "
            f"rc={proc.returncode} args={args!r} "
            f"stdout={proc.stdout.strip()!r} stderr={proc.stderr.strip()!r}"
        )
    return proc


def _openssl_date(cert: Path, option: str) -> datetime:
    output = _run("openssl", "x509", "-in", str(cert), "-noout", option).stdout.strip()
    _, value = output.split("=", 1)
    parsed = datetime.strptime(value, "%b %d %H:%M:%S %Y %Z")
    return parsed.replace(tzinfo=timezone.utc)


def _digest_id(prefix: str, path: Path) -> str:
    return f"{prefix}:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _credential_generation(authority_id: str) -> str:
    if not authority_id or any(ch.isspace() for ch in authority_id):
        raise AssertionError("SPIRE authority identifier is not suitable for generation binding")
    return f"issuer:{authority_id}"


def _fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _certificate_fingerprint(path: Path) -> str:
    output = _run(
        "openssl", "x509", "-in", str(path), "-noout", "-fingerprint", "-sha256"
    ).stdout.strip()
    _, value = output.split("=", 1)
    return value.replace(":", "").lower()


def _require_file(path: Path) -> Path:
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"required SPIRE restore evidence is missing or empty: {path}")
    return path


def _wire_identity(cert: Path) -> str:
    output = _run(
        "openssl", "x509", "-in", str(cert), "-noout", "-ext", "subjectAltName"
    ).stdout
    identities = _URI_RE.findall(output)
    if identities != [WIRE_SPIFFE_ID]:
        raise AssertionError(f"unexpected restored SPIRE SVID URI set: {identities!r}")
    return identities[0]


def _expect_denied(label: str, fragment: str, call) -> None:
    try:
        call()
    except AdmissionDenied as exc:
        if fragment not in str(exc):
            raise AssertionError(
                f"{label}: wrong denial reason; expected fragment={fragment!r} actual={str(exc)!r}"
            ) from exc
        return
    raise AssertionError(f"{label}: restored/stale authority was unexpectedly admitted")


def _peer(*, cert: Path, bundle_generation: str, credential_generation: str) -> VerifiedWorkloadPeer:
    return VerifiedWorkloadPeer(
        spiffe_id=CANONICAL_SPIFFE_ID,
        certificate_not_before=_openssl_date(cert, "-startdate"),
        certificate_not_after=_openssl_date(cert, "-enddate"),
        trust_bundle_generation=bundle_generation,
        workload_credential_generation=credential_generation,
    )


def _admit(
    peer: VerifiedWorkloadPeer,
    *,
    current_bundle: str,
    current_credential: str,
    now: datetime,
):
    return admit_workload_peer(
        peer=peer,
        expected_trust_domain=TRUST_DOMAIN,
        expected_environment=EnvironmentClass.VALIDATION,
        allowed_runtime_profiles=frozenset({API_AUTH_BOUNDARY.runtime_profile_id}),
        current_trust_bundle_generation=current_bundle,
        current_workload_credential_generation=current_credential,
        current_max_certificate_lifetime=timedelta(seconds=45),
        now=now,
    )


def _write_server_config(*, path: Path, data_dir: Path, socket_path: Path, port: int) -> None:
    path.write_text(
        f'''server {{
    bind_address = "127.0.0.1"
    bind_port = "{port}"
    socket_path = "{socket_path}"
    trust_domain = "{TRUST_DOMAIN}"
    data_dir = "{data_dir}"
    log_level = "INFO"
    ca_ttl = "30m"
    default_x509_svid_ttl = "30s"
}}

plugins {{
    DataStore "sql" {{
        plugin_data {{
            database_type = "sqlite3"
            connection_string = "{data_dir / 'datastore.sqlite3'}"
        }}
    }}
    NodeAttestor "join_token" {{
        plugin_data {{}}
    }}
    KeyManager "disk" {{
        plugin_data {{
            keys_path = "{data_dir / 'keys.json'}"
        }}
    }}
}}
''',
        encoding="utf-8",
    )


def _start_server(
    *, server_bin: Path, config: Path, socket_path: Path, log_path: Path
) -> tuple[subprocess.Popen[str], object]:
    _run(str(server_bin), "validate", "-config", str(config))
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [str(server_bin), "run", "-config", str(config)],
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    for _ in range(120):
        if process.poll() is not None:
            log_handle.flush()
            raise AssertionError(
                "SPIRE server exited before readiness: "
                + log_path.read_text(encoding="utf-8", errors="replace")[-4000:]
            )
        if socket_path.exists():
            probe = _run(
                str(server_bin),
                "bundle",
                "show",
                "-socketPath",
                str(socket_path),
                "-format",
                "pem",
                check=False,
                timeout=3.0,
            )
            if probe.returncode == 0 and probe.stdout.strip():
                return process, log_handle
        time.sleep(0.1)
    _stop_server(process, log_handle)
    raise AssertionError(
        "SPIRE server did not become ready: "
        + log_path.read_text(encoding="utf-8", errors="replace")[-4000:]
    )


def _stop_server(process: subprocess.Popen[str] | None, log_handle: object | None) -> None:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    if log_handle is not None and not getattr(log_handle, "closed", False):
        log_handle.close()


def _show_active_authority(server_bin: Path, socket_path: Path) -> str:
    payload = json.loads(
        _run(
            str(server_bin),
            "localauthority",
            "x509",
            "show",
            "-socketPath",
            str(socket_path),
            "-output",
            "json",
        ).stdout
    )
    authority_id = (payload.get("active") or {}).get("authority_id")
    if not isinstance(authority_id, str) or not authority_id:
        raise AssertionError("could not resolve active SPIRE X.509 authority")
    return authority_id


def _show_bundle(server_bin: Path, socket_path: Path, target: Path) -> Path:
    target.write_text(
        _run(
            str(server_bin),
            "bundle",
            "show",
            "-socketPath",
            str(socket_path),
            "-format",
            "pem",
        ).stdout,
        encoding="utf-8",
    )
    return _require_file(target)


def _find_minted_svid(directory: Path) -> Path:
    matches: list[Path] = []
    for candidate in sorted(directory.glob("*.pem")):
        if _run("openssl", "x509", "-in", str(candidate), "-noout", check=False).returncode != 0:
            continue
        try:
            if _wire_identity(candidate) == WIRE_SPIFFE_ID:
                matches.append(candidate)
        except AssertionError:
            continue
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one minted workload SVID, got {len(matches)}")
    return matches[0]


def _mint_svid(server_bin: Path, socket_path: Path, output_dir: Path) -> Path:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    _run(
        str(server_bin),
        "x509",
        "mint",
        "-socketPath",
        str(socket_path),
        "-spiffeID",
        WIRE_SPIFFE_ID,
        "-ttl",
        "30s",
        "-write",
        str(output_dir),
    )
    return _find_minted_svid(output_dir)


def _sqlite_backup(source_db: Path, destination_db: Path) -> None:
    destination_db.parent.mkdir(parents=True, exist_ok=True)
    if destination_db.exists():
        destination_db.unlink()
    with sqlite3.connect(f"file:{source_db}?mode=ro", uri=True) as source:
        with sqlite3.connect(destination_db) as destination:
            source.backup(destination)
            integrity = destination.execute("PRAGMA integrity_check").fetchone()
            if integrity != ("ok",):
                raise AssertionError(f"SQLite snapshot integrity check failed: {integrity!r}")


def _snapshot_provider_state(source_data_dir: Path, snapshot_data_dir: Path) -> None:
    if snapshot_data_dir.exists():
        shutil.rmtree(snapshot_data_dir)
    snapshot_data_dir.mkdir(parents=True)
    source_db = _require_file(source_data_dir / "datastore.sqlite3")
    source_keys = _require_file(source_data_dir / "keys.json")
    _sqlite_backup(source_db, snapshot_data_dir / "datastore.sqlite3")
    shutil.copy2(source_keys, snapshot_data_dir / "keys.json")
    _require_file(snapshot_data_dir / "datastore.sqlite3")
    _require_file(snapshot_data_dir / "keys.json")


def _verify(cert: Path, bundle: Path) -> bool:
    return (
        _run(
            "openssl",
            "verify",
            "-no_check_time",
            "-CAfile",
            str(bundle),
            str(cert),
            check=False,
        ).returncode
        == 0
    )


def _connect_currentness(current_db: Path, fence_db: Path) -> sqlite3.Connection:
    current_db.parent.mkdir(parents=True, exist_ok=True)
    fence_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(current_db)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("ATTACH DATABASE ? AS fence", (str(fence_db),))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS authority_state ("
        "singleton INTEGER PRIMARY KEY CHECK (singleton = 1), "
        "fence_sequence INTEGER NOT NULL CHECK (fence_sequence > 0), "
        "bundle_generation TEXT NOT NULL, credential_generation TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS fence.recovery_fence ("
        "fence_sequence INTEGER PRIMARY KEY CHECK (fence_sequence > 0), "
        "bundle_generation TEXT NOT NULL, credential_generation TEXT NOT NULL)"
    )
    return conn


def _initialize_currentness(
    current_db: Path,
    fence_db: Path,
    *,
    bundle_generation: str,
    credential_generation: str,
) -> None:
    with _connect_currentness(current_db, fence_db) as conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT COUNT(*) FROM authority_state").fetchone() != (0,):
            raise AssertionError("platform currentness authority was unexpectedly pre-initialized")
        conn.execute(
            "INSERT INTO authority_state(singleton, fence_sequence, bundle_generation, credential_generation) "
            "VALUES (1, 1, ?, ?)",
            (bundle_generation, credential_generation),
        )
        conn.execute(
            "INSERT INTO fence.recovery_fence(fence_sequence, bundle_generation, credential_generation) "
            "VALUES (1, ?, ?)",
            (bundle_generation, credential_generation),
        )
        conn.commit()


def _read_currentness(current_db: Path) -> CurrentnessState:
    with sqlite3.connect(current_db) as conn:
        row = conn.execute(
            "SELECT fence_sequence, bundle_generation, credential_generation "
            "FROM authority_state WHERE singleton = 1"
        ).fetchone()
    if row is None:
        raise AdmissionDenied("platform workload currentness authority is unavailable")
    return CurrentnessState(int(row[0]), str(row[1]), str(row[2]))


def _read_latest_fence(fence_db: Path) -> CurrentnessState:
    if not fence_db.is_file():
        raise AdmissionDenied("recovery fence evidence is unavailable")
    with sqlite3.connect(fence_db) as conn:
        row = conn.execute(
            "SELECT fence_sequence, bundle_generation, credential_generation "
            "FROM recovery_fence ORDER BY fence_sequence DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise AdmissionDenied("recovery fence evidence is unavailable")
    return CurrentnessState(int(row[0]), str(row[1]), str(row[2]))


def _commit_successor_currentness(
    current_db: Path,
    fence_db: Path,
    *,
    expected: CurrentnessState,
    successor_bundle: str,
    successor_credential: str,
) -> CurrentnessState:
    successor = CurrentnessState(
        expected.fence_sequence + 1, successor_bundle, successor_credential
    )
    with _connect_currentness(current_db, fence_db) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT fence_sequence, bundle_generation, credential_generation "
            "FROM authority_state WHERE singleton = 1"
        ).fetchone()
        if row != (
            expected.fence_sequence,
            expected.bundle_generation,
            expected.credential_generation,
        ):
            raise AssertionError("platform currentness successor CAS lost authority")
        conn.execute(
            "INSERT INTO fence.recovery_fence(fence_sequence, bundle_generation, credential_generation) "
            "VALUES (?, ?, ?)",
            (
                successor.fence_sequence,
                successor.bundle_generation,
                successor.credential_generation,
            ),
        )
        conn.execute(
            "UPDATE authority_state SET fence_sequence = ?, bundle_generation = ?, credential_generation = ? "
            "WHERE singleton = 1",
            (
                successor.fence_sequence,
                successor.bundle_generation,
                successor.credential_generation,
            ),
        )
        conn.commit()
    return successor


def _reconcile_currentness(
    current_db: Path,
    fence_db: Path,
    *,
    expected_recovery_fence: int,
) -> CurrentnessState:
    """Reconcile restored currentness through the accepted (R,F] recovery fence."""
    surviving = _read_latest_fence(fence_db)
    if surviving.fence_sequence < expected_recovery_fence:
        raise AdmissionDenied("recovery fence evidence is incomplete; workload admission remains quarantined")
    if surviving.fence_sequence != expected_recovery_fence:
        raise AdmissionDenied("recovery fence head is ambiguous; workload admission remains quarantined")

    with _connect_currentness(current_db, fence_db) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT fence_sequence, bundle_generation, credential_generation "
            "FROM authority_state WHERE singleton = 1"
        ).fetchone()
        if row is None:
            raise AdmissionDenied("restored workload currentness authority is missing")
        current = CurrentnessState(int(row[0]), str(row[1]), str(row[2]))
        if current.fence_sequence > surviving.fence_sequence:
            raise AdmissionDenied("restored currentness is ahead of validated recovery fence")
        if current.fence_sequence < surviving.fence_sequence:
            conn.execute(
                "UPDATE authority_state SET fence_sequence = ?, bundle_generation = ?, credential_generation = ? "
                "WHERE singleton = 1",
                (
                    surviving.fence_sequence,
                    surviving.bundle_generation,
                    surviving.credential_generation,
                ),
            )
        elif (
            current.bundle_generation != surviving.bundle_generation
            or current.credential_generation != surviving.credential_generation
        ):
            raise AdmissionDenied("restored currentness conflicts with recovery fence evidence")
        conn.commit()
    reconciled = _read_currentness(current_db)
    if reconciled != surviving:
        raise AdmissionDenied("workload currentness reconciliation did not reach recovery fence")
    return reconciled


def main() -> int:
    root_raw = os.environ.get("SPIRE_ROTATION_EVIDENCE_DIR")
    spire_root_raw = os.environ.get("SPIRE_ROOT")
    if not root_raw:
        raise SystemExit("SPIRE_ROTATION_EVIDENCE_DIR is required")
    if not spire_root_raw:
        raise SystemExit("SPIRE_ROOT is required")
    root = Path(root_raw).resolve()
    spire_root = Path(spire_root_raw).resolve()
    server_bin = _require_file(spire_root / "bin" / "spire-server")
    if not os.access(server_bin, os.X_OK):
        raise SystemExit(f"SPIRE server binary is not executable: {server_bin}")
    if not root.is_dir():
        raise SystemExit(f"SPIRE rotation evidence directory does not exist: {root}")

    work = root / "actual-provider-restore"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    live_data = work / "live-data"
    live_data.mkdir()
    live_socket = work / "live-server.sock"
    live_config = work / "live-server.conf"
    live_log = work / "live-server.log"
    _write_server_config(path=live_config, data_dir=live_data, socket_path=live_socket, port=18083)

    currentness_dir = work / "platform-currentness"
    current_db = currentness_dir / "current.sqlite3"
    fence_db = currentness_dir / "surviving-recovery-fence.sqlite3"
    current_snapshot = work / "snapshot" / "platform-current.sqlite3"
    fence_snapshot_at_r = work / "snapshot" / "recovery-fence-at-r.sqlite3"

    live_process: subprocess.Popen[str] | None = None
    live_log_handle: object | None = None
    restored_process: subprocess.Popen[str] | None = None
    restored_log_handle: object | None = None
    try:
        live_process, live_log_handle = _start_server(
            server_bin=server_bin,
            config=live_config,
            socket_path=live_socket,
            log_path=live_log,
        )
        retired_authority_id = _show_active_authority(server_bin, live_socket)
        pre_bundle = _show_bundle(server_bin, live_socket, work / "pre-rotation-bundle.pem")
        pre_svid = _mint_svid(server_bin, live_socket, work / "pre-rotation-svid")
        if not _verify(pre_svid, pre_bundle):
            raise AssertionError("pre-rotation provider cannot validate its own SVID")

        pre_state = CurrentnessState(
            1,
            _digest_id("bundle", pre_bundle),
            _credential_generation(retired_authority_id),
        )
        _initialize_currentness(
            current_db,
            fence_db,
            bundle_generation=pre_state.bundle_generation,
            credential_generation=pre_state.credential_generation,
        )

        snapshot_data = work / "snapshot" / "server-data"
        _snapshot_provider_state(live_data, snapshot_data)
        _sqlite_backup(current_db, current_snapshot)
        _sqlite_backup(fence_db, fence_snapshot_at_r)

        prepared = json.loads(
            _run(
                str(server_bin),
                "localauthority",
                "x509",
                "prepare",
                "-socketPath",
                str(live_socket),
                "-output",
                "json",
            ).stdout
        )
        successor_authority_id = (prepared.get("prepared_authority") or {}).get("authority_id")
        if not isinstance(successor_authority_id, str) or not successor_authority_id:
            raise AssertionError("SPIRE restore probe did not prepare a successor authority")
        if successor_authority_id == retired_authority_id:
            raise AssertionError("SPIRE restore probe reused the retired authority identifier")
        _run(
            str(server_bin),
            "localauthority",
            "x509",
            "activate",
            "-socketPath",
            str(live_socket),
            "-authorityID",
            successor_authority_id,
            "-output",
            "json",
        )
        _run(
            str(server_bin),
            "localauthority",
            "x509",
            "taint",
            "-socketPath",
            str(live_socket),
            "-authorityID",
            retired_authority_id,
            "-output",
            "json",
        )
        _run(
            str(server_bin),
            "localauthority",
            "x509",
            "revoke",
            "-socketPath",
            str(live_socket),
            "-authorityID",
            retired_authority_id,
            "-output",
            "json",
        )
        if _show_active_authority(server_bin, live_socket) != successor_authority_id:
            raise AssertionError("post-revocation provider authority did not remain on successor")
        current_bundle = _show_bundle(server_bin, live_socket, work / "post-revoke-current-bundle.pem")
        current_svid = _mint_svid(server_bin, live_socket, work / "post-revoke-current-svid")
        if not _verify(current_svid, current_bundle):
            raise AssertionError("post-revocation provider cannot validate current SVID")
        if _verify(pre_svid, current_bundle):
            raise AssertionError("retired pre-rotation SVID still validates under current bundle")

        committed_state = _commit_successor_currentness(
            current_db,
            fence_db,
            expected=pre_state,
            successor_bundle=_digest_id("bundle", current_bundle),
            successor_credential=_credential_generation(successor_authority_id),
        )
        if _read_latest_fence(fence_db) != committed_state:
            raise AssertionError("surviving recovery fence did not durably record successor currentness")

        _stop_server(live_process, live_log_handle)
        live_process = None
        live_log_handle = None

        # Restore at R both SPIRE and the primary platform currentness store. The
        # independently durable (R,F] fence ledger is deliberately not restored.
        shutil.copy2(current_snapshot, current_db)
        rolled_back_state = _read_currentness(current_db)
        if rolled_back_state != pre_state:
            raise AssertionError("platform currentness store did not actually roll back to R")
        if _read_latest_fence(fence_db) != committed_state:
            raise AssertionError("post-R recovery fence did not survive currentness-store restore")

        restored_data = work / "restored-data"
        shutil.copytree(snapshot_data, restored_data)
        restored_socket = work / "restored-server.sock"
        restored_config = work / "restored-server.conf"
        restored_log = work / "restored-server.log"
        _write_server_config(
            path=restored_config,
            data_dir=restored_data,
            socket_path=restored_socket,
            port=18084,
        )
        restored_process, restored_log_handle = _start_server(
            server_bin=server_bin,
            config=restored_config,
            socket_path=restored_socket,
            log_path=restored_log,
        )
        restored_authority_id = _show_active_authority(server_bin, restored_socket)
        if restored_authority_id != retired_authority_id:
            raise AssertionError(
                "actual provider restore did not reactivate snapshotted retired authority: "
                f"expected={retired_authority_id!r} actual={restored_authority_id!r}"
            )
        restored_bundle = _show_bundle(server_bin, restored_socket, work / "actual-restored-bundle.pem")
        restored_svid = _mint_svid(server_bin, restored_socket, work / "actual-restored-svid")
        if not _verify(restored_svid, restored_bundle):
            raise AssertionError("restored provider cannot validate its newly minted restored SVID")
        if _certificate_fingerprint(restored_bundle) != _certificate_fingerprint(pre_bundle):
            raise AssertionError("restored bundle does not match snapshotted retired authority")
        if _verify(current_svid, restored_bundle):
            raise AssertionError("current successor SVID validates under restored retired bundle")

        _stop_server(restored_process, restored_log_handle)
        restored_process = None
        restored_log_handle = None

        restored_peer = _peer(
            cert=restored_svid,
            bundle_generation=_digest_id("bundle", restored_bundle),
            credential_generation=_credential_generation(restored_authority_id),
        )
        restored_now = _openssl_date(restored_svid, "-startdate") + timedelta(seconds=1)

        # Non-vacuous rollback control: before (R,F] reconciliation, the rolled-back
        # platform currentness store really would accept the resurrected issuer.
        rolled_back_principal = _admit(
            restored_peer,
            current_bundle=rolled_back_state.bundle_generation,
            current_credential=rolled_back_state.credential_generation,
            now=restored_now,
        )
        if rolled_back_principal.principal_id != CANONICAL_SPIFFE_ID:
            raise AssertionError("rolled-back positive control changed canonical workload identity")

        # Incomplete (R,F] evidence is quarantine, never permission to use restored state.
        incomplete_current = work / "incomplete-recovery-current.sqlite3"
        incomplete_fence = work / "incomplete-recovery-fence.sqlite3"
        shutil.copy2(current_snapshot, incomplete_current)
        shutil.copy2(fence_snapshot_at_r, incomplete_fence)
        _expect_denied(
            "incomplete_recovery_fence",
            "recovery fence evidence is incomplete",
            lambda: _reconcile_currentness(
                incomplete_current,
                incomplete_fence,
                expected_recovery_fence=committed_state.fence_sequence,
            ),
        )

        reconciled = _reconcile_currentness(
            current_db,
            fence_db,
            expected_recovery_fence=committed_state.fence_sequence,
        )
        if reconciled != committed_state:
            raise AssertionError("(R,F] reconciliation did not restore successor currentness")

        current_peer = _peer(
            cert=current_svid,
            bundle_generation=reconciled.bundle_generation,
            credential_generation=reconciled.credential_generation,
        )
        current_now = _openssl_date(current_svid, "-startdate") + timedelta(seconds=1)
        principal = _admit(
            current_peer,
            current_bundle=reconciled.bundle_generation,
            current_credential=reconciled.credential_generation,
            now=current_now,
        )
        if principal.kind is not PrincipalKind.INTERNAL_SERVICE_PRINCIPAL:
            raise AssertionError("current SPIRE positive control changed principal class")
        if principal.principal_id != CANONICAL_SPIFFE_ID:
            raise AssertionError("current SPIRE positive control changed canonical identity")

        _expect_denied(
            "restored_provider_after_reconciliation",
            "trust-bundle generation is stale",
            lambda: _admit(
                restored_peer,
                current_bundle=reconciled.bundle_generation,
                current_credential=reconciled.credential_generation,
                now=restored_now,
            ),
        )
        stale_credential_peer = _peer(
            cert=restored_svid,
            bundle_generation=reconciled.bundle_generation,
            credential_generation=_credential_generation(restored_authority_id),
        )
        _expect_denied(
            "restored_provider_credential_generation",
            "workload credential generation is stale",
            lambda: _admit(
                stale_credential_peer,
                current_bundle=reconciled.bundle_generation,
                current_credential=reconciled.credential_generation,
                now=restored_now,
            ),
        )

        print(
            "issuer_restore_retired_authority_nonresurrection=PASS "
            f"wire_spiffe_id={WIRE_SPIFFE_ID} canonical_principal={CANONICAL_SPIFFE_ID} "
            f"retired_authority_id={retired_authority_id} successor_authority_id={successor_authority_id} "
            f"restored_bundle_fingerprint={_fingerprint(restored_bundle)} "
            f"current_bundle_fingerprint={_fingerprint(current_bundle)} "
            "actual_provider_restore_exercised=true sqlite_snapshot_consistent=true "
            "provider_key_state_restored=true restored_retired_authority_reactivated=true "
            "restored_issuer_minted_fresh_svid=true platform_currentness_store_rolled_back=true "
            "pre_reconcile_restored_authority_self_admits=true recovery_fence_survived_restore=true "
            "incomplete_recovery_fence_fail_closed=true recovery_interval_r_f_reconciled=true "
            "currentness_loaded_from_durable_recovery_authority=true "
            "currentness_not_derived_from_restored_spire=true restored_bundle_generation_denied=true "
            "restored_credential_generation_denied=true"
        )
        print(
            "conformance_claim=exploratory_only evidence_credited=false ledger_change=false "
            "restore_object_not_current_authority=true wave4=not_granted production=none "
            "d4=not_selected_not_granted"
        )
        return 0
    finally:
        _stop_server(restored_process, restored_log_handle)
        _stop_server(live_process, live_log_handle)


if __name__ == "__main__":
    raise SystemExit(main())
