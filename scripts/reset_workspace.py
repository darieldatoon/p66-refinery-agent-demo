import argparse
from contextlib import suppress

from langgraph_sdk import get_sync_client
from langgraph_sdk.errors import NotFoundError

from refinery_data.source import SqliteRefineryDataSource
from refinery_data.workspace import SNAPSHOT_ID, signal_catalog

NAMESPACE = ["refinery-workspace", SNAPSHOT_ID]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete saved assessments, proposals and issue threads for this snapshot."
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--apply", action="store_true", help="Delete; otherwise list only")
    args = parser.parse_args()
    client = get_sync_client(url=args.url, timeout=120)
    items = []
    while page := client.store.search_items(NAMESPACE, limit=100, offset=len(items))["items"]:
        items.extend(page)
    threads = [signal.thread_id for signal in signal_catalog(SqliteRefineryDataSource())]
    print(f"{len(items)} store records under {'/'.join(NAMESPACE)}; {len(threads)} issue threads")
    if not args.apply:
        print("Dry run. Re-run with --apply to delete.")
        return
    for item in items:
        client.store.delete_item(item["namespace"], item["key"])
    for thread_id in threads:
        with suppress(NotFoundError):
            client.threads.delete(thread_id)
    print("Workspace reset. Reload the browser to start fresh investigations.")


if __name__ == "__main__":
    main()
