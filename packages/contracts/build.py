"""Emit JSON Schema + .d.ts from the Pydantic contract."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "api"))

from app.contracts.models import WS_EVENT_MODELS  # noqa: E402

OUT = Path(__file__).parent / "dist"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for model in WS_EVENT_MODELS:
        schema = model.model_json_schema()
        path = OUT / f"{model.__name__}.schema.json"
        path.write_text(json.dumps(schema, indent=2))
        subprocess.run(
            [
                "npx",
                "-y",
                "json-schema-to-typescript",
                str(path),
                "-o",
                str(OUT / f"{model.__name__}.d.ts"),
            ],
            check=True,
        )
    print(f"wrote {len(WS_EVENT_MODELS)} schemas to {OUT}")


if __name__ == "__main__":
    main()
