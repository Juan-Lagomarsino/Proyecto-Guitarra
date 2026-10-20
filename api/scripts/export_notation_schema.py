"""Escribe schemas/notation.schema.json a partir del modelo Pydantic."""

import json
from pathlib import Path

from guitarra_api.domain.notation import build_json_schema

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "notation.schema.json"


def main() -> None:
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(build_json_schema(), indent=2, ensure_ascii=False) + "\n"
    SCHEMA_PATH.write_text(content, encoding="utf-8", newline="\n")
    print(f"Escrito {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
