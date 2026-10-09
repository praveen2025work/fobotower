# Running the AOF API on AWS: option A and option B

**For:** DevOps, the person running the AOF work, and office Claude.

**Recommendation:**
- **Option A, AOF as its own ECS service.** This is how the original FOBO backend ran.
- **Option B is the fallback.** Use it only if A's internal network is not ready by the end of Sprint 3 (2 Nov). It
  must not block the 30 Nov working version. Move to A before Prod is built (10 Dec).

Today Agent One runs as two ECS tasks: `agentoneapi-family` (the Agent One API plus 7 MCP sidecars) and
`sftfagent-family` (the frontend). A third task, `agentone-fobo-family`, was the original FOBO backend.

---

## The two options

**Option A: its own service**

```
sftfagent-family (frontend :3000)
  /api/finance/*  rewrite ─>  agentoneapi-family: agentoneapi :8000  /finance/api/*
                                  checks the BAM sign-on
                                  ─> internal address ─>  agentone-aof-family: aof-backend :8300  /api/*
```

**Option B: one more container in the Agent One API task**

```
sftfagent-family (frontend :3000)
  /api/finance/*  rewrite ─>  agentoneapi-family: agentoneapi :8000  /finance/api/*
                                  checks the BAM sign-on
                                  ─> localhost ─>  agentoneapi-family: aof-backend :8300  /api/*   (same task)
```

In both:
- The browser never reaches AOF directly.
- `agentoneapi` adds `X-AOF-User` (the signed-in bank id) and `X-AOF-Proxy-Secret`. With `AOF_TRUSTED_PROXY_SECRET`
  set, AOF refuses any call without them.
- The frontend does not change.

| | A. Own service | B. Container in `agentoneapi-family` |
|---|---|---|
| ECS | New family `agentone-aof-family`, new service | One more container in `ecs-task-definition.json` |
| How `agentoneapi` reaches AOF | Internal address (internal load balancer or service discovery) | `http://localhost:8300` |
| An AOF release | Redeploys AOF only | Redeploys the whole task: the API and the 7 MCP sidecars |
| An Agent One API release | AOF keeps running | Restarts AOF; case runs in flight restart (they recover) |
| Scaling | AOF on its own (1 task in UAT, 2 in Prod) | Moves with the API task count |
| Approvals (CARA, CAF, CAB) | One component: one image, one service | Part of the Agent One API change |
| DevOps work | Task definition, service, security group, internal address, pipeline deploy step (copy the FOBO set-up) | Edit one task definition, raise its CPU and memory |
| Rough effort | 3–5 days, more if the network request is slow | 1–2 days |

---

## Shared steps (both options)

These come first, whichever option you choose.

| # | Step | Who | Detail |
|---|---|---|---|
| S1 | Code and image | Office Claude (Prompt A) |<ul><li>`Dockerfile.helix` = `office/hosting/Dockerfile.aof`, with the base image and pip mirror from `app/Dockerfile`.</li><li>Add `psycopg[binary,pool]>=3.2` and `mcp>=2.2,<3` to `app/requirements.txt`.</li><li>Copy `aof_alembic.ini`.</li><li>`.gitlab-ci-aof.yml` builds and pushes `financeagent-aof-backend` to Nexus, with the Wiz scan.</li></ul> |
| S2 | Secrets | DevOps | In Secrets Manager:<ul><li>the AOF database secret (keys host, port, dbname, username, password);</li><li>a new `aof-proxy-secret`, a random string. It is given to both `agentoneapi` and `aof-backend`.</li></ul> |
| S3 | Forwarding route in the Agent One API | Office Claude | `/finance/api/*` checks the sign-on, then calls `AOF_API_URL` + `/api/*` with the two headers. Reference: `office/hosting/aof_forward.py`. `api/routes/aof_cases.py` and `aof_notifications.py` stop importing AOF code, and call the AOF service instead (or are replaced by the route), so AOF runs in one place only. |
| S4 | Migrations | DevOps | Before each deployment, a one-off task with the new AOF image and the command `alembic -c aof_alembic.ini upgrade head`. Run once; it is not part of the service. Do the `alembic_version` check (README section 4) before the first run. |

### The AOF container: the same in both options

```json
{
  "name": "aof-backend",
  "image": "<nexus>/financeagent-aof-backend:<tag>",
  "essential": true,
  "portMappings": [{ "containerPort": 8300, "protocol": "tcp" }],
  "command": ["uvicorn", "agent_one_finance.web.main:app", "--host", "0.0.0.0", "--port", "8300", "--workers", "3", "--proxy-headers"],
  "environment": [
    { "name": "AOF_ENV_NAME", "value": "uat" },
    { "name": "AOF_LLM_ADAPTER", "value": "<as the FOBO backend had it>" },
    { "name": "AOF_CONSOLE_URL", "value": "https://<agent one host>/agentone/finance" },
    { "name": "AOF_CONSOLE_ORIGIN", "value": "https://<agent one host>" },
    { "name": "PHOENIX_COLLECTOR_ENDPOINT", "value": "<as the other agent services>" }
  ],
  "secrets": [
    { "name": "AOF_DATABASE_HOST", "valueFrom": "<aof db secret arn>:host::" },
    { "name": "AOF_DATABASE_PORT", "valueFrom": "<aof db secret arn>:port::" },
    { "name": "AOF_DATABASE_NAME", "valueFrom": "<aof db secret arn>:dbname::" },
    { "name": "AOF_DATABASE_USER", "valueFrom": "<aof db secret arn>:username::" },
    { "name": "AOF_DATABASE_PASSWORD", "valueFrom": "<aof db secret arn>:password::" },
    { "name": "AOF_TRUSTED_PROXY_SECRET", "valueFrom": "<aof-proxy-secret arn>" }
  ],
  "healthCheck": {
    "command": ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8300/health', timeout=4)\" || exit 1"],
    "interval": 30, "timeout": 5, "retries": 3, "startPeriod": 60
  },
  "logConfiguration": {
    "logDriver": "awslogs",
    "options": { "awslogs-group": "<log group>", "awslogs-region": "<region>", "awslogs-stream-prefix": "aof" }
  }
}
```

- `AOF_CONFIG_DIR` and `AOF_DOCUMENTS_DIR` are set by the image.
- The full list of settings is in README section 5.
- Use the same roles, account and region values as `ecs-task-definition-fobo.json`.

---

## Option A: its own ECS service (recommended)

| # | Step | Who | Detail |
|---|---|---|---|
| A1 | Task definition | Office Claude | `ecs-task-definition-aof.json`, copied from `ecs-task-definition-fobo.json`: family `agentone-aof-family`, the container above, the same execution and task roles. Starting size: 1 vCPU and 2 GB, raised if the controllers' end-of-day volume needs it. |
| A2 | Security group | DevOps | Inbound on 8300 **only from the `agentoneapi` tasks' security group** (and the internal load balancer, if one is used). Outbound to the AOF database, MB Rec, MOTIF, FAS, the LLM gateway and Phoenix. |
| A3 | Internal address | DevOps | One of:<ul><li>an **internal** load balancer target group on port 8300, health check path `/health`. The FOBO set-up (`infrastructure/fobo-alb-rules.json`) is the pattern, but the load balancer must be internal.</li><li>ECS service discovery: for example `aof-backend.<namespace>:8300`.</li></ul> |
| A4 | ECS service | DevOps | Service `aof-backend` in the same cluster and subnets as FOBO. Desired count 1 in UAT and 2 in Prod; rolling deployment. Several tasks are safe: each scheduled run is claimed once, and each case is locked while it runs. |
| A5 | Pipeline deploy step | DevOps | `.gitlab-ci-aof.yml`: build, then the migration task (S4), then update the `aof-backend` service to the new image. Triggered by changes to `agent_one_finance/`, `aof_migrations/`, `aof_alembic.ini`, `config/agent-one-finance/` and `seed_data/aof_documents/`. |
| A6 | Point the API at AOF | DevOps | On `agentoneapi`, set `AOF_API_URL=<the internal address from A3>` and `AOF_TRUSTED_PROXY_SECRET` (secret). Deploy with the S3 route. |

Release order the first time: S1 → S2 → S4 → A1–A5 (AOF up, `/health` green) → A6 → checks.

Rollback:
- AOF: point the `aof-backend` service at the previous image.
- The API change: roll `agentoneapi` back to the previous task definition revision.

---

## Option B: a container in `agentoneapi-family` (fallback)

| # | Step | Who | Detail |
|---|---|---|---|
| B1 | Task definition | Office Claude | In `ecs-task-definition.json`, add the container above as a ninth container, with `"essential": false`, so a failing AOF does not stop the API. Raise the task's CPU and memory by 1 vCPU and 2 GB (on Fargate, pick a valid size). |
| B2 | Settings on `agentoneapi` | Office Claude | `AOF_API_URL=http://localhost:8300` and `AOF_TRUSTED_PROXY_SECRET` (secret) |
| B3 | Security group | DevOps | No change for AOF (it is reached on localhost). Outbound to the AOF database, MB Rec, MOTIF, FAS, the LLM gateway and Phoenix must be allowed for the task. |
| B4 | Migration task | DevOps | A small task definition `agentone-aof-migrate` (one container, the AOF image, the command `alembic -c aof_alembic.ini upgrade head`), run before each deployment. It cannot be part of the eight-container task. |
| B5 | Pipeline | DevOps | The AOF image is built by `.gitlab-ci-aof.yml`. A release needs a new revision of `ecs-task-definition.json` with the new AOF image tag, deployed through the API pipeline (`.gitlab-ci-api.yml`). |

Release order the first time: S1 → S2 → S4 → B1, B2 and S3 in one API deployment → checks.

Rollback: roll `agentoneapi` back to the previous task definition revision. That rolls back the API too.

### Moving from B to A later

1. Do A1–A5.
2. Change `AOF_API_URL` on `agentoneapi` to the internal address.
3. Remove the `aof-backend` container from `ecs-task-definition.json` and lower the task size again.

No code changes: the image, settings and forwarding route are the same.

---

## Checks after each deployment (both)

```bash
# 1. AOF is up (from inside the agentoneapi task: ECS Exec, or the task's logs)
curl -s $AOF_API_URL/health                      # {"status":"ok"}

# 2. AOF refuses calls that skip the front door
curl -s -o /dev/null -w "%{http_code}\n" $AOF_API_URL/api/me -H "X-AOF-User: anyone"   # 401

# 3. Through the front door, signed in as a FOBO controller
open https://<agent one host>/agentone/finance     # inbox loads, left menu shows its icons
```

Logs: the `aof` stream prefix in the log group. Migration results appear in the migration task's log.

## Decision and timing

| When | What |
|---|---|
| Sprint 2 (now) | Choose A. DevOps raises the security group and internal-address requests (the long-lead part). |
| Sprint 3 (by 2 Nov) | A1–A6 in UAT. If the network is not ready, run B in UAT instead and keep going with A. |
| By 30 Nov | Working version on AOF in UAT (A, or B for now) |
| By 10 Dec | Prod built with **A** |
| After go-live | Retire FOBO's `Dockerfile.fobo`, `ecs-task-definition-fobo.json` and `fobo-alb-rules.json` |
