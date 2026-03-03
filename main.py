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
    id: int = Field(default=0, description="The Chat or Group ID")
    messages: list[Message] = Field(default_factory=list)


def load_chat_data(path: Path) -> ChatData:
    """Read a JSON file and parse it into a ChatData. Returns an empty ChatData if file doesn't exist."""
    if not path.exists():
        return ChatData()
    content = path.read_text(encoding="utf-8")
    content_dict = json.loads(content)
    return ChatData(**content_dict)


def merge_chat_data(original: ChatData, new: ChatData) -> ChatData:
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
    original_chat_path = Path(f"./data/{group_id}.json")
    new_chat_path = Path(f"./data/{group_id}.temp")

    original_chat_path.parent.mkdir(exist_ok=True, parents=True)

    original_chat_data = load_chat_data(original_chat_path)
    console.rule("[bold cyan]Original Chat Data Loaded")

    export_command = f"tdl chat export --chat {group_id} --all --with-content --output {new_chat_path.as_posix()}"
    os.system(export_command)  # noqa: S605

    new_chat_data = load_chat_data(new_chat_path)
    new_chat_path.unlink(missing_ok=True)
    console.rule("[bold cyan]New Chat Data Loaded")

    combined_chat_data = merge_chat_data(original_chat_data, new_chat_data)
    console.rule("[bold cyan]Chat Data Merged")

    for message in combined_chat_data.messages:
        if message.downloaded or not message.file:
            continue

        target_url = f"https://t.me/c/{group_id}/{message.id}"
        console.print(f"[cyan]Downloading: {target_url}  ({message.file})")
        download_command = f"tdl download --url {target_url} --threads 64"
        os.system(download_command)  # noqa: S605
        message.downloaded = True

    combined_chat_data_json = combined_chat_data.model_dump_json(indent=2, ensure_ascii=False)
    original_chat_path.write_text(combined_chat_data_json, encoding="utf-8")
    console.rule("[bold cyan]Final Data Saved")
    console.print(f"[green]Done! Final data saved to {original_chat_path}")


if __name__ == "__main__":
    group_id = "3310384808"
    download_media(group_id=group_id)
