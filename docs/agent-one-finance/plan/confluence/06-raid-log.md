# RAID log

| Owner | Status | Last updated | Purpose |
|---|---|---|---|
| *(name)* | Draft | 9 Oct 2026 | Risks, assumptions, issues and dependencies |

| ID | Type | Description | Rating | Action | Owner |
|---|---|---|---|---|---|
| R1 | Risk | Prod not ready by 10 Dec | High | Raise platform and network requests in Sprint 2; track weekly | DevOps |
| R2 | Risk | Posting to MOTIF through FAS needs controls sign-off and FAS access in UAT | High | Agree posting rules in Sprint 3; controls story in Sprint 5 | BA / Risk |
| R3 | Risk | Late approvals (TAC, ARB, CAF, CDO, DAIP, CARA, DPIA, CAB) | High | Artefact register from Sprint 2; forum dates booked now; each week late moves go-live by about a week | Governance lead |
| R6 | Risk | All approvals rest on one person | Medium | Register and packs kept in Confluence; a named backup for steerco weeks | PM |
| R7 | Risk | FOBO controllers' time for set-up, UAT and the parallel run not protected | High | Names and time agreed with the Business in Sprint 2 | PM |
| R4 | Risk | MB Rec extra data arrives late | Medium | Extra checks stay off; go-live not blocked | BA |
| R5 | Risk | Sprint 7 runs over the holidays | Medium | UAT cycle 2 starts 15 Dec; sign-offs and CAB request by 18 Dec | PM |
| A1 | Assumption | Named FOBO controllers available for set-up in Sprints 3–4, UAT in Sprints 6–7 and the parallel run in Sprint 8 |  | Confirm with the Business | PM |
| A2 | Assumption | The FOBO controllers are already provisioned for interim skill testing |  |  | PM |
| A3 | Assumption | One team member works full time on governance approvals |  |  | PM |
| I1 | Issue | The AOF orchestrator deployment on AWS is not yet healthy | High | Missing package fixed; own ECS service in Sprint 2; database migration history settled in Sprint 3 | DevOps |
| I2 | Issue | Converting each AOF release by hand lost styles and screens | High | Take each release with the sync tool from Sprint 3 | Frontend |
| D1 | Dependency | MB Rec: extra data and end-of-day notification |  | Weekly session; dates in plan | PM |
| D2 | Dependency | FAS: test access in UAT and Prod connection |  | Dates in plan | PM |
| D3 | Dependency | Agent One team: session per capability per case |  | Design agreed in Sprint 3 | Architect |
