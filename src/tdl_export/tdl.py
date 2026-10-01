import json
from typing import Any
from pathlib import Path
import subprocess

from tdl_export.archive import Message, ChatData

# tdl's own default, pinned here: a TDL_TEMPLATE environment variable silently replaces it
# when the flag is absent, and these names are the only record of what has been downloaded.
NAME_TEMPLATE = "{{ .DialogID }}_{{ .MessageID }}_{{ filenamify .FileName }}"


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


def download(
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
