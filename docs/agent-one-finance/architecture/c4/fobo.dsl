/*
 * FOBO on Agent One Finance — C4 model for ARB and CDO review (version 2, 2026-10-13).
 * Scope: FOBO break investigation per named P&L (NPL), and the Balance rec capability beside it.
 * Render with Structurizr Lite:  docker run -it --rm -p 8080:8080 -v $PWD:/usr/local/structurizr structurizr/lite
 * The same views, drawn for reading, are in fobo-c4-architecture.html in this folder.
 */
workspace "FOBO on Agent One Finance" "Break investigation per named P&L, as configuration on a governed AI framework." {

    model {
        controller = person "FOBO controller" "PC user. Checks the work at the tollgate, decides each group and signs off; a second controller releases postings." "Person"
        owner = person "Capability owner" "Changes an NPL config; a second owner approves." "Person"

        aof = softwareSystem "Agent One Finance (AOF)" "Runs FOBO and Balance rec as Helix capabilities: rules as configuration, the model only for judgement, people decide." {
            api = container "AOF API and Helix engine" "Takes MB Rec's notifications and runs every case: load, checks, tollgate, model, review, record, post. Enforces roles, NPL scope and approvals. Holds the Helix capabilities: FOBO break investigation (a config per NPL) and Balance rec." "Python, FastAPI, LangGraph; its own ECS service"
            gateway = container "MCP gateway" "The only way out to bank systems: allow-list, NPL scope, masking, an audit row per call." "Python, MCP client" "Gateway"
            database = container "AOF database" "Cases, decisions, audit, capability and config versions, run checkpoints." "PostgreSQL with pgvector, on AWS" "Database"
            phoenix = container "Phoenix" "One trace per case run, payloads masked." "OpenTelemetry"
        }

        agentOne = softwareSystem "Agent One" "Hosts the AOF console at /agentone/finance, signs users in (BAM), forwards their requests to AOF with the user and a shared secret, and gives AOF its model access." "Existing"

        group "PC Ramp / FinPortal" {
            mbrec = softwareSystem "MB Rec" "Reconciles CATS to MOTIF; sends one notification per NPL and COB; MCP server for breaks, master book status and FO/BO data." "Existing"
            entitlements = softwareSystem "PC Ramp entitlements" "Entitlement URL: each user's roles and the NPLs they may see." "Existing"
        }
        fas = softwareSystem "FAS" "MCP server: validates approved adjustments and posts them into MOTIF." "Existing"
        motif = softwareSystem "MOTIF" "Back-office ledger. Receives adjustments from FAS; MCP server for balances (Balance rec)." "Existing"

        # System context
        controller -> agentOne "A. Uses the AOF console" "HTTPS, BAM sign-on"
        controller -> aof "Decides and signs off; releases postings"
        owner -> aof "Changes NPL configs"
        mbrec -> aof "Notifies: one NPL and COB" "HTTPS, event secret"
        aof -> mbrec "Reads breaks, master book status, FO/BO data" "MCP, read"
        aof -> entitlements "Who may see which NPL" "HTTPS"
        aof -> agentOne "Asks the model, judgement only" "Agent SDK"
        aof -> fas "Posts approved adjustments, after sign-off and release" "MCP, write"
        aof -> motif "Reads balances, Balance rec only" "MCP, read"
        fas -> motif "Books the adjustment"

        # Containers (letters match the interface table in the HTML page)
        agentOne -> api "B. Forwards each request with the user" "HTTPS, shared secret"
        mbrec -> api "C. Notification per NPL and COB" "HTTPS, event secret"
        api -> entitlements "D. Roles and NPLs, cached 60 seconds" "HTTPS"
        api -> agentOne "E. Model: one group at a time, after the tollgate" "Agent SDK"
        gateway -> mbrec "F. Breaks, master book status, FO/BO data" "MCP, read"
        gateway -> fas "G. Approved adjustments, after release" "MCP, write"
        gateway -> motif "H. Balances, for Balance rec" "MCP, read"
        api -> database "J. Reads and writes" "SQL"
        api -> phoenix "K. Traces" "OpenTelemetry"
        api -> gateway "L. Every call to a bank system" "In process"
    }

    views {
        systemContext aof "Context" "C4 level 1: MB Rec starts each NPL case; AOF writes to MOTIF only through FAS." {
            include *
            autolayout lr
        }
        container aof "Containers" "C4 level 2: every call out of AOF goes through the MCP gateway; only FAS writes to MOTIF." {
            include *
            autolayout lr
        }
        dynamic aof "NPLRun" "One NPL run: from MB Rec's notification to the adjustment in MOTIF." {
            mbrec -> api "1. Notification for an NPL and COB"
            api -> gateway "2-3. Opens the case on the NPL's config; reads through the gateway"
            gateway -> mbrec "3. Breaks, master book status, FO/BO data"
            api -> entitlements "5. Who may see the NPL"
            controller -> agentOne "6. Tollgate: checks the breaks and the sorting"
            agentOne -> api "6. Continues the run"
            api -> agentOne "7. Model: only what the checks could not explain"
            controller -> agentOne "8-9. Signs off; a second controller releases"
            api -> gateway "10. Posts the approved adjustments"
            gateway -> fas "10. FAS validates, then posts once"
            fas -> motif "11. Books the adjustment"
            autolayout lr
        }
        styles {
            element "Person" {
                shape Person
                background #13a37a
                color #ffffff
            }
            element "Software System" {
                background #1f6fd1
                color #ffffff
            }
            element "Existing" {
                background #999999
                color #ffffff
            }
            element "Container" {
                background #5b9bf0
                color #ffffff
            }
            element "Database" {
                shape Cylinder
            }
            element "Web" {
                shape WebBrowser
            }
            element "Gateway" {
                shape Hexagon
            }
        }
    }
}
