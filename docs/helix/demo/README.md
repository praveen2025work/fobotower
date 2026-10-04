# Helix: executive demo (CIO and accounting MDs)

**Video:** [`helix-demo.mp4`](helix-demo.mp4), 3 min 06 s, 1280×720, with voice-over and
on-screen captions. It was recorded from the running app on 2026-10-04: the dev stack,
dev data, and the deterministic stub model (no live model calls).

## Running order

| Time | Scene | Message to land |
|---|---|---|
| 0:00 | Title | One governed platform: AI does the legwork, people make every decision |
| 0:12 | The problem | Breaks are investigated by hand: about 12 min each (FOBO's own basis), and every team builds its own tooling |
| 0:30 | Inbox | The work is done before the controller arrives (scheduled at 06:30, matched and classified) |
| 0:45 | FOBO Prime case | The business's own playbook decides: checks, tests, verdict table, owner. Unconfirmed thresholds are flagged, not assumed. |
| 1:11 | Guard and evidence | A front-office cause never posts (enforced in code). Every figure traces to a system call; anything untraceable goes to a person. |
| 1:27 | Ask about this case | Plain-English questions, answered from this case's data only, and audited |
| 1:37 | Sign-off | One decision per pattern; sign-off in seconds; evidence pack ready for audit |
| 1:49 | Rates group | Same engine and playbook, with the team's own books, thresholds and reviewers. A new team is configuration. |
| 2:02 | Authoring | New work (accruals, substantiation, intercompany) is drafted, checked, and goes live on a second owner's approval |
| 2:16 | Operations | Entitlements on every call, masking, audit, cost caps, one-click off switches |
| 2:34 | What it means | Investigating becomes reviewing; one decision per pattern; same controls everywhere; use cases as configuration |
| 2:52 | Next steps | Pilot on FOBO Prime and Rates, measure against the 12-minute basis, then accruals and substantiation |

## How to use it in the meeting

1. Play the video, or pause it at 1:37 and do the sign-off live from the user guide
   steps.
2. Then put up the time-saving arithmetic with **your own volumes**. The video's line
   "200 breaks a day × 12 min = 40 hours" is shown as *illustrative*. It is arithmetic on
   FOBO's 12-minute basis, not a measured result.
3. The platform's own **Overview → Hours saved (30 days)** tile shows the measured figure
   and its basis: items grouped into decisions × the declared manual minutes. In the pilot,
   that tile is the number to report.

## Likely questions

| Question | Answer |
|---|---|
| *Can the AI post something wrong?* | No. It only proposes. A reviewer approves every group, and a write-back needs a second person's release. Guards in code (e.g. R2) override the model, and the validate gate escalates any figure that does not trace to source data. |
| *Is our data safe with the model?* | Every data access goes through the gateway, which applies the caller's entitlements and data scope, and audits each call. Account numbers are masked and counterparties pseudonymized before the model sees anything. |
| *Which model and where does it run?* | In the office: the Claude Agent SDK, through the office agent platform. Traces go to Phoenix. The demo used a deterministic stand-in. |
| *What does it cost to run?* | Model spend is recorded per case, with caps per case and per day. Over a cap, the work goes to people. |
| *How is this different from the office agent platform?* | It builds on it. It uses the platform's MCP connectors, plugins and RAG, and adds the workflow, playbooks, four-eyes control, evidence and audit that accounting needs. |
| *How long to onboard a new process?* | If its systems are already connected: a configuration file, checked by the platform, approved by a second owner. A new system needs an MCP connector, onboarded once by the Helix team. |
| *What happens to FOBO?* | FOBO keeps running unchanged. Its rules run on Helix as configuration (Prime and Rates), so it can move across when the team chooses. |
| *How do we know it agrees with our people?* | Evals replay past decided cases on any new version, without writing anything, and report agreement before it goes live. |

## Re-making the video

The scene scripts used to make it are in this folder:

| File | Holds |
|---|---|
| `scenes.json` | Narration per scene |
| `record-scenes.mjs` | Playwright recording with captions and highlights |
| `mux-scenes.py` | Adds the voice-over and encodes each scene |

The voice-over used a local Piper text-to-speech voice (`en_GB-alan-medium`), so no
content left the machine. To use a human voice, record each scene's line over the same
timings and rerun the mux step.
