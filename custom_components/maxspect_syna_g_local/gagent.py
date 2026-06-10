"""Gizwits/GAgent local protocol helpers for Maxspect Syna-G devices.

The helpers in this module avoid Home Assistant imports so they can be tested
and used by the standalone probe script.
"""

from __future__ import annotations

import dataclasses
import socket
import time
from math import ceil
from typing import Any, BinaryIO

MAGIC = b"\x00\x00\x00\x03"
CMD_HANDSHAKE = 0x0006
CMD_HANDSHAKE_REPLY = 0x0007
CMD_AUTH = 0x0008
CMD_AUTH_REPLY = 0x0009
CMD_P0 = 0x0093
CMD_P0_REPLY = 0x0094

P0_READ_STATUS = 0x12
P0_READ_STATUS_ACK = 0x13
P0_CONTROL = 0x11

# APK-derived getDeviceStatus payload for a 17-attribute schema:
# SN(4-byte BE) + P0 read cmd 0x12 + 3-byte attribute bitmap.
ATTRIBUTE_NAMES = [
    "identification",
    "temperature_alert",
    "MODE",
    "channel_1",
    "channel_2",
    "channel_3",
    "channel_4",
    "channel_5",
    "channel_6",
    "special_mode",
    "auto",
    "display",
    "quick_display",
    "time",
    "other",
    "serial_number",
    "password",
]
STATUS_BITMAP = b"\xff" * ceil(len(ATTRIBUTE_NAMES) / 8)
CHANNEL_NAMES = [f"channel_{idx}" for idx in range(1, 7)]
CHANNEL_LABELS = {
    "channel_1": "Purplish Blue",
    "channel_2": "Pool Blue",
    "channel_3": "Royal Blue + Cool White",
    "channel_4": "Green",
    "channel_5": "Warm White",
    "channel_6": "Red",
}
CHANNEL_LABELS_SHORT = {
    "channel_1": "PB",
    "channel_2": "Blue",
    "channel_3": "RB+CW",
    "channel_4": "Green",
    "channel_5": "Warm White",
    "channel_6": "Red",
}


def labeled_channels(decoded_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return APK-derived channel labels paired with decoded brightness values."""

    return {
        name: {
            "label": CHANNEL_LABELS[name],
            "short_label": CHANNEL_LABELS_SHORT[name],
            "value": decoded_data.get(name),
        }
        for name in CHANNEL_NAMES
    }


def labeled_channels_summary(decoded_data: dict[str, Any], *, short: bool = True) -> str | None:
    """Format channel brightness values with APK-derived labels."""

    if any(decoded_data.get(name) is None for name in CHANNEL_NAMES):
        return None
    labels = CHANNEL_LABELS_SHORT if short else CHANNEL_LABELS
    return ", ".join(f"{labels[name]}={decoded_data[name]}" for name in CHANNEL_NAMES)


class GAgentError(RuntimeError):
    """Protocol or connection error."""


@dataclasses.dataclass(slots=True)
class Frame:
    """A decoded GAgent frame."""

    flag: int
    command: int
    payload: bytes


@dataclasses.dataclass(slots=True)
class ProbeResult:
    """Result of a local probe."""

    host: str
    port: int
    online: bool
    last_command: int | None = None
    last_payload_hex: str = ""
    status_payload_length: int = 0
    decoded_data: dict[str, Any] = dataclasses.field(default_factory=dict)
    elapsed_ms: int = 0
    error: str = ""


def encode_varint(value: int) -> bytes:
    """Encode an unsigned integer as LEB128/varint."""

    if value < 0:
        raise ValueError("value must be non-negative")
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def decode_varint(stream: BinaryIO) -> int:
    """Decode an unsigned LEB128/varint from a stream."""

    shift = 0
    value = 0
    for _ in range(5):
        raw = stream.read(1)
        if not raw:
            raise EOFError("unexpected EOF while reading varint")
        byte = raw[0]
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value
        shift += 7
    raise GAgentError("varint too long")


def build_frame(command: int, payload: bytes = b"", flag: int = 0) -> bytes:
    """Build a GAgent frame.

    Frame shape: 4-byte magic, varint length, 1-byte flag, 2-byte big-endian
    command, payload. Older simple examples use one-byte length; varint keeps
    this compatible with larger Maxspect replies.
    """

    body = bytes([flag]) + command.to_bytes(2, "big") + payload
    return MAGIC + encode_varint(len(body)) + body


def read_exact(stream: BinaryIO, size: int) -> bytes:
    """Read exactly size bytes or raise EOFError."""

    chunks = bytearray()
    while len(chunks) < size:
        data = stream.read(size - len(chunks))
        if not data:
            raise EOFError(f"expected {size} bytes, got {len(chunks)}")
        chunks.extend(data)
    return bytes(chunks)


def read_frame(stream: BinaryIO) -> Frame:
    """Read and decode one GAgent frame from a stream."""

    magic = read_exact(stream, 4)
    if magic != MAGIC:
        raise GAgentError(f"unexpected magic {magic.hex()}")
    length = decode_varint(stream)
    if length < 3:
        raise GAgentError(f"invalid body length {length}")
    body = read_exact(stream, length)
    return Frame(flag=body[0], command=int.from_bytes(body[1:3], "big"), payload=body[3:])


def status_request_payload(serial: int = 3) -> bytes:
    """Build the read-only status request payload for command 0x0093."""

    return serial.to_bytes(4, "big") + bytes([P0_READ_STATUS]) + STATUS_BITMAP


def _control_flags(names: list[str]) -> bytes:
    value = 0
    for name in names:
        value |= 1 << ATTRIBUTE_NAMES.index(name)
    return value.to_bytes(len(STATUS_BITMAP), "big")


def build_control_payload(_decoded_data: dict[str, Any], updates: dict[str, int], serial: int = 4) -> bytes:
    """Build Maxspect/Gizwits var_len control payload.

    The product uses Gizwits `protocolType: var_len`. Control uses a bitmap over
    the full product attribute list, LSB-ordered by attribute id, followed by the
    updated values in attribute order. It is compact, not a full attr_vals block.
    """

    unsupported = [name for name in updates if name not in {"MODE", *CHANNEL_NAMES, "special_mode", "identification"}]
    if unsupported:
        raise ValueError(f"unsupported control attributes: {', '.join(unsupported)}")
    ordered = [name for name in ATTRIBUTE_NAMES if name in updates]
    values = bytearray()
    for name in ordered:
        value = int(updates[name])
        if not 0 <= value <= 255:
            raise ValueError(f"{name} must fit in one byte")
        values.append(value)
    return serial.to_bytes(4, "big") + bytes([P0_CONTROL]) + _control_flags(ordered) + bytes(values)


def _channels_any_on(point: dict[str, Any]) -> bool:
    return any(int(point.get(f"channel_{idx}") or 0) > 0 for idx in range(1, 7))


def _minutes_from_hhmm(value: str) -> int | None:
    try:
        hour, minute = value.split(":", 1)
        return int(hour) * 60 + int(minute)
    except (AttributeError, TypeError, ValueError):
        return None


def infer_lighting_phase(decoded_data: dict[str, Any]) -> str | None:
    """Infer the user-visible lighting phase from mode, clock, and schedule.

    The Maxspect controller appears to handle lunar/night output internally in
    auto mode after the programmed schedule reaches an all-zero point. The raw
    channel datapoints can still show the last daytime channel set, so classify
    the phase from the schedule window instead of channels alone.
    """

    mode = decoded_data.get("MODE")
    if mode is None:
        return None
    channels_on = any(int(decoded_data.get(f"channel_{idx}") or 0) > 0 for idx in range(1, 7))
    if int(mode) != 1:
        return "manual_on" if channels_on else "manual_off"

    points = decoded_data.get("schedule_points") or []
    device_time = decoded_data.get("device_time")
    if not points or not device_time:
        return "auto"
    now = _minutes_from_hhmm(device_time[11:16])
    if now is None:
        return "auto"
    timed_points = [(_minutes_from_hhmm(point.get("time")), point) for point in points]
    timed_points = [(minute, point) for minute, point in timed_points if minute is not None]
    if not timed_points:
        return "auto"
    timed_points.sort(key=lambda item: item[0])
    current = timed_points[-1][1]
    for minute, point in timed_points:
        if minute <= now:
            current = point
        else:
            break
    return "auto_daylight" if _channels_any_on(current) else "auto_lunar"


def decode_other_block(other: bytes) -> dict[str, Any]:
    """Decode the known prefix of the Maxspect `other` extension block.

    The public schema only describes this as "extension between app and
    firmware". Live captures show a 25-byte prefix whose final byte increments
    day-to-day and matches the app-visible lunar-cycle suspicion. Field names are
    deliberately conservative until APK/UI capture confirms the labels.
    """

    if not other:
        return {}
    length = other[0]
    decoded: dict[str, Any] = {"extension_length": length}
    if len(other) < 26 or length < 25:
        return decoded
    decoded.update(
        {
            "extension_type": other[1],
            "lunar_profile": other[2],
            "lunar_high_channels": list(other[3:6]),
            "lunar_low_channels": list(other[6:9]),
            "lunar_enabled": bool(other[10]),
            "lunar_cycle_day": other[25],
        }
    )
    return decoded


def decode_schedule(auto: bytes) -> list[dict[str, int | str]]:
    """Decode the 255-byte auto/schedule block into time/channel points.

    Observed layout begins with header byte, count byte, then count fixed
    9-byte records: point index, hour, minute, channel1..channel6.
    """

    if len(auto) < 2:
        return []
    count = auto[1]
    points: list[dict[str, int | str]] = []
    offset = 2
    for _ in range(count):
        chunk = auto[offset : offset + 9]
        if len(chunk) < 9:
            break
        _, hour, minute, *channels = chunk
        if hour <= 23 and minute <= 59:
            point: dict[str, int | str] = {"time": f"{hour:02d}:{minute:02d}"}
            point.update({f"channel_{idx}": channels[idx - 1] for idx in range(1, 7)})
            points.append(point)
        offset += 9
    return points


def _decode_device_time(time_value: bytes) -> str | None:
    if len(time_value) != 6:
        return None
    yy, month, day, hour, minute, second = time_value
    if 1 <= month <= 12 and 1 <= day <= 31 and hour <= 23 and minute <= 59 and second <= 59:
        return f"20{yy:02d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
    return None


def decode_maxspect_status_payload(payload: bytes) -> dict[str, Any] | None:
    """Decode a Maxspect/Syna-G 0x0094 status payload.

    The device response is SN(4) + 0x13(read-datapoint-response) + bitmap(3)
    + fixed schema data from product key 401dff8180744f02b071f476edf6363b.
    """

    minimum = 4 + 1 + len(STATUS_BITMAP) + 567
    if len(payload) < minimum or payload[4] != P0_READ_STATUS_ACK:
        return None

    sn = int.from_bytes(payload[:4], "big")
    bitmap = payload[5 : 5 + len(STATUS_BITMAP)]
    data = payload[5 + len(STATUS_BITMAP) :]
    offset = 0

    flags = data[offset]
    offset += 1
    values: dict[str, Any] = {
        "sn": sn,
        "p0_cmd": f"{P0_READ_STATUS_ACK:02x}",
        "requested_bitmap": bitmap.hex(),
        "identification": bool(flags & 0x01),
        "temperature_alert": bool(flags & 0x02),
    }
    for name in ["MODE", *CHANNEL_NAMES, "special_mode"]:
        values[name] = data[offset]
        offset += 1

    auto = data[offset : offset + 255]
    offset += 255
    display = data[offset : offset + 6]
    offset += 6
    quick_display = data[offset : offset + 7]
    offset += 7
    time_value = data[offset : offset + 6]
    offset += 6
    # The APK schema says `other` is 255 bytes, but live MJ2 firmware pads a few
    # extra bytes before the fixed 12-byte serial. Anchor the read-only serial on
    # its stable ASCII prefix rather than losing the trailing digits.
    serial_offset = data.find(b"MJ-", offset)
    if serial_offset < 0:
        serial_offset = offset + 255
    other = data[offset:serial_offset]
    serial = data[serial_offset : serial_offset + 12]
    password = data[serial_offset + 12 : serial_offset + 29]

    schedule_points = decode_schedule(auto)
    other_decoded = decode_other_block(other)
    values.update(
        {
            "auto": auto.hex(),
            "schedule_points": schedule_points,
            "schedule_summary": "; ".join(
                f"{point['time']} {point['channel_1']}/{point['channel_2']}/{point['channel_3']}/{point['channel_4']}/{point['channel_5']}/{point['channel_6']}"
                for point in schedule_points
            ) or "unknown",
            "display": display.hex(),
            "quick_display": quick_display.hex(),
            "time_hex": time_value.hex(),
            "device_time": _decode_device_time(time_value),
            "other": other.hex(),
            "other_decoded": other_decoded,
            "lunar_cycle_day": other_decoded.get("lunar_cycle_day"),
            "lunar_enabled": other_decoded.get("lunar_enabled"),
            "lunar_high_channels": other_decoded.get("lunar_high_channels"),
            "lunar_low_channels": other_decoded.get("lunar_low_channels"),
            "serial_number": serial.rstrip(b"\x00").decode("ascii", errors="ignore"),
            "password_configured": any(password),
        }
    )
    values["channel_labels"] = labeled_channels(values)
    values["channels_labeled_summary"] = labeled_channels_summary(values)
    values["lighting_phase"] = infer_lighting_phase(values)
    return values


def _read_status_after_handshake(stream: BinaryIO, serial: int = 3) -> Frame:
    stream.write(build_frame(CMD_P0, status_request_payload(serial)))
    status = read_frame(stream)
    if status.command != CMD_P0_REPLY:
        raise GAgentError(f"expected 0094, got {status.command:04x}")
    return status


def _expect_control_ack(stream: BinaryIO, serial: int) -> None:
    ack = read_frame(stream)
    if ack.command != CMD_P0_REPLY:
        raise GAgentError(f"expected 0094 ACK, got {ack.command:04x}")
    if ack.payload != serial.to_bytes(4, "big"):
        raise GAgentError(f"unexpected control ACK payload {ack.payload.hex()}")


def _open_authenticated_stream(host: str, port: int, timeout: float) -> tuple[socket.socket, Any]:
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.settimeout(timeout)
    stream = sock.makefile("rwb", buffering=0)

    stream.write(build_frame(CMD_HANDSHAKE))
    hello = read_frame(stream)
    if hello.command != CMD_HANDSHAKE_REPLY:
        sock.close()
        raise GAgentError(f"expected 0007, got {hello.command:04x}")

    stream.write(build_frame(CMD_AUTH, hello.payload))
    auth = read_frame(stream)
    if auth.command != CMD_AUTH_REPLY:
        sock.close()
        raise GAgentError(f"expected 0009, got {auth.command:04x}")
    return sock, stream


def control(host: str, updates: dict[str, int], port: int = 12416, timeout: float = 5.0, serial: int = 4) -> ProbeResult:
    """Send a local control update and return a fresh readback probe result."""

    current = probe(host, port, timeout)
    if not current.online:
        raise GAgentError(current.error or "device is offline")
    payload = build_control_payload(current.decoded_data, updates, serial=serial)
    sock, stream = _open_authenticated_stream(host, port, timeout)
    with sock:
        stream.write(build_frame(CMD_P0, payload))
        _expect_control_ack(stream, serial)
    # ACK only means accepted; success is determined by a fresh readback.
    return probe(host, port, timeout)


def probe(host: str, port: int = 12416, timeout: float = 5.0) -> ProbeResult:
    """Run a local handshake/status probe against a local device."""

    started = time.monotonic()
    result = ProbeResult(host=host, port=port, online=False)
    try:
        sock, stream = _open_authenticated_stream(host, port, timeout)
        with sock:
            status = _read_status_after_handshake(stream)
            result.online = True
            result.last_command = status.command
            result.last_payload_hex = status.payload[:64].hex()
            result.status_payload_length = len(status.payload)
            result.decoded_data = decode_maxspect_status_payload(status.payload) or {}
    except Exception as exc:  # noqa: BLE001 - surfaced as diagnostic sensor
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        result.elapsed_ms = int((time.monotonic() - started) * 1000)
    return result
