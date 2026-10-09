# RAID log

| Owner | Status | Last updated | Purpose |
|---|---|---|---|
| *(name)* | Draft | 9 Oct 2026 | Risks, assumptions, issues and dependencies |

| ID | Type | Description | Rating | Action | Owner |
|---|---|---|---|---|---|
| R1 | Risk | Prod not ready by 11 Dec | High | Raise platform and network requests in S0; track weekly | DevOps |
| R2 | Risk | Posting to MOTIF through FAS needs controls sign-off and FAS access in UAT | High | Agree posting rules in S1; controls story in S3 | BA / Risk |
| R3 | Risk | Late approvals (model, DPIA, penetration test, CAB) | High | Start in S0; each week late moves go-live by about a week | PM |
| R4 | Risk | MB Rec extra data arrives late | Medium | Extra checks stay off; go-live not blocked | BA |
| A1 | Assumption | Product Control available for set-up in S1–S2 and UAT in S4–S5 |  | Confirm with the Business | PM |
| A2 | Assumption | Users are already provisioned for interim skill testing |  |  | PM |
| I1 | Issue | The build deployment is failing (missing package in the image) | High | Fix in progress | DevOps |
| D1 | Dependency | MB Rec: extra data and end-of-day notification |  | Weekly session; dates in plan | PM |
| D2 | Dependency | FAS: test access in UAT and Prod connection |  | Dates in plan | PM |
| D3 | Dependency | Agent One team: session per capability per case |  | Design agreed in S0 | Architect |
