import re
from pathlib import Path

from rich.markup import escape
from rich.console import Console

from tdl_export.archive import Message, ChatData

console = Console()


def sweep_temp_files(path: Path) -> None:
    """Drop tdl's leftovers; it truncates a `.tmp` on the next attempt rather than resuming it."""
    for leftover in path.glob("*.tmp"):
        size = leftover.stat().st_size
        console.print(f"[yellow]Removing stale temp file: {escape(str(leftover))} ({size} bytes)")
        leftover.unlink()


def lowercase_extensions(path: Path) -> None:
    entries = sorted(path.iterdir())
    names = {entry.name for entry in entries}
    for entry in entries:
        if not entry.is_file() or entry.suffix == entry.suffix.lower():
            continue
        target = entry.with_suffix(entry.suffix.lower())
        if target.name in names:
            console.print(
                f"[yellow]Kept {escape(entry.name)}; {escape(target.name)} already exists"
            )
            continue
        entry.rename(target)
        names.add(target.name)


def scan(path: Path, chat_id: str) -> dict[int, Path]:
    """Map message id to the file tdl wrote for it, by reading the `--template` prefix back."""
    pattern = re.compile(rf"^{re.escape(chat_id)}_(\d+)_")
    current: dict[int, Path] = {}
    for entry in path.iterdir():
        if not entry.is_file() or entry.suffix == ".tmp":
            continue
        matched = pattern.match(entry.name)
        if matched:
            current[int(matched.group(1))] = entry
    return current


def find_pending(chat_data: ChatData, current: dict[int, Path]) -> list[Message]:
    pending: list[Message] = []
    for message in chat_data.messages:
        if not message.file:
            continue
        local = current.get(message.id)
        if local is None:
            pending.append(message)
            continue
        # tdl swallows a failed transfer and renames the partial file to its final name,
        # so a file that is present still has to be measured.
        actual = local.stat().st_size
        if message.size is not None and actual != message.size:
            path = escape(str(local))
            console.print(
                f"[yellow]Incomplete, removing: {path} ({actual} of {message.size} bytes)"
            )
            local.unlink()
            pending.append(message)
    return pending


def report_incomplete(pending: list[Message], chat_id: str, download_path: Path) -> None:
    """The directory is the only honest answer, since tdl exits 0 even when files failed."""
    current = scan(path=download_path, chat_id=chat_id)
    failed = [
        message.id
        for message in pending
        if message.id not in current
        or (message.size is not None and current[message.id].stat().st_size != message.size)
    ]
    if not failed:
        return
    shown = ", ".join(str(message_id) for message_id in failed[:20])
    more = f" ... and {len(failed) - 20} more" if len(failed) > 20 else ""
    console.print(f"[red]{len(failed)} message(s) still missing or incomplete: {shown}{more}")
