from pathlib import Path
import tempfile
import subprocess

import fire
from rich.table import Table
from rich.console import Console

from tdl_export import tdl, ledger, archive
from tdl_export.archive import Message, ChatData

console = Console()

CHAT_DIR = Path("./data/chats")
DOWNLOAD_DIR = Path("./data/downloads")

DEFAULT_CHAT_IDS = [
    5727382280,
    3893137254,
    8155177296,
    8229333075,
    7974286223,
    7479079265,
    8801654201,
    # 1602149932,
]


def sync_archive(chat_id: int, verify: bool, staging: Path) -> ChatData:
    """Export what is new in the chat, merge it into the archive and save that."""
    path = CHAT_DIR / f"{chat_id}.json"
    chat_data = archive.load(path=path)
    # An archive holding no sizes at all predates them, and cannot be checked until it is rebuilt.
    full = verify or not any(message.size is not None for message in chat_data.messages)
    since = None if full else max(message.id for message in chat_data.messages) + 1
    scope = "everything" if since is None else f"messages after {since - 1}"
    console.rule(f"[bold cyan]{chat_id}: exporting {scope}")
    exported = tdl.export_chat(
        chat_id=chat_id, output=staging / f"{chat_id}.export.json", since=since
    )
    chat_data = archive.merge(original=chat_data, new=exported)
    archive.save(path=path, chat_data=chat_data)
    return chat_data


def reconcile(chat_id: int, chat_data: ChatData) -> list[Message]:
    """Tidy the chat's folder and return the messages whose file is not there in full."""
    folder = DOWNLOAD_DIR / str(chat_id)
    folder.mkdir(exist_ok=True, parents=True)
    ledger.sweep_temp_files(path=folder)
    ledger.lowercase_extensions(path=folder)
    current = ledger.scan(path=folder, chat_id=chat_id)
    pending = ledger.find_pending(chat_data=chat_data, current=current)
    console.print(f"{chat_id}: {len(current)} on disk, {len(pending)} to download")
    return pending


def report(pending: dict[int, list[Message]]) -> None:
    """Measure what arrived; the folder is the only honest answer, since tdl exits 0 regardless."""
    table = Table("chat", "requested", "arrived", "still missing or incomplete")
    for chat_id, requested in pending.items():
        folder = DOWNLOAD_DIR / str(chat_id)
        ledger.lowercase_extensions(path=folder)
        missing = ledger.find_incomplete(pending=requested, path=folder, chat_id=chat_id)
        shown = ", ".join(str(message_id) for message_id in missing[:20])
        more = f" and {len(missing) - 20} more" if len(missing) > 20 else ""
        arrived = str(len(requested) - len(missing))
        table.add_row(str(chat_id), str(len(requested)), arrived, shown + more)
    console.print(table)


def run(
    *chat_ids: int, verify: bool = False, limit: int = tdl.LIMIT, threads: int = tdl.THREADS
) -> None:
    """Mirror the media of each chat under ./data, or of DEFAULT_CHAT_IDS when none are named.

    Every chat is exported first, then each one's missing files are downloaded in turn.

    Args:
        *chat_ids: Numeric Telegram chat ids.
        verify: Re-export every chat in full, refreshing every recorded size.
        limit: How many files tdl downloads at once.
        threads: How many parts of one large file tdl downloads at once.
    """
    # tdl hangs on 0 and takes a negative limit as no limit at all.
    if limit < 1 or threads < 1:
        raise SystemExit("--limit and --threads must be at least 1")
    failed: list[str] = []
    pending: dict[int, list[Message]] = {}
    with tempfile.TemporaryDirectory() as temp_dir:
        staging = Path(temp_dir)
        for chat_id in [int(chat_id) for chat_id in chat_ids] or DEFAULT_CHAT_IDS:
            try:
                chat_data = sync_archive(chat_id=chat_id, verify=verify, staging=staging)
            except subprocess.CalledProcessError:
                failed.append(f"{chat_id}: export failed, skipped")
                continue
            pending[chat_id] = reconcile(chat_id=chat_id, chat_data=chat_data)

        pending = {chat_id: messages for chat_id, messages in pending.items() if messages}
        for chat_id, messages in pending.items():
            console.rule(f"[bold cyan]{chat_id}: downloading {len(messages)} files")
            try:
                tdl.download(
                    pending=ChatData(id=chat_id, messages=messages),
                    directory=DOWNLOAD_DIR / str(chat_id),
                    request=staging / f"{chat_id}.request.json",
                    limit=limit,
                    threads=threads,
                )
            except subprocess.CalledProcessError:
                failed.append(f"{chat_id}: tdl dl stopped early")
            except subprocess.TimeoutExpired:
                failed.append(
                    f"{chat_id}: nothing arrived for {tdl.STALL // 60} minutes, tdl stopped"
                )
        if pending:
            report(pending=pending)

    for failure in failed:
        console.print(f"[red]{failure}")
    if failed:
        raise SystemExit(1)


def main() -> None:
    try:
        fire.Fire(run)
    except KeyboardInterrupt:
        # Finished files are on disk under their final names; the next run works out the rest.
        console.print("[yellow]Interrupted. Run it again to continue where it stopped.")
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
