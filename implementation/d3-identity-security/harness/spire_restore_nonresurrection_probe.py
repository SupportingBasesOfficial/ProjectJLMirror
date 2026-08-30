#!/usr/bin/env python3
from __future__ import annotations

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


def _run(*args: str, check: bool = True, timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )


def _openssl_date(cert: Path, option: str) -> datetime:
    output = _run("openssl", "x509", "-in", str(cert), "-noout", option).stdout.strip()
    _, value = output.split("=", 1)
    parsed = datetime.strptime(value, "%b %d %H:%M:%S %Y %Z")
    return parsed.replace(tzinfo=timezone.utc)


def _digest_id(prefix: str, path: Path) -> str:
    return f"{prefix}:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _certificate_fingerprint(path: Path) -> str:
    output = _run(
        "openssl",
        "x509",
        "-in",
        str(path),
        "-noout",
        "-fingerprint",
        "-sha256",
    ).stdout.strip()
    _, value = output.split("=", 1)
    return value.replace(":", "").lower()


def _require_file(path: Path) -> Path:
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"required SPIRE restore evidence is missing or empty: {path}")
    return path


def _wire_identity(cert: Path) -> str:
    output = _run(
        "openssl",
        "x509",
        "-in",
        str(cert),
        "-noout",
        "-ext",
        "subjectAltName",
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


def _peer(
    *,
    cert: Path,
    bundle_generation: str,
    credential_generation: str,
) -> VerifiedWorkloadPeer:
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


def _write_server_config(
    *,
    path: Path,
    data_dir: Path,
    socket_path: Path,
    port: int,
) -> None:
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
    *,
    server_bin: Path,
    config: Path,
    socket_path: Path,
    log_path: Path,
) -> tuple[subprocess.Popen[str], object]:
    _run(str(server_bin), "validate", "-config", str(config))
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [str(server_bin), "run", "-config", str(config)],
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    for _ in range(100):
        if process.poll() is not None:
            log_handle.flush()
            raise AssertionError(
                "restored SPIRE server exited before readiness: "
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
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    log_handle.flush()
    log_handle.close()
    raise AssertionError(
        "restored SPIRE server did not become ready: "
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
    if log_handle is not None:
        log_handle.close()


def _show_active_authority(server_bin: Path, socket_path: Path) -> str:
    output = _run(
        str(server_bin),
        "localauthority",
        "x509",
        "show",
        "-socketPath",
        str(socket_path),
        "-output",
        "json",
    ).stdout
    payload = json.loads(output)
    authority_id = (payload.get("active") or {}).get("authority_id")
    if not isinstance(authority_id, str) or not authority_id:
        raise AssertionError("SPIRE restore probe could not resolve active X.509 authority")
    return authority_id


def _show_bundle(server_bin: Path, socket_path: Path, target: Path) -> Path:
    output = _run(
        str(server_bin),
        "bundle",
        "show",
        "-socketPath",
        str(socket_path),
        "-format",
        "pem",
    ).stdout
    target.write_text(output, encoding="utf-8")
    return _require_file(target)


def _find_minted_svid(directory: Path) -> Path:
    matches: list[Path] = []
    for candidate in sorted(directory.glob("*.pem")):
        parsed = _run(
            "openssl",
            "x509",
            "-in",
            str(candidate),
            "-noout",
            check=False,
        )
        if parsed.returncode != 0:
            continue
        try:
            identity = _wire_identity(candidate)
        except AssertionError:
            continue
        if identity == WIRE_SPIFFE_ID:
            matches.append(candidate)
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
        "30",
        "-write",
        str(output_dir),
    )
    return _find_minted_svid(output_dir)


def _snapshot_provider_state(source_data_dir: Path, snapshot_data_dir: Path) -> None:
    if snapshot_data_dir.exists():
        shutil.rmtree(snapshot_data_dir)
    snapshot_data_dir.mkdir(parents=True)
    source_db = _require_file(source_data_dir / "datastore.sqlite3")
    source_keys = _require_file(source_data_dir / "keys.json")
    destination_db = snapshot_data_dir / "datastore.sqlite3"
    with sqlite3.connect(f"file:{source_db}?mode=ro", uri=True) as source:
        with sqlite3.connect(destination_db) as destination:
            source.backup(destination)
            destination.execute("PRAGMA integrity_check")
    shutil.copy2(source_keys, snapshot_data_dir / "keys.json")
    _require_file(destination_db)
    _require_file(snapshot_data_dir / "keys.json")


def _verify(cert: Path, bundle: Path) -> bool:
    result = _run(
        "openssl",
        "verify",
        "-no_check_time",
        "-CAfile",
        str(bundle),
        str(cert),
        check=False,
    )
    return result.returncode == 0


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
    _write_server_config(
        path=live_config,
        data_dir=live_data,
        socket_path=live_socket,
        port=18083,
    )

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
        pre_restore_bundle = _show_bundle(server_bin, live_socket, work / "pre-restore-bundle.pem")
        pre_restore_svid = _mint_svid(server_bin, live_socket, work / "pre-restore-svid")
        if not _verify(pre_restore_svid, pre_restore_bundle):
            raise AssertionError("pre-rotation provider state cannot validate its own SVID")

        snapshot_data = work / "snapshot" / "server-data"
        _snapshot_provider_state(live_data, snapshot_data)

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
        current_authority_id = _show_active_authority(server_bin, live_socket)
        if current_authority_id != successor_authority_id:
            raise AssertionError("post-revocation provider authority did not remain on the successor")
        current_bundle = _show_bundle(server_bin, live_socket, work / "post-revoke-current-bundle.pem")
        current_svid = _mint_svid(server_bin, live_socket, work / "post-revoke-current-svid")
        if not _verify(current_svid, current_bundle):
            raise AssertionError("post-revocation current provider state cannot validate its own SVID")
        if _verify(pre_restore_svid, current_bundle):
            raise AssertionError("retired pre-snapshot SVID still validates after provider authority revocation")

        _stop_server(live_process, live_log_handle)
        live_process = None
        live_log_handle = None

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
                "actual provider restore did not reactivate the snapshotted retired authority: "
                f"expected={retired_authority_id!r} actual={restored_authority_id!r}"
            )
        restored_bundle = _show_bundle(server_bin, restored_socket, work / "actual-restored-bundle.pem")
        restored_svid = _mint_svid(server_bin, restored_socket, work / "actual-restored-svid")
        if not _verify(restored_svid, restored_bundle):
            raise AssertionError("actual restored provider cannot validate its newly minted restored SVID")
        if _certificate_fingerprint(restored_bundle) != _certificate_fingerprint(pre_restore_bundle):
            raise AssertionError("restored provider bundle does not match the snapshotted retired authority")
        if _verify(current_svid, restored_bundle):
            raise AssertionError("post-revocation current SVID unexpectedly validates under restored retired bundle")

        _stop_server(restored_process, restored_log_handle)
        restored_process = None
        restored_log_handle = None

        _wire_identity(current_svid)
        _wire_identity(restored_svid)
        current_bundle_generation = _digest_id("bundle", current_bundle)
        current_credential_generation = _digest_id("svid", current_svid)
        restored_bundle_generation = _digest_id("bundle", restored_bundle)
        restored_credential_generation = _digest_id("svid", restored_svid)
        if current_bundle_generation == restored_bundle_generation:
            raise AssertionError("actual restored bundle generation collapsed into post-revocation current state")
        if current_credential_generation == restored_credential_generation:
            raise AssertionError("actual restored credential generation collapsed into post-revocation current state")

        current_peer = _peer(
            cert=current_svid,
            bundle_generation=current_bundle_generation,
            credential_generation=current_credential_generation,
        )
        current_now = _openssl_date(current_svid, "-startdate") + timedelta(seconds=1)
        principal = _admit(
            current_peer,
            current_bundle=current_bundle_generation,
            current_credential=current_credential_generation,
            now=current_now,
        )
        if principal.kind is not PrincipalKind.INTERNAL_SERVICE_PRINCIPAL:
            raise AssertionError("post-revocation current SPIRE positive control changed principal class")
        if principal.principal_id != CANONICAL_SPIFFE_ID:
            raise AssertionError("post-revocation current SPIRE positive control changed canonical identity")

        restored_peer = _peer(
            cert=restored_svid,
            bundle_generation=restored_bundle_generation,
            credential_generation=restored_credential_generation,
        )
        restored_now = _openssl_date(restored_svid, "-startdate") + timedelta(seconds=1)

        # Non-vacuous restore control: if the platform incorrectly adopts the restored
        # provider generations as current, the restored issuer is fully usable again.
        restored_self_principal = _admit(
            restored_peer,
            current_bundle=restored_bundle_generation,
            current_credential=restored_credential_generation,
            now=restored_now,
        )
        if restored_self_principal.principal_id != CANONICAL_SPIFFE_ID:
            raise AssertionError("restored provider positive control changed canonical workload identity")

        # Actual currentness fence: the restored provider state cannot overwrite the
        # post-revocation bundle/credential generations merely because the restore works.
        _expect_denied(
            "actual_restored_provider_bundle",
            "trust-bundle generation is stale",
            lambda: _admit(
                restored_peer,
                current_bundle=current_bundle_generation,
                current_credential=current_credential_generation,
                now=restored_now,
            ),
        )

        # Independent credential fence: even if the restored bundle were accidentally
        # relabelled as current, its restored SVID generation remains retired.
        stale_credential_peer = _peer(
            cert=restored_svid,
            bundle_generation=current_bundle_generation,
            credential_generation=restored_credential_generation,
        )
        _expect_denied(
            "actual_restored_provider_credential_generation",
            "workload credential generation is stale",
            lambda: _admit(
                stale_credential_peer,
                current_bundle=current_bundle_generation,
                current_credential=current_credential_generation,
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
            "restored_issuer_minted_fresh_svid=true restored_state_self_admits=true "
            "retired_under_post_rotation_bundle=true restored_bundle_generation_denied=true "
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
