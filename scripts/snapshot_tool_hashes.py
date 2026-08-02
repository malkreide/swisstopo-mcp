#!/usr/bin/env python3
"""Snapshot a hash per tool definition (audit SEC-022).

A tool's name, description and input schema are what a client approves. If any
of them changes, the client is running against a definition it never saw. This
script writes `tool-hashes.json`; CI regenerates it and fails on an
uncommitted difference, so a tool-definition change cannot reach a release
without showing up in review.

Usage:
    python scripts/snapshot_tool_hashes.py           # write tool-hashes.json
    python scripts/snapshot_tool_hashes.py --check   # exit 1 if it differs
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import pathlib
import sys

from swisstopo_mcp.server import mcp

OUTPUT = pathlib.Path(__file__).resolve().parent.parent / "tool-hashes.json"


def _normalise_description(description: str | None) -> str:
    """Dedent a tool description before hashing.

    Descriptions come from function docstrings, and Python 3.13 strips their
    common leading whitespace at compile time while 3.11 and 3.12 do not. Left
    raw, the same source would hash differently per interpreter and the CI
    matrix would disagree with itself. `cleandoc` is idempotent on the already
    dedented 3.13 form, so all three converge.
    """
    return inspect.cleandoc(description or "")


async def collect() -> dict[str, str]:
    tools = await mcp.list_tools()
    return {
        tool.name: hashlib.sha256(
            json.dumps(
                {
                    "name": tool.name,
                    "description": _normalise_description(tool.description),
                    "schema": tool.input_schema,
                },
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        for tool in sorted(tools, key=lambda t: t.name)
    }


def render(hashes: dict[str, str]) -> str:
    return json.dumps(dict(sorted(hashes.items())), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the committed snapshot is stale instead of rewriting it.",
    )
    args = parser.parse_args()

    rendered = render(asyncio.run(collect()))

    if not args.check:
        OUTPUT.write_text(rendered, encoding="utf-8")
        print(f"Wrote {OUTPUT.name}")
        return 0

    if not OUTPUT.exists():
        print(f"{OUTPUT.name} is missing — run scripts/snapshot_tool_hashes.py", file=sys.stderr)
        return 1
    if OUTPUT.read_text(encoding="utf-8") != rendered:
        print(
            f"{OUTPUT.name} is stale: a tool name, description or input schema "
            "changed.\nRun `python scripts/snapshot_tool_hashes.py`, commit the "
            "result, and add a CHANGELOG entry naming the affected tools — "
            "clients must re-approve a changed definition.",
            file=sys.stderr,
        )
        return 1
    print(f"{OUTPUT.name} is up to date ({len(rendered.splitlines()) - 2} tools).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
