"""Bring a running deployment's capabilities and groups in line with the
config files — through the same four-eyes approval as any change.

The YAML files under config/agent-one-finance seed a fresh database. Once a capability
or group is live, its file is only a proposal: this command drafts a new
version wherever the file differs from what is active, as
"system:config-sync", and an owner approves it in the console (Authoring,
or the group's page). A group whose new file needs a newer capability
version waits: run the command again after that version is approved.

    python -m agent_one_finance.config_sync            # draft what changed
    python -m agent_one_finance.config_sync --dry-run  # only list it
"""

import argparse
import asyncio
import json

import yaml
from sqlalchemy import func, select

from agent_one_finance import capabilities
from agent_one_finance import groups as team_groups
from agent_one_finance.config import settings
from agent_one_finance.db import get_session
from agent_one_finance.manifest import Manifest, problems
from agent_one_finance.models import CapabilityVersion, GroupVersion

SYNC_USER = "system:config-sync"


def _same(a: dict, b: dict) -> bool:
    # Compared as values, not text: a number stored as 12.0 equals the file's 12.
    as_json = lambda d: json.loads(json.dumps(d, default=str))  # noqa: E731
    return as_json(a) == as_json(b)


def _manifest(stored: dict) -> dict:
    """A stored manifest as today's schema writes it, so a field added since
    (with its default) is not mistaken for a change in the file."""
    try:
        return Manifest.model_validate(stored).model_dump(by_alias=True)
    except ValueError:
        return stored


def _config(stored: dict) -> dict:
    try:
        return team_groups.GroupConfig.model_validate(stored).model_dump()
    except ValueError:
        return stored


async def _capabilities(dry_run: bool) -> list[str]:
    out = []
    for m in capabilities.seed_files():
        body = m.model_dump(by_alias=True)
        async with get_session() as s:
            rows = (await s.execute(select(CapabilityVersion).where(
                CapabilityVersion.capability_id == m.id))).scalars().all()
        active = next((r for r in rows if r.status == "active"), None)
        if active is not None and _same(_manifest(active.manifest), body):
            continue
        if any(r.status == "draft" and _same(_manifest(r.manifest), body) for r in rows):
            out.append(f"{m.id}: a draft with this file is waiting for approval")
            continue
        # A capability that is not live yet (a new file) is drafted as version 1.
        found = problems(Manifest.model_validate(body))
        if found:
            out.append(f"{m.id}: file has problems, not drafted: {'; '.join(found)}")
            continue
        if not dry_run:
            async with get_session() as s:
                n = max((r.version for r in rows), default=0) + 1
                s.add(CapabilityVersion(capability_id=m.id, version=n, manifest=body, status="draft",
                                        note="from config files (config-sync)", drafted_by=SYNC_USER))
                await s.commit()
        out.append(f"{m.id}: {'would draft' if dry_run else 'drafted'} a new version — an owner approves it")
    return out


async def _groups(dry_run: bool) -> list[str]:
    out = []
    root = settings().config_dir / "groups"
    if not root.exists():
        return out
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        try:
            _, base = await capabilities.active(folder.name)
        except capabilities.CapabilityError:
            out += [f"{folder.name}/{p.stem}: waits for capability {folder.name} to be approved"
                    for p in sorted(folder.glob("*.yaml"))]
            continue
        for path in sorted(folder.glob("*.yaml")):
            cfg = team_groups.GroupConfig.model_validate(yaml.safe_load(path.read_text()))
            body = cfg.model_dump()
            async with get_session() as s:
                rows = (await s.execute(select(GroupVersion).where(
                    GroupVersion.capability_id == folder.name, GroupVersion.group_id == cfg.group))).scalars().all()
            active = next((r for r in rows if r.status == "active"), None)
            if active is not None and _same(_config(active.config), body):
                continue
            label = f"{folder.name}/{cfg.group}"
            if any(r.status == "draft" and _same(_config(r.config), body) for r in rows):
                out.append(f"{label}: a draft with this file is waiting for approval")
                continue
            _, found = team_groups.effective(base, cfg)
            if found:
                out.append(f"{label}: waits for a newer {folder.name} version ({'; '.join(found[:3])})")
                continue
            if not dry_run:
                async with get_session() as s:
                    n = ((await s.execute(select(func.max(GroupVersion.version)).where(
                        GroupVersion.capability_id == folder.name,
                        GroupVersion.group_id == cfg.group))).scalar_one() or 0) + 1
                    s.add(GroupVersion(capability_id=folder.name, group_id=cfg.group, version=n, config=body,
                                       status="draft", note="from config files (config-sync)", drafted_by=SYNC_USER))
                    await s.commit()
            out.append(f"{label}: {'would draft' if dry_run else 'drafted'} a new version — a group owner approves it")
    return out


async def sync(dry_run: bool = False) -> list[str]:
    return await _capabilities(dry_run) + await _groups(dry_run)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dry-run", action="store_true")
    for line in asyncio.run(sync(p.parse_args().dry_run)) or ["everything matches the config files"]:
        print(line)


if __name__ == "__main__":
    main()
