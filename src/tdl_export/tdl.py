import json
from typing import Any
from pathlib import Path
import subprocess

from tdl_export.archive import Message, ChatData

# Every value below is always passed explicitly: tdl reads a TDL_<FLAG> environment variable for each
# of these flags when it is left out, and the rendered names are the only record of what has arrived.
NAME_TEMPLATE = "{{ .DialogID }}_{{ .MessageID }}_{{ filenamify .FileName }}"
# Files at once, and parts per large file. 4 files measured faster than tdl's default of 2 and no
# slower than 8; small files ignore both, as tdl looks messages up one at a time.
LIMIT = 4
THREADS = 4


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


def export_chat(chat_id: int, output: Path, since: int | None) -> ChatData:
    export_command = [
        "tdl",
        "chat",
        "export",
        "--chat",
        str(chat_id),
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


def download(pending: ChatData, directory: Path, request: Path, limit: int, threads: int) -> None:
    """Fetch the messages of `pending` into `directory`, through the request file `request`.

    One process per chat: tdl stops the whole process at the first message it cannot resolve, and a
    process of its own keeps that to the chat the message belongs to.
    """
    messages = [Message(id=message.id, file=message.file) for message in pending.messages]
    request.write_text(
        ChatData(id=pending.id, messages=messages).model_dump_json(
            indent=2, ensure_ascii=False, exclude_none=True
        ),
        encoding="utf-8",
    )
    download_command = [
        "tdl",
        "dl",
        "--file",
        request.as_posix(),
        "--dir",
        directory.as_posix(),
        "--template",
        NAME_TEMPLATE,
        "--limit",
        str(limit),
        "--threads",
        str(threads),
        # Never reads tdl's own resume state, which is keyed on the exact message list and marks a
        # truncated transfer as finished; the pending list is rebuilt from disk every run anyway.
        "--restart",
    ]
    subprocess.run(download_command, check=True)  # noqa: S603
