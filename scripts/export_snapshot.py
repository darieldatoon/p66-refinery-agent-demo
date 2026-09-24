import json
from pathlib import Path

from refinery_data.source import SqliteRefineryDataSource
from refinery_data.workspace import static_evidence, static_workspace


def main() -> None:
    source = SqliteRefineryDataSource()
    target = Path("frontend/public/snapshot.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    snapshot = static_workspace(source) | {"evidence": static_evidence(source)}
    target.write_text(json.dumps(snapshot, separators=(",", ":")) + "\n")
    print("Exported the fixed synthetic snapshot")


if __name__ == "__main__":
    main()
