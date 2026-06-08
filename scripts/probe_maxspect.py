#!/usr/bin/env python3
"""Probe Maxspect Syna-G devices over local Gizwits/GAgent TCP."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "maxspect_syna_g_local"))

from gagent import probe  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("hosts", nargs="+", help="Device host/IP to probe")
    parser.add_argument("--port", type=int, default=12416)
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()

    results = [dataclasses.asdict(probe(host, args.port, args.timeout)) for host in args.hosts]
    print(json.dumps(results, indent=2))
    return 0 if all(item["online"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
