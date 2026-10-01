import re
import json
from typing import Any
from pathlib import Path
import tempfile
import subprocess

import fire
from pydantic import Field, BaseModel
from rich.markup import escape
from rich.console import Console

console = Console()

CHAT_DIR = Path("./data/chats")
DOWNLOAD_DIR = Path("./data/downloads")

# tdl's own default, pinned here: a TDL_TEMPLATE environment variable silently replaces it
# when the flag is absent, and these names are the only record of what has been downloaded.
NAME_TEMPLATE = "{{ .DialogID }}_{{ .MessageID }}_{{ filenamify .FileName }}"

DEFAULT_CHAT_IDS = [
    "5727382280",
    "3893137254",
    "8155177296",
    "8229333075",
    "7974286223",
    "7479079265",
    "8801654201",
    # "1602149932",
]


class Message(BaseModel):
    id: int = Field(..., description="The Message ID")
    type: str = Field(default="message", description="The type of the message")
    file: str = Field(default="", description="This is the file name")
    size: int | None = Field(default=None, description="Byte size Telegram reports for the media")
    date: int | None = Field(default=None)
    text: str | None = Field(default=None)


class ChatData(BaseModel):
    id: int = Field(default=0, description="The Chat or Group ID")
    messages: list[Message] = Field(default_factory=list)


def load_chat_data(path: Path) -> ChatData:
    """Read a JSON file and parse it into a ChatData. Returns an empty ChatData if file doesn't exist."""
    if not path.exists():
        return ChatData()
    content = path.read_text(encoding="utf-8")
    content_dict = json.loads(content)
    return ChatData(**content_dict)


def save_chat_data(path: Path, chat_data: ChatData) -> None:
    path.parent.mkdir(exist_ok=True, parents=True)
    # Staged, because a half-written archive costs a full rate-limited re-export to rebuild.
    staging = path.with_name(f"{path.name}.tmp")
    staging.write_text(chat_data.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
    staging.replace(path)


def merge_chat_data(original: ChatData, new: ChatData) -> ChatData:
    merged: dict[int, Message] = {message.id: message for message in original.messages}
    merged.update({message.id: message for message in new.messages})
    sorted_messages = sorted(merged.values(), key=lambda message: message.id, reverse=True)
    return ChatData(id=new.id, messages=sorted_messages)


def get_media_size(raw: dict[str, Any]) -> int | None:
    """Pull the byte size out of a `--raw` message, the way tdl derives it."""
    media = raw.get("Media") or {}
    document = media.get("Document")
    if isinstance(document, dict):
        return document.get("Size")

    photo = media.get("Photo")
    if not isinstance(photo, dict) or not photo.get("Sizes"):
        return None
    # tdl downloads the last size; a progressive one carries its own list of byte counts.
    largest = photo["Sizes"][-1]
    progressive = largest.get("Sizes")
    if isinstance(progressive, list) and progressive:
        return progressive[-1]
    return largest.get("Size")


def export_chat(chat_id: str, output: Path, since: int | None) -> ChatData:
    export_command = [
        "tdl",
        "chat",
        "export",
        "--chat",
        chat_id,
        "--all",
        "--with-content",
        "--raw",
        "--type",
        "id",
        "--output",
        output.as_posix(),
    ]
    # A single --input is expanded to [since, MaxInt], so this exports only what is newer.
    if since is not None:
        export_command += ["--input", str(since)]
    subprocess.run(export_command, check=True)  # noqa: S603

    payload = json.loads(output.read_text(encoding="utf-8"))
    messages = [
        Message(
            id=entry["id"],
            type=entry["type"],
            file=entry.get("file", ""),
            size=get_media_size(raw=entry.get("raw") or {}),
            date=entry.get("date"),
            text=entry.get("text"),
        )
        for entry in payload["messages"]
    ]
    return ChatData(id=payload["id"], messages=messages)


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


def get_all_current_file(path: Path, chat_id: str) -> dict[int, Path]:
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


def get_pending_messages(chat_data: ChatData, current: dict[int, Path]) -> list[Message]:
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


def download_media_files(
    pending: list[Message], chat_id: str, download_path: Path, request_path: Path
) -> None:
    request = ChatData(
        id=int(chat_id),
        messages=[Message(id=message.id, file=message.file) for message in pending],
    )
    request_path.write_text(
        request.model_dump_json(indent=2, ensure_ascii=False, exclude_none=True), encoding="utf-8"
    )
    download_command = [
        "tdl",
        "dl",
        "--file",
        request_path.as_posix(),
        "--dir",
        download_path.as_posix(),
        "--template",
        NAME_TEMPLATE,
        # Without this tdl puts an interactive prompt on stdin whenever resume state is left over.
        "--continue",
    ]
    subprocess.run(download_command, check=True)  # noqa: S603


def report_incomplete(pending: list[Message], chat_id: str, download_path: Path) -> None:
    """The directory is the only honest answer, since tdl exits 0 even when files failed."""
    current = get_all_current_file(path=download_path, chat_id=chat_id)
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


def download_media(chat_id: str, verify: bool = False) -> None:
    chat_id = str(chat_id)
    chat_path = CHAT_DIR / f"{chat_id}.json"
    download_path = DOWNLOAD_DIR / chat_id
    download_path.mkdir(exist_ok=True, parents=True)

    chat_data = load_chat_data(path=chat_path)
    # An archive holding no sizes at all predates them, and cannot be checked until it is rebuilt.
    full = verify or not any(message.size is not None for message in chat_data.messages)
    since = None if full else max(message.id for message in chat_data.messages) + 1

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        scope = "everything" if since is None else f"messages after {since - 1}"
        console.rule(f"[bold cyan]{chat_id}: exporting {scope}")
        exported = export_chat(chat_id=chat_id, output=temp_path / "export.json", since=since)
        chat_data = merge_chat_data(original=chat_data, new=exported)
        save_chat_data(path=chat_path, chat_data=chat_data)

        sweep_temp_files(path=download_path)
        lowercase_extensions(path=download_path)
        current = get_all_current_file(path=download_path, chat_id=chat_id)
        pending = get_pending_messages(chat_data=chat_data, current=current)
        console.rule(f"[bold cyan]{chat_id}: {len(current)} on disk, {len(pending)} to download")

        if pending:
            download_media_files(
                pending=pending,
                chat_id=chat_id,
                download_path=download_path,
                request_path=temp_path / "download.json",
            )
            lowercase_extensions(path=download_path)
            report_incomplete(pending=pending, chat_id=chat_id, download_path=download_path)

    console.print(f"[green]Done! {chat_id} data saved to {chat_path}")


def run(*chat_ids: str, verify: bool = False) -> None:
    for chat_id in [str(chat_id) for chat_id in chat_ids] or DEFAULT_CHAT_IDS:
        download_media(chat_id=chat_id, verify=verify)


def main() -> None:
    fire.Fire(run)


if __name__ == "__main__":
    main()
