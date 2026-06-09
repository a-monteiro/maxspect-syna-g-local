from io import BytesIO
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "maxspect_syna_g_local"))

from gagent import (  # noqa: E402
    CMD_P0,
    Frame,
    build_control_payload,
    control,
    build_frame,
    decode_maxspect_status_payload,
    decode_other_block,
    decode_schedule,
    decode_varint,
    encode_varint,
    infer_lighting_phase,
    probe,
    read_frame,
    status_request_payload,
)

LIVE_STATUS_FRAME_HEX = (
    "00000003c2040000940000000313ffffff0001414141000500003706010a00000000000000020b00323232000300030c0041414100050004120041414100050005130032323200030006140000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001a06080c1c001900026464641e1e1e000100000000000000000005050000000c000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000004d4a2d4c31423030313334390000000000000000000000000000000000"
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


def test_decode_full_status_payload_from_live_frame():
    frame = read_frame(BytesIO(bytes.fromhex(LIVE_STATUS_FRAME_HEX)))
    decoded = decode_maxspect_status_payload(frame.payload)
    assert decoded is not None
    assert decoded["MODE"] == 1
    assert decoded["channel_1"] == 65
    assert decoded["channel_5"] == 5
    assert decoded["serial_number"] == "MJ-L1B001349"
    assert decoded["time_hex"] == "1a06080c1c00"
    assert decoded["device_time"] == "2026-06-08 12:28:00"
    assert decoded["temperature_alert"] is False
    assert decoded["password_configured"] is False
    assert "password" not in decoded


def test_decode_schedule_points_from_auto_block():
    frame = read_frame(BytesIO(bytes.fromhex(LIVE_STATUS_FRAME_HEX)))
    decoded = decode_maxspect_status_payload(frame.payload)
    points = decode_schedule(bytes.fromhex(decoded["auto"]))
    assert points == [
        {"time": "10:00", "channel_1": 0, "channel_2": 0, "channel_3": 0, "channel_4": 0, "channel_5": 0, "channel_6": 0},
        {"time": "11:00", "channel_1": 50, "channel_2": 50, "channel_3": 50, "channel_4": 0, "channel_5": 3, "channel_6": 0},
        {"time": "12:00", "channel_1": 65, "channel_2": 65, "channel_3": 65, "channel_4": 0, "channel_5": 5, "channel_6": 0},
        {"time": "18:00", "channel_1": 65, "channel_2": 65, "channel_3": 65, "channel_4": 0, "channel_5": 5, "channel_6": 0},
        {"time": "19:00", "channel_1": 50, "channel_2": 50, "channel_3": 50, "channel_4": 0, "channel_5": 3, "channel_6": 0},
        {"time": "20:00", "channel_1": 0, "channel_2": 0, "channel_3": 0, "channel_4": 0, "channel_5": 0, "channel_6": 0},
    ]


def test_build_control_payload_uses_full_attribute_lsb_bitmap_and_compact_values():
    frame = read_frame(BytesIO(bytes.fromhex(LIVE_STATUS_FRAME_HEX)))
    decoded = decode_maxspect_status_payload(frame.payload)
    assert build_control_payload(decoded, {"MODE": 1}, serial=4).hex() == "000000041100000401"
    assert build_control_payload(
        decoded,
        {"channel_1": 0, "channel_2": 0, "channel_3": 0, "channel_4": 0, "channel_5": 0, "channel_6": 0},
        serial=4,
    ).hex() == "00000004110001f8000000000000"


def test_build_control_payload_orders_values_by_schema_not_input_order():
    frame = read_frame(BytesIO(bytes.fromhex(LIVE_STATUS_FRAME_HEX)))
    decoded = decode_maxspect_status_payload(frame.payload)
    payload = build_control_payload(decoded, {"channel_6": 6, "MODE": 1, "channel_1": 10}, serial=4)
    assert payload.hex() == "000000041100010c010a06"


def test_infer_lighting_phase_reports_auto_daylight_for_noon_fixture():
    frame = read_frame(BytesIO(bytes.fromhex(LIVE_STATUS_FRAME_HEX)))
    decoded = decode_maxspect_status_payload(frame.payload)
    assert infer_lighting_phase(decoded) == "auto_daylight"


def test_infer_lighting_phase_reports_lunar_after_last_zero_schedule_point():
    frame = read_frame(BytesIO(bytes.fromhex(LIVE_STATUS_FRAME_HEX)))
    decoded = decode_maxspect_status_payload(frame.payload)
    decoded = {**decoded, "device_time": "2026-06-09 22:00:00"}
    assert infer_lighting_phase(decoded) == "auto_lunar"


def test_decode_full_status_payload_includes_lighting_phase():
    frame = read_frame(BytesIO(bytes.fromhex(LIVE_STATUS_FRAME_HEX)))
    decoded = decode_maxspect_status_payload(frame.payload)
    assert decoded["lighting_phase"] == "auto_daylight"


def test_decode_other_block_extracts_probable_lunar_extension_fields():
    frame = read_frame(BytesIO(bytes.fromhex(LIVE_STATUS_FRAME_HEX)))
    decoded = decode_maxspect_status_payload(frame.payload)
    other = decode_other_block(bytes.fromhex(decoded["other"]))
    assert other == {
        "extension_length": 25,
        "extension_type": 0,
        "lunar_profile": 2,
        "lunar_high_channels": [100, 100, 100],
        "lunar_low_channels": [30, 30, 30],
        "lunar_enabled": True,
        "lunar_cycle_day": 12,
    }


def test_decode_full_status_payload_includes_probable_lunar_cycle_day():
    frame = read_frame(BytesIO(bytes.fromhex(LIVE_STATUS_FRAME_HEX)))
    decoded = decode_maxspect_status_payload(frame.payload)
    assert decoded["lunar_cycle_day"] == 12
    assert decoded["lunar_enabled"] is True
