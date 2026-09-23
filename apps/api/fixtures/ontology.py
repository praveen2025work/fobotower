"""Layer A ontology and Layer B policy — now loaded from the playbook YAML.

The definitions used to live here as Python constants. They moved to
config/playbook/fobo-cats-vs-motif.yaml so Product Control can edit them
without a code change, and so there is exactly one copy.
"""

from app.playbook.loader import load_playbook, loaded_version


async def load_ontology(session, *, commit: bool = True) -> None:
    await load_playbook(session, commit=commit)


async def ontology_is_loaded(session) -> bool:
    return await loaded_version(session) is not None
