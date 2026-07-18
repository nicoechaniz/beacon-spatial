"""Golden, OSC round-trip, and source-coverage tests for Beacon Spatial."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import contract_codec


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "beacon_spatial.contract.json"
GOLDEN_PATH = REPO_ROOT / "beacon_spatial.contract_id.golden"
ENGINE_PATH = REPO_ROOT / "beacon.scd"
UPSTREAM_CODEC_PATH = (
    REPO_ROOT.parent
    / "harmonic-weaver"
    / "src"
    / "harmonic_weaver"
    / "contract_codec.py"
)


def _expand_pattern(pattern: str, parameters: dict) -> set[str]:
    """Expand the contract's bounded integer path placeholders."""

    addresses = {pattern}
    for name, definition in parameters.items():
        low, high = definition["bounds"]
        placeholder = "{" + name + "}"
        addresses = {
            address.replace(placeholder, str(value))
            for address in addresses
            for value in range(low, high + 1)
        }
    return addresses


def _native_manifest_addresses(manifest: dict) -> set[str]:
    """Return the original engine surface (capabilities plus commands)."""

    addresses: set[str] = set()
    for entry in manifest["capabilities"] + manifest["commands"]:
        addresses.update(
            _expand_pattern(entry["address_pattern"], entry["parameters"])
        )
    return addresses


def _incoming_manifest_addresses(manifest: dict) -> set[str]:
    """Return every address for which beacon.scd installs an OSCdef."""

    return _native_manifest_addresses(manifest) | {
        manifest["handshake"]["hello_request_address"],
        manifest["state_sync"]["request_address"],
    }


def _oscdef_blocks(source: str) -> list[str]:
    """Extract balanced OSCdef(...) calls from straightforward sclang source."""

    blocks: list[str] = []
    current: list[str] = []
    depth = 0
    collecting = False
    for line in source.splitlines():
        if not collecting and "OSCdef(" in line and not line.lstrip().startswith("//"):
            collecting = True
            current = []
            depth = 0
        if collecting:
            current.append(line)
            depth += line.count("(") - line.count(")")
            if depth == 0:
                blocks.append("\n".join(current))
                collecting = False
    if collecting:
        raise AssertionError("unterminated OSCdef call in beacon.scd")
    return blocks


def _oscdef_patterns(source: str) -> list[str]:
    """Extract literal or indexed address patterns from all OSCdef calls."""

    patterns: list[str] = []
    for block in _oscdef_blocks(source):
        paths = re.findall(r"['\"](/beacon/[a-z0-9_/]+)['\"]", block)
        if not paths:
            raise AssertionError(f"OSCdef has no /beacon address:\n{block}")
        path = paths[-1]
        if path.endswith("/") and re.search(
            rf"{re.escape(path)}['\"]\s*\+\+\s*n\b", block
        ):
            path += "{N}"
        patterns.append(path)
    return patterns


def _source_oscdef_addresses(manifest: dict, source: str) -> set[str]:
    bounds_by_pattern = {
        entry["address_pattern"]: entry["parameters"]
        for entry in manifest["capabilities"] + manifest["commands"]
    }
    addresses: set[str] = set()
    for pattern in _oscdef_patterns(source):
        parameters = bounds_by_pattern.get(pattern, {})
        addresses.update(_expand_pattern(pattern, parameters))
    return addresses


def test_manifest_validates_and_matches_golden_sidecar() -> None:
    manifest = contract_codec.load_manifest(MANIFEST_PATH)
    assert contract_codec.validate_manifest(manifest) is manifest
    assert contract_codec.check_golden_sidecar(manifest, GOLDEN_PATH) == (
        GOLDEN_PATH.read_text(encoding="ascii").strip()
    )
    assert "voice_model_alias" not in manifest

    engine_contract_id = re.search(
        r'var contractId = "([0-9a-f]{32})";',
        ENGINE_PATH.read_text(encoding="utf-8"),
    )
    assert engine_contract_id is not None
    assert engine_contract_id.group(1) == GOLDEN_PATH.read_text(
        encoding="ascii"
    ).strip()


def test_copied_codec_is_byte_identical_to_ecosystem_codec() -> None:
    assert (REPO_ROOT / "contract_codec.py").read_bytes() == (
        UPSTREAM_CODEC_PATH.read_bytes()
    )


def test_native_address_table_formalizes_all_69_existing_addresses() -> None:
    manifest = contract_codec.load_manifest(MANIFEST_PATH)
    native_addresses = _native_manifest_addresses(manifest)

    assert len(native_addresses) == 69
    assert len([address for address in native_addresses if "/gain/" in address]) == 13
    assert len([address for address in native_addresses if "/az/" in address]) == 13
    assert len([address for address in native_addresses if "/dist/" in address]) == 13
    assert len([address for address in native_addresses if "/solo/" in address]) == 13
    assert len([address for address in native_addresses if "/q/" in address]) == 12
    assert {entry["address_pattern"] for entry in manifest["commands"]} == {
        "/beacon/record/start",
        "/beacon/record/stop",
        "/beacon/reset",
    }
    assert next(
        command
        for command in manifest["commands"]
        if command["address_pattern"] == "/beacon/record/stop"
    )["arguments"] == []
    assert next(
        command
        for command in manifest["commands"]
        if command["address_pattern"] == "/beacon/reset"
    )["arguments"] == []


def test_simulated_atomic_state_dump_round_trips_through_stdlib_codec() -> None:
    manifest = contract_codec.load_manifest(MANIFEST_PATH)
    contract_id = contract_codec.check_golden_sidecar(manifest, GOLDEN_PATH)
    stream_id = "0123456789abcdef"
    state_seq = 42

    readable_messages: list[bytes] = []
    readable_addresses: list[str] = []
    for capability in manifest["capabilities"]:
        if not capability["read"]:
            continue
        argument = capability["arguments"][0]
        low, high = argument["range"]
        value = float(low + (high - low) / 2)
        for address in sorted(
            _expand_pattern(
                capability["address_pattern"], capability["parameters"]
            )
        ):
            readable_addresses.append(address)
            readable_messages.append(contract_codec.encode_message(address, [value]))

    assert len(readable_messages) == 66
    members = [
        contract_codec.encode_message(
            "/beacon/state/begin",
            [stream_id, ("h", state_seq), contract_id],
        ),
        *readable_messages,
        contract_codec.encode_message(
            "/beacon/state/end", [stream_id, ("h", state_seq)]
        ),
    ]
    packet = contract_codec.encode_bundle(members)
    decoded = contract_codec.decode_bundle(packet)

    assert len(packet) <= manifest["transport"]["max_datagram_bytes"]
    assert decoded[0] == (
        "/beacon/state/begin",
        [stream_id, state_seq, contract_id],
    )
    assert [address for address, _args in decoded[1:-1]] == readable_addresses
    assert decoded[-1] == (
        "/beacon/state/end",
        [stream_id, state_seq],
    )
    for (_address, args), capability_address in zip(
        decoded[1:-1], readable_addresses, strict=True
    ):
        assert capability_address.startswith("/beacon/")
        assert len(args) == 1
        assert isinstance(args[0], float)


def test_manifest_covers_every_oscdef_in_beacon_scd() -> None:
    manifest = contract_codec.load_manifest(MANIFEST_PATH)
    source = ENGINE_PATH.read_text(encoding="utf-8")
    source_addresses = _source_oscdef_addresses(manifest, source)
    manifest_addresses = _incoming_manifest_addresses(manifest)

    assert source_addresses == manifest_addresses, (
        f"missing from manifest: {sorted(source_addresses - manifest_addresses)}; "
        f"not implemented by OSCdef: {sorted(manifest_addresses - source_addresses)}"
    )
    assert len(source_addresses) == 71


def test_invalid_golden_id_is_rejected() -> None:
    manifest = contract_codec.load_manifest(MANIFEST_PATH)
    with pytest.raises(contract_codec.ContractIdMismatch):
        contract_codec.verify_contract_id(manifest, "0" * 32)
