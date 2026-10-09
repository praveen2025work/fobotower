# office/: Agent One Finance in the office's shape

| Here | What it is |
|---|---|
| `aos-frontend/` | The console converted for the office's Agent One frontend (Next.js pages under `/finance`, the console code in `src/app/finance/_aof`, JSX, styles scoped to `#aof-root`). Made by `apps/web/office/convert.mjs`; do not edit here. |
| `aof_sync.py` | Copies `aos-frontend/` and the AOF backend into the office repos, keeping the office's own changes. |
| `hosting/` | Templates for running the AOF API on AWS next to the Agent One API: the image, the migration settings, and the Agent One API's forwarding route. |

How to use them, in one guide: [`docs/agent-one-finance/office/conversion-guide.md`](../docs/agent-one-finance/office/conversion-guide.md).
