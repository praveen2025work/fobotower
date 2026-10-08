# Fix: deployment fails because `greenlet` is missing from the API image

**For:** office Claude Code, working in the repo that builds `financeagent-api`.

## The problem

- The image `financeagent-api:0.1.502-SNAPSHOT` builds fine, but the deployment fails.
- DevOps found the root cause: the image is missing the Python package **`greenlet`**.

## Why

- The backend uses SQLAlchemy's **async** engine (`apps/backend/agent_one_finance/db.py`:
  `create_async_engine`, `AsyncSession`). The async engine needs `greenlet` at runtime.
- Upstream declares it through the extra: `"sqlalchemy[asyncio]>=2.0"` in
  `apps/backend/pyproject.toml`. The `[asyncio]` extra is what installs `greenlet`.
- From **SQLAlchemy 2.1**, `greenlet` is installed **only** when that extra is named. If the office
  dependency list says plain `sqlalchemy`, or the extra is lost when generating a `requirements.txt`
  or lock file, `pip install` succeeds without `greenlet`.
- The app then fails at the first database call, with an error like
  `ValueError: the greenlet library is required to use this function. No module named 'greenlet'`.
  That is why the build looks fine and only the deployment fails.

This is a dependency fix only. **No application code changes, no database migration, no settings.**

## What to do

Work on a new branch, for example `fix/greenlet-dependency`. Do not touch the main branch, any
database, deployment or secret. Stop after each step and show me the result.

1. **Find where the image gets its Python packages.** Read the Dockerfile(s) for the API, and find
   what they install from: `apps/backend/pyproject.toml`, a `requirements*.txt`, a lock file
   (`uv.lock`, `poetry.lock`, `requirements.lock`) or a constraints file. Tell me which one.

2. **Declare `greenlet` explicitly** in that file, keeping the SQLAlchemy extra:

   ```
   sqlalchemy[asyncio]>=2.0
   greenlet>=3.0
   ```

   - In `pyproject.toml`, add `"greenlet>=3.0",` to `[project] dependencies` next to the
     SQLAlchemy line.
   - If a `requirements.txt` or lock file is **generated**, add it to the source, then regenerate
     with the office's usual command. Do not hand-edit a generated lock file.
   - If a constraints or pin file pins SQLAlchemy, leave the pin alone and add the `greenlet` line.

3. **Check that the package can be installed from our mirror**, in a clean virtual environment
   with the same Python version as the image's base:

   ```bash
   python -m venv /tmp/gl && /tmp/gl/bin/pip install "sqlalchemy[asyncio]>=2.0" "greenlet>=3.0"
   /tmp/gl/bin/python -c "import sqlalchemy, greenlet; print(sqlalchemy.__version__, greenlet.__version__)"
   ```

   If pip cannot find or build `greenlet`, stop and tell me. The internal mirror needs the
   `greenlet` wheel for the image's platform. An Alpine (musl) base needs greenlet 3.x. DevOps adds
   it; we do not change the base image ourselves.

4. **Build the image locally**, if Docker is available here, and prove the fix inside it:

   ```bash
   docker build -t financeagent-api:greenlet-check <the API's build context and Dockerfile>
   docker run --rm financeagent-api:greenlet-check \
     python -c "import greenlet, sqlalchemy; from sqlalchemy.ext.asyncio import create_async_engine; print('ok', sqlalchemy.__version__, greenlet.__version__)"
   ```

   It must print `ok` and two versions. If Docker is not available here, say so; DevOps will run
   this check in the pipeline.

5. **Run the backend tests** in `apps/backend` with `pytest -q`, and report the counts. Nothing
   should change: this only adds a package.

6. **Commit** on the branch with a message such as:
   `Declare greenlet explicitly: SQLAlchemy 2.1 installs it only with the asyncio extra; the API image was missing it`

   Then summarise:
   - the file changed;
   - the SQLAlchemy and greenlet versions now resolved;
   - the result of steps 3 to 5.

   Stop there. I will raise the merge request.

## Do not

- Change application code, `db.py`, or switch the engine to a sync driver to avoid `greenlet`.
- Remove the `[asyncio]` extra.
- Paste or ask for access tokens. Use the normal git credentials already set up here.
- Change the CI pipeline or base image without asking me.

## Message for DevOps once it is merged

> The deployment failure was one missing Python dependency: `greenlet`, which SQLAlchemy's async
> engine needs at runtime. SQLAlchemy 2.1 installs it only with the `[asyncio]` extra, which our
> dependency list had dropped. It is now declared explicitly. Please rebuild the image from
> `<branch/commit>` and redeploy. To check the image before deploying:
> `docker run --rm <image> python -c "import greenlet, sqlalchemy; print(sqlalchemy.__version__, greenlet.__version__)"`.
