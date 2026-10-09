# E04 Data connections: MB Rec, MOTIF and FAS

| Owner | Status | Last updated | Purpose |
|---|---|---|---|
| *(name)* | Draft | 9 Oct 2026 | Requirements for this epic; one section per story |

| Jira epic | Component | Dates | Status |
|---|---|---|---|
| E04 | Connections | 6 Oct 2026 to 14 Dec 2026 | To Do |

**Objective:** Read breaks from MB Rec and bookings from MOTIF; post approved adjustments to MOTIF through FAS

**Deliverables:** MB Rec and MOTIF connections, MB Rec end-of-day trigger, FAS posting of approved adjustments, user roles, Prod connections

**Exit criteria:** Breaks load from MB Rec; an approved adjustment posts to MOTIF through FAS in UAT

**Dependencies:** MB Rec, MOTIF and FAS teams; network rules

## Stories

### E04-S31 MB Rec: request the extra data the checks need (long lead)

As a BA, I want MB Rec's extra data requested with dates, so that the extra checks can be turned on.

Book status, history by book, and breaks across books.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 2 | R1 Working version | 1 | Highest | BA | - | To Do |

**Acceptance criteria**

- Done when: MB Rec gives delivery dates

### E04-S32 MB Rec: read breaks and break history

As a Product Control reviewer, I want breaks and their history read from MB Rec, so that each case starts from the real breaks.

Read-only connection.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 3 | R1 Working version | 5 | Highest | Backend | UAT | To Do |

**Acceptance criteria**

- Given a book and date in MB Rec, when a case opens, then its breaks load read-only.
- Done when: Real breaks load into a case in UAT

**Blocked by:** E02-S12

### E04-S33 FAS: agree posting rules with Product Control and MOTIF

As a BA, I want the posting rules agreed, so that only the right adjustments are posted.

Which adjustments are posted, accounts and booking fields, limits, who releases.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 3 | R1 Working version | 2 | Highest | BA / Product Control | - | To Do |

**Acceptance criteria**

- Done when: Posting rules signed

### E04-S34 Give provisioned users their AOF roles and books

As a Product Control reviewer, I want my AOF role and books set, so that I see only my books.

Users are already provisioned; set who reviews, who releases and which books each sees.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 3 | R1 Working version | 3 | Highest | Backend | UAT | To Do |

**Acceptance criteria**

- Given a reviewer for book A, when they open the inbox, then they see only book A's cases.
- Done when: Users see only their books

### E04-S35 MB Rec: end-of-day notification opens a case

As a Product Control reviewer, I want a case opened automatically when MB Rec finishes a book, so that work is ready when I start.

When MB Rec finishes a book, AOF opens the case; late breaks open a follow-up.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 3 | High | Backend / MB Rec | UAT | To Do |

**Acceptance criteria**

- Given MB Rec finishes a book, when it sends its notification, then a case opens.
- Given a late break for an open book, when MB Rec notifies, then a follow-up case opens.
- Done when: Case opens automatically in UAT

**Blocked by:** E04-S32

### E04-S36 MOTIF: read trades, positions and booking events

As a Product Control reviewer, I want trades, positions and booking events read from MOTIF, so that breaks are explained from the booking side.

Read-only connection.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 5 | Highest | Backend | UAT | To Do |

**Acceptance criteria**

- Given a break, when it is investigated, then the MOTIF data used is shown on the case.
- Done when: MOTIF data available in UAT

**Blocked by:** E02-S12

### E04-S37 FAS: post approved adjustments to MOTIF

As a Product Control reviewer, I want approved adjustments posted to MOTIF through FAS, so that I do not re-key them.

Connect the FAS service. Only adjustments approved by a reviewer and released by a second person are posted; each is posted once.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 4 | R1 Working version | 8 | Highest | Backend | UAT | To Do |

**Acceptance criteria**

- Given an adjustment approved by a reviewer and released by a second person, when it is posted, then it reaches MOTIF through FAS.
- Given an adjustment already posted, when it is posted again, then the second post is refused.
- Given an adjustment not released, when anyone tries to post it, then nothing is posted.
- Done when: Approved adjustment posted to MOTIF in UAT; a second post is refused; audit shows who approved and released

**Blocked by:** E04-S33, E02-S12

### E04-S38 FAS: confirm each posted adjustment in MOTIF

As a Product Control reviewer, I want each posting confirmed in MOTIF, so that I know it landed.

Read back from MOTIF that the adjustment landed; flag any that did not.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 5 | R1 Working version | 3 | High | Backend | UAT | To Do |

**Acceptance criteria**

- Given a posted adjustment, when MOTIF is read back, then the case shows it confirmed, or flags it.
- Done when: Every UAT posting confirmed

**Blocked by:** E04-S37

### E04-S39 Connections in Prod before the freeze

As a platform engineer, I want MB Rec, MOTIF and FAS reachable from Prod by 10 Dec, so that the 5 Jan release needs no network change.

MB Rec, MOTIF and FAS reachable from Prod by 10 Dec.

| Sprint | Release | Points | Priority | Team | Environment | Status |
|---|---|---|---|---|---|---|
| Sprint 6 | R2 Go-live | 3 | Highest | DevOps | Prod | To Do |

**Acceptance criteria**

- Done when: All connections up in Prod

**Blocked by:** E02-S19

