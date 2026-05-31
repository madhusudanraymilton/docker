#!/usr/bin/env python3
"""
prune_addons.py
---------------
Generate the module whitelist used by entrypoint.sh / lock_modules.sql.
Run at image build time (Dockerfile RUN step).

IMPORTANT

Odoo's Apps menu reads from the `ir.module.module` table in PostgreSQL,
NOT directly from the filesystem at runtime.

Odoo 19's base module references metadata for many bundled modules while the
database is being initialized. Physically deleting bundled addon directories
before the first base load can break bootstrap. Therefore this script keeps
the bundled addons on disk and only writes /opt/odoo-whitelist.txt. The actual
Apps-menu restriction is enforced after bootstrap by scripts/lock_modules.sql.

The whitelist contains core modules only. Custom addons are discovered at
runtime from /mnt/extra-addons and appended to the SQL whitelist by
entrypoint.sh.
"""

from __future__ import annotations

import os
import sys

# Odoo 19 official image keeps bundled addons here. The /usr/lib/python3/dist-packages/addons
# path historically existed in some older debian-packaged builds; we attempt it defensively but
# don't fail if it's missing.
ADDONS_DIRS: list[str] = [
    "/usr/lib/python3/dist-packages/odoo/addons",
    "/usr/lib/python3/dist-packages/addons",
]

WHITELIST: set[str] = {
    # ── Core / framework (required to boot Odoo) ─────────────────────────────
    "base",
    "web",
    "base_setup",
    "base_import",
    "base_import_module",
    "base_install_request",
    "html_editor",
    "bus",
    "web_tour",
    "http_routing",
}


def audit(addons_dir: str) -> tuple[int, list[str]]:
    """Audit a single addons directory. Returns (exit_code, present)."""
    if not os.path.isdir(addons_dir):
        print(
            f"[module_whitelist] SKIP: {addons_dir} not found "
            "(this is fine if path doesn't exist on this image)"
        )
        return 0, []

    present: list[str] = []

    for entry in sorted(os.listdir(addons_dir)):
        full = os.path.join(addons_dir, entry)
        if not os.path.isdir(full):
            continue
        if entry in WHITELIST:
            present.append(entry)

    print(f"[module_whitelist] {addons_dir}")
    print(
        f"[module_whitelist]   Present ({len(present):>3}): "
        f"{', '.join(present) if present else '-'}"
    )
    return 0, present


def main() -> int:
    all_kept: set[str] = set()
    rc_final = 0

    for d in ADDONS_DIRS:
        rc, present = audit(d)
        all_kept.update(present)
        rc_final = rc_final or rc

    # Sanity-check: every whitelisted module must exist in AT LEAST one addons dir
    missing = sorted(m for m in WHITELIST if m not in all_kept)
    if missing:
        print(
            f"[module_whitelist] WARNING: whitelisted modules not present on disk: {missing}",
            file=sys.stderr,
        )
        # Non-fatal: Odoo 19 has reshuffled some modules; we don't want a missing
        # legacy entry to fail the entire image build.

    # Emit the canonical whitelist as a file so entrypoint.sh / SQL can read it
    # without duplicating the list.
    out_path = "/opt/odoo-whitelist.txt"
    with open(out_path, "w", encoding="utf-8") as fh:
        for m in sorted(WHITELIST):
            fh.write(m + "\n")

    print(
        f"[module_whitelist] Wrote canonical whitelist -> "
        f"{out_path} ({len(WHITELIST)} modules)"
    )

    return rc_final


if __name__ == "__main__":
    sys.exit(main())
