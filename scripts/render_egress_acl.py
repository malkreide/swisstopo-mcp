#!/usr/bin/env python3
"""Regenerate deploy/smokescreen-acl.yaml from ALLOWED_HOSTS (audit SEC-021).

The egress proxy's allow-list and the code-layer frozenset must not drift. This
renders one from the other rather than asking a reviewer to compare them.

Usage:
    python scripts/render_egress_acl.py           # write the ACL
    python scripts/render_egress_acl.py --check   # exit 1 if it is stale
"""
from __future__ import annotations

import argparse
import pathlib
import sys

from swisstopo_mcp.api_client import ALLOWED_HOSTS

OUTPUT = pathlib.Path(__file__).resolve().parent.parent / "deploy" / "smokescreen-acl.yaml"


def render() -> str:
    existing = OUTPUT.read_text(encoding="utf-8")
    header, _, _ = existing.partition("    allowed_domains:\n")
    # Six spaces: the entries must nest *under* `allowed_domains:`, which itself
    # sits at four. Emitting them at two made the key parse as null and promoted
    # every host to a sibling of the service object — a file that renders,
    # round-trips through `--check`, and enforces nothing (audit SEC-021).
    rules = "\n".join(f"      - {h}" for h in sorted(ALLOWED_HOSTS))
    return (
        header
        + "    allowed_domains:\n"
        + rules
        + "\n\ndefault:\n  name: default\n  action: enforce\n  allowed_domains: []\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    rendered = render()
    if not args.check:
        OUTPUT.write_text(rendered, encoding="utf-8")
        print(f"Wrote {OUTPUT.name} ({len(ALLOWED_HOSTS)} hosts)")
        return 0

    if OUTPUT.read_text(encoding="utf-8") != rendered:
        print(
            f"{OUTPUT.name} is stale — ALLOWED_HOSTS changed. Run "
            "`python scripts/render_egress_acl.py` and commit the result.",
            file=sys.stderr,
        )
        return 1
    print(f"{OUTPUT.name} is up to date ({len(ALLOWED_HOSTS)} hosts).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
