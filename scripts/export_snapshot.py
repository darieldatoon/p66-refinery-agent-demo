import json
from pathlib import Path

from refinery_data.source import SqliteRefineryDataSource
from refinery_data.workspace import static_workspace


def main() -> None:
    target = Path("frontend/public/snapshot.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(static_workspace(SqliteRefineryDataSource()), indent=2) + "\n")
    print("Exported the fixed synthetic snapshot")


if __name__ == "__main__":
    main()
