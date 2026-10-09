"""AOF_DATABASE_URL, or the URL built from its parts (each key of a database secret as its own variable)."""

from agent_one_finance import config


def _url(monkeypatch, **env):
    for k in ("AOF_DATABASE_URL", "AOF_DATABASE_HOST", "AOF_DATABASE_PORT", "AOF_DATABASE_NAME", "AOF_DATABASE_USER",
              "AOF_DATABASE_PASSWORD", "FOBO_DATABASE_URL"):
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    config.settings.cache_clear()
    try:
        return config.settings().database_url
    finally:
        config.settings.cache_clear()


def test_parts_make_the_url_with_the_password_escaped(monkeypatch):
    url = _url(monkeypatch, AOF_DATABASE_HOST="db.internal", AOF_DATABASE_NAME="aof", AOF_DATABASE_USER="aof_app",
               AOF_DATABASE_PASSWORD="p@ss:w/rd")
    assert url == "postgresql+asyncpg://aof_app:p%40ss%3Aw%2Frd@db.internal:5432/aof"


def test_a_full_url_wins_over_parts(monkeypatch):
    assert _url(monkeypatch, AOF_DATABASE_URL="postgresql+asyncpg://u@h/d", AOF_DATABASE_HOST="other") == "postgresql+asyncpg://u@h/d"
