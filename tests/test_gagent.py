from io import BytesIO
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "maxspect_syna_g_local"))

from gagent import (  # noqa: E402
    CMD_P0,
    Frame,
    build_frame,
    decode_varint,
    encode_varint,
    read_frame,
    status_request_payload,
)


def test_varint_single_and_multi_byte():
    assert encode_varint(5) == b"\x05"
    assert encode_varint(578) == bytes.fromhex("c204")
    assert decode_varint(BytesIO(bytes.fromhex("c204"))) == 578


def test_build_and_read_frame_roundtrip():
    raw = build_frame(CMD_P0, bytes.fromhex("0000000312ffffff"))
    frame = read_frame(BytesIO(raw))
    assert frame == Frame(flag=0, command=CMD_P0, payload=bytes.fromhex("0000000312ffffff"))


def test_status_request_payload():
    assert status_request_payload(3).hex() == "0000000312ffffff"
