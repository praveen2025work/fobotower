# Skills for office Claude Code

Two skills, for two different jobs. Copy the one you need into the office repo, at
`.claude/skills/<name>/SKILL.md`, and copy this whole `migration/` folder in as well,
so the skill can read the guide, the rename map and the list of changes.

| Your office repo has… | You want to… | Skill |
|---|---|---|
| A copy of the platform under its old name, Helix (`apps/backend/helix`, `HELIX_*`), taken before 2026-10-06 | Get the new names, steps v2 and the rest, and keep the office's connectors, adapter and config | [`upgrade-to-aof`](upgrade-to-aof/SKILL.md) |
| FOBO running on Agent One, and Agent One Finance not yet (or just) added | Move FOBO onto Agent One Finance as configuration, prove parity, and retire the FOBO code | [`fobo-to-aof`](fobo-to-aof/SKILL.md) |
| Both | Run `upgrade-to-aof` first, then `fobo-to-aof` | both |

What goes with them:

- [`../whats-new.md`](../whats-new.md): everything that changed since 2026-10-04, with
  the migrations, features, files and office actions.
- [`../rename-map.json`](../rename-map.json): the old → new names, as data.
- `apps/backend/scripts/aof_convert.py`: applies the map to a repo (a dry run by default).
  It lists what is left for a person to decide, and running it twice changes nothing.
- [`../../renaming.md`](../../renaming.md): the names in a table, and the release order.
- [`../README.md`](../README.md): the FOBO change guide (for `fobo-to-aof`).

## Getting upstream into the office

`upgrade-to-aof` needs upstream `main` (`praveen2025work/fobotower`) inside the office repo.
If the office cannot reach GitHub, carry a git bundle in:

```bash
# on a machine with access
git clone https://github.com/praveen2025work/fobotower && cd fobotower && git bundle create aof.bundle main
# in the office repo
git fetch /path/aof.bundle 'refs/heads/*:refs/remotes/upstream/*'
```

## Prompts to start a session

**Upgrade:**

> Use the upgrade-to-aof skill. Upstream is `upstream/main` (fetched from the bundle). Start
> with Phase 0 and stop after it. Work on the branch `upgrade/agent-one-finance`. Do not touch
> any database or deployment.

**FOBO:** use the prompt in [§9 of the change guide](../README.md#9-the-prompt-to-start-office-claude).

## How these were tested

The upgrade path was rehearsed here on a mock office repo:

- a copy of the platform from 2026-10-06, before steps v2 phases 2–6 and before the rename;
- no shared git history with upstream;
- an office edit in the LLM adapter and one in `connectors.yaml`.

The steps were Phase 0 (bundle), the baseline search, Phase 2 (converter) and Phase 3,
route B (`git apply -3`). They applied with no conflicts. The result was identical to upstream
except for the two office edits, which were kept.

The converter on its own was checked against the real rename. On the converted copy:

- backend: 740 passed;
- web: 92 passed;
- FOBO console: 192 passed.
