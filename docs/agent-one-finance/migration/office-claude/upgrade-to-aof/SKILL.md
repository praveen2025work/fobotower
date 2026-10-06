---
name: upgrade-to-aof
description: Upgrade the office copy of the platform (still named Helix, taken from praveen2025work/fobotower before 2026-10-06) to the current Agent One Finance. It renames everything to the new names, brings in steps v2 and the other new features, migrates the database, and keeps the office's own connectors, LLM adapter, configuration and FOBO answers. Use when asked to rename Helix, upgrade or sync with upstream, bring in steps v2, or move the office app to Agent One Finance. Works phase by phase and stops for sign-off after each phase.
---

# Upgrade the office app to Agent One Finance

The office repo has a copy of the platform under its old name, **Helix**:

- `apps/backend/helix`, `config/helix`;
- `HELIX_*` settings, `X-Helix-*` headers, `helix_*` tables.

On top of that copy sit the office's own changes: connectors, an LLM adapter, configuration, perhaps more.
Upstream (`praveen2025work/fobotower`, `main`) has since:

1. renamed everything to **Agent One Finance**;
2. added steps v2 and the features listed in `whats-new.md`.

Your job is to make the office repo match upstream and keep every office change, so that:

- the office deployment runs the new names;
- every open case carries on;
- every FOBO answer stays the same.

**Read first, every session (they come from upstream):**

1. `docs/agent-one-finance/migration/whats-new.md`: what changed, the migrations in order, the
   office actions, and the LLM adapter changes.
2. `docs/agent-one-finance/renaming.md`: the old → new names and the release order.
3. `docs/agent-one-finance/migration/rename-map.json`: the same names as data. Do not edit it.
   If it lacks a rule the office needs, add the rule to the office's own notes and apply it by hand.
4. `apps/backend/scripts/aof_convert.py --help`: the converter.

If you cannot see upstream (Phase 0), stop and ask the user how to get it.

## Rules that override everything else

1. **Every FOBO answer stays the same.** If something would change a category, side or verdict:
   - do not change it;
   - write it in `UPGRADE_GAPS.md`;
   - ask the user.
2. **Upstream owns the engine; the office owns its extension points.**
   - **Upstream:** the engine is `agent_one_finance/` (`workflow.py`, `steps*.py`, `stepkit.py`,
     `gateway.py`, `manifest.py`, `runner.py`, the gates, and the rest), plus `apps/web` and the migrations.
   - **Office:** the extension points are:
     - `config/agent-one-finance/**` (connectors, groups, capabilities, knowledge, dev users);
     - the LLM adapter's `_run`, or the office adapter module;
     - the entitlement and tracing hooks;
     - deployment files;
     - office-only migrations and tests.
   - **When both changed the same lines:** stop and ask. Never pick a side on your own.
3. **Use the converter for the rename, not hand edits.** Run `aof_convert.py`, read its
   leftover list, and decide each leftover. Do not run broad `sed` over the repo.
4. **Never touch a production database.** Run migrations on a disposable copy or UAT first.
   Run `downgrade -1`, then `upgrade head`, before anyone signs off.
5. **No secrets in files.** Rename settings in the environment and the secret store. Never write
   their values into the repo or the chat.
6. **Keep the old names working until the release is done.** Do this on the outside (old roles beside the new ones in
   entitlements; a proxy that sends both headers). Never leave old names in the code.
7. **One phase per turn.** Finish the phase, run its check, report, and stop. Wait until the user
   approves the phase.
8. **Commit each phase separately**, with a message that names the phase, on a branch (for example
   `upgrade/agent-one-finance`), never on the main branch. Do not push unless the user asks.

## Phase 0: Get upstream into the office repo

This phase only adds things. It changes no office file.

1. Get upstream `main` in whichever way the office allows:
   - **Remote:** `git remote add upstream <url>`, then `git fetch upstream main`.
   - **Bundle (no GitHub from the office):** someone runs `git bundle create aof.bundle main` on
     a machine with access and copies the file in. Then run
     `git fetch /path/aof.bundle 'refs/heads/*:refs/remotes/upstream/*'`.
   - **Folder copy (no git):** unpack it outside the repo and use its path as `<upstream>`.
     Wherever this skill says `git show upstream/main:<file>`, read `<upstream>/<file>`.
     Route B then uses `git merge-file` for each file.
2. Copy the conversion kit in from upstream:

   ```bash
   git checkout upstream/main -- docs/agent-one-finance/migration docs/agent-one-finance/renaming.md \
     apps/backend/scripts/aof_convert.py
   ```

Check:

- `python apps/backend/scripts/aof_convert.py --root .` runs (a dry run) and lists the moves;
- `git log -1 upstream/main` shows the expected commit.

Commit: `Upgrade phase 0: add the Agent One Finance conversion kit`.

## Phase 1: Inventory (read only)

Write `UPGRADE_INVENTORY.md` with these sections.

1. **Baseline.** Which upstream commit is the office copy from? If the histories are shared,
   use `git merge-base HEAD upstream/main`. Otherwise, compare the office working tree with
   each candidate upstream commit. The one with the fewest changed lines is the baseline:

   ```bash
   for c in $(git log --format=%h --since=2026-09-15 --until=2026-10-06 upstream/main); do
     echo "$c $(git diff --shortstat $c -- apps/backend/helix apps/web/src config/helix | tail -1)"
   done
   ```

   Write the commit and how sure you are. Then mark it: `git branch upstream-base <commit>`.
2. **Office changes.** List every file that differs from the baseline
   (`git diff --stat upstream-base -- apps config`). For each file, give the path, what changed,
   and its owner under rule 2 (extension point or engine). Engine changes are the risk.
   For each one, write why the office needed it and whether upstream now covers it
   (check `whats-new.md`).
3. **Outside the code**, for the release:
   - every `HELIX_*` setting in the deployment files and secret store (names only);
   - the headers the proxy, bots and webhooks send;
   - the `HELIX_*` roles in the entitlement system;
   - the Phoenix queries and alerts that use `helix.*`;
   - any Agent SDK hook that names `mcp__helix__`.
4. **Database:**
   - the current Alembic head (`alembic current`);
   - any office-only migrations;
   - roughly how many open cases there are (they must carry on).
5. **Route** (see Phase 3):
   - **A**, if every office change is at an extension point;
   - **B**, if any engine file has office edits.
6. **Open questions**, numbered.

Check: every section is filled in. Stop, show the route and the open questions.

## Phase 2: Rename the office copy

1. Run the converter as a dry run and save the output:
   `python apps/backend/scripts/aof_convert.py --root . > UPGRADE_RENAME_DRYRUN.txt`.
   Read it.
   - Files listed under moves and edits should be platform files and office extension files.
   - If a FOBO file (`apps/backend/fobo`, `apps/console` outside `src/aof`) appears with
     anything other than the console's Agent One Finance view, stop and ask.
2. Apply it with `--apply`.
   - A `keep` line means a file exists under both the old and the new folder, usually an
     upstream doc the kit brought in. If the old file equals the baseline's copy, delete the
     old file (`git diff --quiet upstream-base -- <old path>`). Otherwise, put the office's
     lines into the new file.
   - An old `docs/agent-one-finance/migration/office-claude/SKILL.md` is the FOBO skill's
     previous place; it now lives in `office-claude/fobo-to-aof/`. Delete the old copy.
   - Then go through the leftover list. For each leftover line, write
   the decision in `UPGRADE_INVENTORY.md`:
   - **Rename it** if it is a name the code uses: an office table, an office setting, an office
     header. Do it by hand, in the converter's style.
   - **Keep it** if it is history: old migration files, `renaming.md`, dated design notes,
     the FOBO chat string "Helix session".
   - **Ask** if it might be data. For example, a role name inside YAML that the entitlement system also holds.
3. If the office has its own Alembic migrations that create `helix_*` tables, leave the old
   files alone. The rename migration in Phase 3 renames tables by their actual names, so check
   `e7f9a1b3c5d7` covers the office tables. If it does not, write an office migration after it
   that renames them.
4. Run the office's own tests exactly as before the rename (`pytest`, `vitest`, `tsc`). The
   behaviour has not changed, only names, so the counts must equal the pre-rename counts.

Check:

- the tests are green with the same counts;
- `grep -rni helix` shows only the leftovers you decided to keep.

Commit: `Upgrade phase 2: rename Helix to Agent One Finance`.

## Phase 3: Bring in the upstream changes

First rename the baseline the same way, so all three sides use the same names:

```bash
git worktree add ../aof-base upstream-base
python apps/backend/scripts/aof_convert.py --root ../aof-base --apply   # the office repo's copy of the kit
git -C ../aof-base add -A && git -C ../aof-base commit -qm "baseline, renamed"   # upstream-base now points here
```

**Route A (office changes are only at extension points).** Recommended when it applies.

1. Take upstream for everything the engine owns:

   ```bash
   git checkout upstream/main -- apps/backend/agent_one_finance apps/backend/migrations \
     apps/backend/tests/agent_one_finance apps/backend/scripts apps/web apps/console/src/aof \
     apps/console/src/app/aof docs/agent-one-finance
   # files upstream deleted since the baseline
   git diff --name-only --diff-filter=D upstream-base upstream/main | xargs -r git rm -q --ignore-unmatch
   ```

   Office-only files in those folders stay. If the office changed an upstream doc, merge it
   like a configuration file (step 2).
2. For each extension-point file, run a three-way merge (renamed baseline, office, upstream):

   ```bash
   f=config/agent-one-finance/connectors.yaml
   git show upstream-base:$f > /tmp/base && git show upstream/main:$f > /tmp/theirs
   git merge-file $f /tmp/base /tmp/theirs    # conflicts are marked in $f
   ```

   Do this for every file under `config/agent-one-finance/` that both sides have, and for
   `pyproject.toml` and `apps/web/package.json`. In a conflict, the office wins on its own
   values (URLs, roles, thresholds, books) and upstream wins on keys that are new. Take files
   that only upstream has as they are.
3. Step 1 overwrote any office edits inside those folders, such as `_run` in
   `llm_agent_sdk.py`. The office version is still in `HEAD`
   (`git diff HEAD -- apps/backend/agent_one_finance/llm_agent_sdk.py`). Put the office `_run`
   back into the new file, or keep the office adapter module. See Phase 4.

**Route B (the office changed engine files).**

1. Replay upstream onto the office branch with a three-way apply:

   ```bash
   git diff --binary upstream-base upstream/main -- . ':!docs/agent-one-finance/migration' > ../upstream.patch
   git apply -3 ../upstream.patch
   ```
2. For each conflict:
   - **Upstream added or changed it, the office did not:** take upstream.
   - **The office changed it, upstream did not:** keep the office version.
   - **Both changed the same lines:** stop, show both, and say which upstream feature it
     belongs to (`whats-new.md` §2). Ask the user.
3. For each office engine change from the inventory, check whether upstream now does the same
   thing. If it does, prefer upstream, and write that down.

Both routes:

- Keep the office's own migrations after `e7f9a1b3c5d7`: set their `down_revision`, and check
  `alembic heads` shows one head.
- Merge the dependencies in `pyproject.toml` and `package.json`. Then regenerate the lock files
  with the tools (`pip`/`uv`, `npm install`), never by hand.

Check:

- `pytest -q` (backend), `npx vitest run` and `npx tsc --noEmit -p .` (web), and
  `npx vitest run` (console) are green;
- `alembic heads` shows one head.

Report the counts next to upstream's (`whats-new.md` §5).

Commit: `Upgrade phase 3: bring in Agent One Finance <upstream short sha>`.

## Phase 4: Adapter, connectors and configuration

1. **LLM adapter** (`whats-new.md` §4). Keep the office's `_run`. Add:
   - `notes` and `sections` to what it sends;
   - parsing of `sections` in what it returns.

   Add `extract` only if the office will use the `extract` step. Check that the trace attributes
   use `aof.llm.*`.
2. **Connectors.** The office's `connectors.yaml` keeps its servers.
   - New example capabilities (`fin.accruals`, `client.complaints`, `controls.*`,
     `payments.exceptions`) need connectors the office may not have yet. Leave them out, or use
     the entries in `connectors.office.example.yaml` as a starting point. Never point them at stubs in UAT
     or production.
   - A capability whose connectors are missing will not validate. That is fine for a
     capability the office does not use; write it down.
3. **Configuration.**
   - Run `python -m agent_one_finance.config_sync` to create drafts for the changed files.
   - A second owner approves them in Authoring.
   - Do not approve them yourself.
4. **FOBO:**
   - Run `pytest -q tests/agent_one_finance/test_fobo_playbook.py
     tests/agent_one_finance/test_break_investigation.py`.
   - If FOBO groups are live in the office, run `scripts/fobo_aof_parity.py` for one recent
     COB per book and compare with the last run before the upgrade. The deterministic verdicts
     must match exactly.

Check: green tests and a parity diff of zero. Commit: `Upgrade phase 4: office adapter and configuration`.

## Phase 5: Database (on a copy first)

1. Restore a recent copy of the office database to a disposable instance and point
   `AOF_DATABASE_URL` at it. Do not use production.
2. Note the Alembic head and count the open cases. Then run `alembic upgrade head`.
   Every migration from `whats-new.md` §1 runs, ending at `e7f9a1b3c5d7`.
3. Check:
   - no `helix_*` tables are left (`\dt helix_*` is empty, and the `aof_*` tables exist);
   - stored roles read `AOF_*`;
   - checkpoint thread ids start with `aof:`.
4. Start the API on the copy. Open three open cases in the web app, one waiting at review if there is
   one. Approve one and check that it continues past the gate.
5. Run `alembic downgrade -1`, then `alembic upgrade head` again. Both must succeed.
6. Run `python scripts/aof_office_smoke.py --user <real id>` against the copy, with the new headers.

Check: steps 3–6 pass. Write the timings, because the release window needs them.
Commit any office migration fix.

## Phase 6: Release plan (written, not run)

Write `UPGRADE_RELEASE.md` for the user to run. Follow `renaming.md` "Order of the release",
filled in with the inventory's names:

1. **Before the release:**
   - add the `AOF_*` roles beside the old ones in the entitlement system;
   - add the `AOF_*` settings beside the old ones in the secret store;
   - make the proxy and bots send both header names;
   - update the Phoenix queries.
2. **At the release:** stop the scheduler, deploy the build, run `alembic upgrade head`, start
   it again, run the smoke test, and open one case end to end.
3. **After one clean business day:** remove the old roles, settings and header names.
4. **Rollback:** redeploy the previous build, then run `alembic downgrade d6e8f0a2b4c6`
   (the rename migration reverses itself), then restore the old settings. Test this once on the copy from Phase 5.
5. **What users notice:**
   - the new product name;
   - they choose their user and theme once more;
   - the new screens: Configurable steps, Data sets, Clocks, Child cases, and
     About Agent One Finance (`/pitch/`).

Check: the user has read the plan and agreed it.

## What to report after each phase

- what you changed (files), and what you did not do and why;
- the check's command and its output (pass or fail counts);
- new gaps and open questions, numbered;
- the next phase, waiting for approval.
