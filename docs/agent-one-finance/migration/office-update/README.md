# Updating an office copy that already runs Agent One Finance

**For:** an office repo that already has **Agent One Finance** (new names, any version from
06 Oct 2026 onwards), being brought up to the latest upstream. If the office copy is still named
Helix, use the [`upgrade-to-aof`](../office-claude/upgrade-to-aof/SKILL.md) skill instead.

What changed and what each change needs in the office is in [`../whats-new.md`](../whats-new.md),
sections 1a onwards. **The updates from 06 to 08 Oct need no database migration and no new
settings.** FOBO's answers are unchanged.

## 0. Build the package (outside the office)

On a machine with this repo's full git history:

```bash
python apps/backend/scripts/aof_office_update.py --out aof-update
zip -r aof-update.zip aof-update
```

| In the package | What it is |
|---|---|
| `which-version.py` + `versions.json` | Finds the exact upstream version the office copy matches. Needs only Python 3, not git, and changes nothing. |
| `patches/from-<version>.patch` | One patch from each upstream version since 06 Oct to the latest. Demo screenshots and PDFs are left out. |
| `README.md` | This page. |

Carry the zip into the office through the bank's approved transfer route.

## 1. Find the office's version

**By hand:** look at the last `## 1…` section of `docs/agent-one-finance/migration/whats-new.md`
in the office repo.

| Last section | The office copy is at |
|---|---|
| no file | before 06 Oct 17:41: use the `upgrade-to-aof` skill |
| `## 1.` | 06 Oct 17:41 to 07 Oct (`c762a2b` … `e291591`) |
| `## 1a` | 08 Oct, algorithm steps (`28b1614` … `87bbeaf`) |
| `## 1b` | 08 Oct, skill session (`4ad9156` … `2a9e6f4`) |
| `## 1c` | 08 Oct, skill simulation or the console work after it (`cbe6b66` … `ee5b2f0`) |
| `## 1d` | 08 Oct, up to date as of `dbaac6f` |

**Exact version, with the script:**

```bash
python3 which-version.py /path/to/office/repo
```

It prints:

- the closest upstream version;
- the patch to apply;
- the files that differ from that version. These are usually the office's own edits, such as
  `connectors.yaml` or `llm_agent_sdk.py`. Keep this output: Claude needs it in step 3.

## 2. Prepare the office repo (5 minutes)

1. Unzip the package **outside** the office repo, for example `~/aof-update`.
2. Create a branch: `git checkout -b aof-update`. Never work on the office's main branch.
3. If you have already copied files in by hand, commit that copy on the branch first
   (`git add -A && git commit -m "upstream copy, unmerged"`). That gives Claude a clean diff to
   review against.

## 3. The prompt for office Claude Code

Fill in the three `<…>` and paste:

> We are bringing our office copy of Agent One Finance up to date with upstream. The update
> package is at `<path>/aof-update`; read its `README.md` first, then
> `docs/agent-one-finance/migration/whats-new.md` (sections 1a onwards) and
> `docs/agent-one-finance/migration/styles.md`.
>
> `which-version.py` says our copy is at `<version>` and these files differ from it: `<paste the list>`.
>
> Work on the branch `aof-update` only. Do not touch any database, deployment, secret or the main branch.
>
> 1. **Apply.** Run `git apply --check -3 <path>/aof-update/patches/from-<version>.patch`, show me
>    the result, and stop. Once I agree, apply it.
>    *(If I already copied the files in by hand, skip this step. Instead, review `git diff HEAD~1`
>    for anything the copy overwrote that was ours.)*
> 2. **Merge office files by hand.** Keep ours and add upstream's new parts:
>    - `config/agent-one-finance/connectors.yaml`: keep our URLs, `headers_env` and tools. Add the
>      new tools `mbrec.book_status`, `mbrec.break_history_book`, `mbrec.breaks_all`,
>      `cats.pnl_components`, `motif.pnl_components`, `secref.corporate_actions`,
>      `secref.bond_metadata` and the `secref` connector, *commented out* with a TODO for each
>      system team until the tools exist in our environment.
>    - `apps/backend/agent_one_finance/llm_agent_sdk.py`: take upstream's file and put our `_run`
>      back exactly as it was.
>    - FOBO capability and group YAMLs: keep our thresholds and roles, and take the new steps.
>      Until MB Rec provides `break_history_book` and `breaks_all`, leave the steps that need them
>      out of `steps`.
>    - Any other file in the list above: show me both versions and ask.
> 3. **Office screens and styles.** Run `npm run check:styles` in `apps/web`. If our own screens
>    use yellow, amber, purple or sky colours, change them as `styles.md` says. Don't edit the
>    upstream style files or the style manifest.
> 4. **Test.** Run `pytest -q` in `apps/backend`. In `apps/web`, run `npx tsc --noEmit -p .`,
>    `npx vitest run` and `npm run check:styles`. Report the counts. Upstream has 775 and 93
>    passing at `dbaac6f`. Fix only failures caused by our merge; if an upstream test fails because
>    of our environment, tell me why instead of changing the test.
> 5. **Summary.** Commit with a clear message. Then list for me: what was applied, what you merged
>    by hand and how, which connector tools are waiting on other teams, and the test results.
>    Stop there; I will raise the pull request.
>
> Stop after each numbered step for my OK.

## 4. After Claude, before merging

1. **Read Claude's summary and the diff** of `connectors.yaml` and `llm_agent_sdk.py` yourself.
   Those two hold the office specifics.
2. **Run the app on UAT** and click through:
   - a FOBO case;
   - **How it runs**;
   - **Evals**: run one for FOBO Prime and expect a lower but honest agreement figure, because the
     old figure was overstated (section 1d);
   - **Operations** signed in as platform support.
3. **Approve the new FOBO capability and group versions** in the console (Versions tab).
   Configuration changes go live only after a second owner approves them.
4. **Ask the system teams for the new tools:**
   - MB Rec: `book_status`, `break_history_book`, `breaks_all`;
   - CATS and MOTIF: `pnl_components`;
   - security reference data: `corporate_actions`, `bond_metadata`.

   Turn on the matching steps as each tool arrives.
5. **Raise the pull request** through the normal review.

If Claude proposes a database migration or a new environment setting for the 06–08 Oct updates,
stop. None is needed. Check against `whats-new.md` first.

## Known deployment issue: `greenlet` missing from the image

If the image builds but the deployment fails on its first database call, see
[`fix-greenlet-deploy.md`](fix-greenlet-deploy.md). It is a one-line dependency fix with steps for
office Claude.

## How this was proved

Four mock office copies were tested. They had no shared git history, were made at `e291591`,
`4ad9156`, `cbe6b66` and `b3073ab`, and each had an office edit in `connectors.yaml`.

- `which-version.py` picked the right version every time and listed `connectors.yaml` as the one
  office file.
- Each patch applied with `git apply -3` with no conflict.
- The result equalled upstream `dbaac6f` in all 653 files except `connectors.yaml`, which kept
  the office edit.
