import os
import json
from pathlib import Path

from pydantic import Field, BaseModel
from rich.console import Console

console = Console()


class Message(BaseModel):
    id: int = Field(..., description="The Message ID")
    type: str = Field(..., description="The type of the message")
    file: str = Field(default="", description="This is the file name")
    date: int
    text: str | None = Field(default=None)
    downloaded: bool = Field(default=False, description="Whether the file is downloaded or not")


class ChatData(BaseModel):
    id: int = Field(..., description="The Chat ID")
    messages: list[Message]


def load_chat_data(path: Path) -> ChatData | None:
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8")
    content_dict = json.loads(content)
    return ChatData(**content_dict)


def merge_chat_data(original: ChatData | None, new: ChatData) -> ChatData:
    if original is None:
        return new

    # Build a lookup map from original data keyed by (id, date)
    original_map: dict[tuple[int, int], Message] = {
        (msg.id, msg.date): msg for msg in original.messages
    }

    merged_map: dict[tuple[int, int], Message] = dict(original_map)

    for msg in new.messages:
        key = (msg.id, msg.date)
        if key not in merged_map:
            # New message not seen before — add it
            merged_map[key] = msg

    # Sort by id descending to keep the same ordering as tdl export output
    sorted_messages = sorted(merged_map.values(), key=lambda m: m.id, reverse=True)

    return ChatData(id=new.id, messages=sorted_messages)


def download_media(group_id: str) -> None:
    chat_path = Path(f"./data/{group_id}.json")
    new_chat_path = Path(f"./data/{group_id}_new.json")

    chat_path.parent.mkdir(exist_ok=True, parents=True)

    # ── Step 1: Read original data (may not exist on first run) ──────────────
    console.rule("[bold cyan]Step 1: Loading original chat data")
    original_chat_data = load_chat_data(chat_path)
    if original_chat_data is not None:
        console.print(
            f"[green]Loaded {len(original_chat_data.messages)} messages from {chat_path}"
        )
    else:
        console.print(f"[yellow]No existing data found at {chat_path}, will create fresh.")

    # ── Step 2: Export latest data from Telegram ─────────────────────────────
    os.system(  # noqa: S605
        f"tdl chat export --chat {group_id} --all --with-content --output {new_chat_path.as_posix()}"
    )

    new_chat_data = load_chat_data(new_chat_path)
    if new_chat_data is None:
        console.print(f"[red]Export failed: {new_chat_path} not found. Aborting.")
        return

    # ── Step 3: Merge original + new data ────────────────────────────────────
    console.rule("[bold cyan]Step 3: Merging chat data")
    original_count = len(original_chat_data.messages) if original_chat_data else 0
    combined_chat_data = merge_chat_data(original_chat_data, new_chat_data)
    new_count = len(combined_chat_data.messages) - original_count
    console.print(f"[green]Updated {new_count} messages")

    new_chat_path.unlink(missing_ok=True)

    # ── Step 4 & 5: Download files, skip already downloaded ──────────────────
    console.rule("[bold cyan]Step 4: Downloading files")
    pending = [msg for msg in combined_chat_data.messages if not msg.downloaded and msg.file]
    console.print(
        f"[bold]{len(pending)} files to download (skipping already downloaded & empty files)"
    )

    for message in combined_chat_data.messages:
        if message.downloaded or not message.file:
            continue

        target_url = f"https://t.me/c/{group_id}/{message.id}"
        console.print(f"[cyan]Downloading: {target_url}  ({message.file})")
        # os.system(f"tdl download --url {target_url} --threads 64")  # noqa: S605
        message.downloaded = True

    # ── Step 5: Save final state ──────────────────────────────────────────────
    console.rule("[bold cyan]Step 5: Saving final downloaded state")
    chat_path.write_text(
        combined_chat_data.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8"
    )
    console.print(f"[green]Done! Final data saved to {chat_path}")


if __name__ == "__main__":
    group_id = "3310384808"
    download_media(group_id=group_id)
