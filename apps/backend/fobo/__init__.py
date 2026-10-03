import asyncio
import sys

# psycopg's async mode (used by the LangGraph Postgres checkpointer) cannot run
# on Windows' default ProactorEventLoop. This covers asyncio.run() in the CLIs,
# the scripts and pytest; uvicorn picks its own loop, so the server is started
# with `--loop asyncio:SelectorEventLoop` (see README, "Running on Windows").
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
