"""Gizwits/GAgent local protocol helpers for Maxspect Syna-G devices.

The helpers in this module avoid Home Assistant imports so they can be tested
and used by the standalone probe script.
"""

from __future__ import annotations

import dataclasses
import socket
import time
from typing import BinaryIO

MAGIC = b"\x00\x00\x00\x03"
CMD_HANDSHAKE = 0x0006
CMD_HANDSHAKE_REPLY = 0x0007
CMD_AUTH = 0x0008
CMD_AUTH_REPLY = 0x0009
CMD_P0 = 0x0093
CMD_P0_REPLY = 0x0094

# APK-derived getDeviceStatus payload for a 17-attribute schema:
# SN(4-byte BE) + P0 read cmd 0x12 + 3-byte attribute bitmap.
STATUS_BITMAP = b"\xff\xff\xff"


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
    """Result of a read-only local probe."""

    host: str
    port: int
    online: bool
    last_command: int | None = None
    last_payload_hex: str = ""
    status_payload_length: int = 0
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

    return serial.to_bytes(4, "big") + b"\x12" + STATUS_BITMAP


def probe(host: str, port: int = 12416, timeout: float = 5.0) -> ProbeResult:
    """Run a read-only handshake/status probe against a local device."""

    started = time.monotonic()
    result = ProbeResult(host=host, port=port, online=False)
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            stream = sock.makefile("rwb", buffering=0)

            stream.write(build_frame(CMD_HANDSHAKE))
            hello = read_frame(stream)
            if hello.command != CMD_HANDSHAKE_REPLY:
                raise GAgentError(f"expected 0007, got {hello.command:04x}")

            stream.write(build_frame(CMD_AUTH, hello.payload))
            auth = read_frame(stream)
            if auth.command != CMD_AUTH_REPLY:
                raise GAgentError(f"expected 0009, got {auth.command:04x}")

            stream.write(build_frame(CMD_P0, status_request_payload()))
            status = read_frame(stream)
            if status.command != CMD_P0_REPLY:
                raise GAgentError(f"expected 0094, got {status.command:04x}")

            result.online = True
            result.last_command = status.command
            result.last_payload_hex = status.payload[:64].hex()
            result.status_payload_length = len(status.payload)
    except Exception as exc:  # noqa: BLE001 - surfaced as diagnostic sensor
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        result.elapsed_ms = int((time.monotonic() - started) * 1000)
    return result
