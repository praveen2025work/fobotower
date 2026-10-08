/*
 * FOBO on Agent One Finance — C4 model for ARB and CDO review (2026-10-08).
 * Scope: the FOBO break-investigation use case only.
 * Render with Structurizr Lite:  docker run -it --rm -p 8080:8080 -v $PWD:/usr/local/structurizr structurizr/lite
 * Owners and the roles of Finance Portal, Workspaces and FAS are placeholders to confirm.
 */
workspace "FOBO on Agent One Finance" "Break investigation for Product Control, as configuration on a governed AI framework." {

    model {
        controller = person "Product Controller" "Checks the breaks at the checkpoint, decides each group, signs off by 11:00 next business day." "Product Control"
        desk = person "Desk, Operations, CATS support" "Answer questions asked from a case; own the tickets raised to them." "Business"
        owner = person "Capability owner" "Changes FOBO's configuration; a second owner approves." "Product Control"

        group "PC reporting application" {
            aof = softwareSystem "Agent One Finance" "Governed AI framework for Finance. FOBO runs on it as configuration: rules as code, the model for judgement, people decide." {
                web = container "Web console" "Inbox, case workspace, review and sign-off, configuration, audit." "React, Vite" "Web"
                api = container "API and workflow engine" "Runs every step and gate of a case; enforces roles, book scope, approvals." "Python, FastAPI, LangGraph" {
                    intake = component "Case intake" "Opens a case per book and COB from Masterbook Rec's event; follow-up cases for late breaks." "FastAPI"
                    engine = component "Workflow engine" "Runs the steps in order, pauses at the checkpoint and review, resumes from checkpoints." "LangGraph"
                    loadStep = component "Load and enrich steps" "Reads Masterbook Rec's breaks and MOTIF's snapshots per instrument; no re-matching." "Python"
                    algos = component "Algorithm steps" "Evidence only: equal-and-opposite, split bookings, same break in other books, near-identical names, trend, unusual size." "Python"
                    resolve = component "Reference resolver" "Book to desk to escalation team, as of the COB." "Knowledge graph"
                    playbook = component "Playbook rules engine" "FOBO's skill as configuration: checks C1-C6, tests FO-1..8 and BO-1..6, findings, categories, verdict table, guards R2, R5, P1." "Python, safe expressions"
                    reasoner = component "Reasoner and model adapter" "Asks the model about judgement groups only, in the skill's answer sections; validates every figure against the data." "Agent SDK adapter"
                    review = component "Review and decisions" "Maker-checker, confirmations for unset thresholds, the sign-off checklist, questions to desks." "Python"
                    record = component "Record and follow-up" "Tickets to owning teams, decisions as priors, next-COB re-test of POST and MONITOR." "Python"
                    config = component "Configuration and versions" "Capability and FOBO group versions, four-eyes approval, eval replay before change." "Python"
                    audit = component "Audit and evidence" "Tool-call audit, decision history, evidence pack PDF, Excel export." "Python"
                }
                gateway = container "MCP gateway" "The only path to bank systems: allow-list, book scope, masking, audit row per call." "Python, MCP client" "Gateway"
                scheduler = container "Scheduler" "Deadlines, reminders, chasing questions, timeouts." "Python"
                store = container "Case store" "Cases, items, decisions, tool-call audit, versions, knowledge graph, workflow checkpoints." "PostgreSQL" "Database"
                files = container "Configuration files" "break-investigation capability, FOBO Prime and Rates groups, reference lineage." "YAML in Git" "Files"
            }
            mbrec = softwareSystem "Masterbook Rec" "Reconciles CATS to MOTIF at end of day; raises each book's breaks; sends the end-of-day event." "Existing"
            portal = softwareSystem "Finance Portal" "Finance users' front door: single sign-on and navigation." "Existing"
            workspaces = softwareSystem "Workspaces" "Controllers' working area: links, notifications, evidence packs." "Existing"
            fas = softwareSystem "FAS" "Finance accounting system; books approved adjustments. No direct link in this release." "Existing"
        }

        cats = softwareSystem "CATS" "Front-office trades and positions." "Existing"
        motif = softwareSystem "MOTIF" "Back-office positions, booking events, FO/BO snapshots." "Existing"
        agentOne = softwareSystem "Agent One" "The office's governed model access (Claude Agent SDK)." "Existing"
        entitlement = softwareSystem "Entitlement service" "Users' roles and the books each may see." "Existing"
        ticketing = softwareSystem "Ticketing" "Tickets to owning teams." "Existing"
        teams = softwareSystem "Teams and email" "Notifications and questions to desks." "Existing"
        phoenix = softwareSystem "Phoenix" "Traces, one per case run, payloads masked." "Existing"

        # System context
        controller -> portal "Signs in"
        portal -> aof "Opens, with the signed-in user"
        controller -> aof "Reviews and signs off breaks"
        owner -> aof "Changes FOBO's configuration"
        desk -> aof "Answers questions"
        mbrec -> aof "End-of-day event per book and COB"
        aof -> mbrec "Reads breaks, break history" "MCP, read"
        aof -> motif "Reads snapshots, booking events, positions, trades" "MCP, read"
        aof -> cats "Reads trades" "MCP, read"
        aof -> agentOne "Asks about judgement groups" "Agent SDK"
        aof -> entitlement "Roles and book scope" "HTTPS"
        aof -> ticketing "Raises tickets after a person decides" "MCP, write"
        aof -> teams "Notifications and questions" "Webhook"
        aof -> workspaces "Links and evidence packs"
        aof -> phoenix "Traces" "OpenTelemetry"
        controller -> workspaces "Works the day"
        ticketing -> fas "Operations books approved adjustments (outside Agent One Finance)"

        # Containers
        controller -> web "Uses" "HTTPS via SSO proxy"
        web -> api "Calls" "JSON/HTTPS"
        mbrec -> api "Posts end-of-day event" "HTTPS, event secret"
        api -> gateway "Every system call"
        gateway -> mbrec "Breaks, history, all books" "MCP"
        gateway -> motif "Snapshots, events, positions, trades" "MCP"
        gateway -> cats "Trades" "MCP"
        gateway -> ticketing "Create ticket" "MCP, write"
        api -> agentOne "Judgement groups" "Agent SDK"
        api -> store "Reads and writes" "SQL"
        api -> files "Reads at sync; owners approve versions"
        api -> entitlement "Roles and scope" "HTTPS"
        api -> phoenix "Traces" "OTLP"
        scheduler -> store "Deadlines and timeouts" "SQL"
        scheduler -> teams "Reminders and escalations" "Webhook"

        # Components
        mbrec -> intake "End-of-day event"
        intake -> engine "Starts the run"
        engine -> loadStep "load, enrich"
        loadStep -> gateway "mbrec.breaks, motif.break_snapshots"
        engine -> algos "history, offsets, split bookings, systemic, near names, trend, unusual"
        algos -> gateway "Reads data sets"
        engine -> resolve "resolve"
        engine -> playbook "classify, group"
        engine -> reasoner "reason, after the checkpoint"
        reasoner -> agentOne "One group at a time"
        reasoner -> gateway "Model's tool calls"
        engine -> review "review"
        web -> review "Decisions, checklist, questions"
        engine -> record "record"
        record -> gateway "ticketing.create_ticket"
        config -> files "Versions"
        engine -> store "Checkpoints"
        audit -> store "Reads"
        gateway -> store "Audit row per call"
    }

    views {
        systemContext aof "Context" "C4 level 1: FOBO on Agent One Finance in the PC reporting application." {
            include *
            autolayout lr
        }
        container aof "Containers" "C4 level 2: Agent One Finance's containers for FOBO." {
            include *
            autolayout lr
        }
        component api "Components" "C4 level 3: the API components that run a FOBO break investigation." {
            include *
            autolayout lr
        }
        dynamic api "FOBORun" "One FOBO run, Masterbook Rec's event to sign-off." {
            mbrec -> intake "1. End-of-day event for a book and COB"
            intake -> engine "2. Opens the case"
            engine -> loadStep "3. Load breaks, enrich with snapshots"
            engine -> algos "4. Evidence: offsets, split bookings, other books, near names, trend"
            engine -> resolve "5. Book to desk to team, as of the COB"
            engine -> playbook "6. Checks, tests, categories, verdict table, guards"
            controller -> web "7. Checkpoint: approves before any model call"
            engine -> reasoner "8. Judgement groups only"
            reasoner -> agentOne "9. Model investigates with allowed tools"
            controller -> web "10. Signs off each group"
            engine -> record "11. Tickets; next COB re-tests the decisions"
            autolayout lr
        }
        styles {
            element "Person" {
                shape Person
                background #08427b
                color #ffffff
            }
            element "Software System" {
                background #1168bd
                color #ffffff
            }
            element "Existing" {
                background #999999
                color #ffffff
            }
            element "Container" {
                background #438dd5
                color #ffffff
            }
            element "Component" {
                background #85bbf0
                color #000000
            }
            element "Database" {
                shape Cylinder
            }
            element "Web" {
                shape WebBrowser
            }
            element "Files" {
                shape Folder
            }
        }
    }
}
