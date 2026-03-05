import json
from pathlib import Path
import subprocess

from pydantic import Field, BaseModel
from rich.console import Console

console = Console()


class FileInfo(BaseModel):
    group_id: int
    message_id: int
    message_filename: str


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


def save_chat_data(path: Path, chat_data: ChatData) -> ChatData:
    chat_data_json = chat_data.model_dump_json(indent=2, ensure_ascii=False)
    path.write_text(chat_data_json, encoding="utf-8")
    return chat_data


def merge_chat_data(original: ChatData, new: ChatData) -> ChatData:
    # Build a lookup map from original data keyed by (id, date)
    original_map: dict[tuple[int, int], Message] = {
        (msg.id, msg.date): msg for msg in original.messages
    }

    merged_map: dict[tuple[int, int], Message] = dict(original_map)

    for msg in new.messages:
        key = (msg.id, msg.date)
        if key not in merged_map:
            merged_map[key] = msg

    sorted_messages = sorted(merged_map.values(), key=lambda m: m.id, reverse=True)

    return ChatData(id=new.id, messages=sorted_messages)


def get_all_current_file(path: Path) -> list[FileInfo]:
    if not path.exists():
        return []

    all_files = [f for f in path.glob("**/*") if f.is_file()]
    file_info: list[FileInfo] = []
    for f in all_files:
        # 使用 maxsplit=2 確保我們只以最前面的兩個底線來切分，避免檔名中也含有底線而導致錯誤
        parts = f.name.split("_", maxsplit=2)
        if len(parts) == 3:
            file_data = FileInfo(
                group_id=int(parts[0]),  # 3310384808
                message_id=int(parts[1]),  # 37
                message_filename=parts[2],  # 6170222615722053134.jpg
            )
            file_info.append(file_data)
    return file_info


def check_chat_data(path: Path, chat_data: ChatData) -> ChatData:
    current_files = get_all_current_file(path=path)
    downloaded_msg_ids = {f.message_id for f in current_files}

    for message in chat_data.messages:
        # 檢查該 message 是否已經在我們本地的資料夾中
        if message.id in downloaded_msg_ids:
            message.downloaded = True
    return chat_data


def download_media(group_id: str, from_file: bool = True) -> None:
    original_chat_path = Path(f"./data/{group_id}.json")
    new_chat_path = Path(f"./data/{group_id}_new.temp")
    temp_chat_path = Path(f"./data/{group_id}_undownloaded.temp")
    download_path = Path(f"./downloads/{group_id}")

    original_chat_path.parent.mkdir(exist_ok=True, parents=True)

    original_chat_data = load_chat_data(path=original_chat_path)
    console.rule("[bold cyan]Original Chat Data Loaded")

    export_command = [
        "tdl",
        "chat",
        "export",
        "--chat",
        str(group_id),
        "--all",
        "--with-content",
        "--output",
        new_chat_path.as_posix(),
    ]
    subprocess.run(export_command, check=True)  # noqa: S603

    new_chat_data = load_chat_data(path=new_chat_path)
    new_chat_path.unlink(missing_ok=True)
    console.rule("[bold cyan]New Chat Data Loaded")

    combined_chat_data = merge_chat_data(original=original_chat_data, new=new_chat_data)
    console.rule("[bold cyan]Chat Data Merged")

    if from_file:
        undownloaded = check_chat_data(path=download_path, chat_data=combined_chat_data)
        undownloaded.messages = [msg for msg in undownloaded.messages if not msg.downloaded]
        save_chat_data(path=temp_chat_path, chat_data=undownloaded)
        console.rule("[bold cyan]Checked Existing Local Files")

        console.rule("[bold cyan]Start Downloading Media")
        download_command = ["tdl", "dl", "-f", f"{temp_chat_path}", "-d", str(download_path)]
        subprocess.run(download_command, check=True)  # noqa: S603
        temp_chat_path.unlink(missing_ok=True)

    else:
        undownloaded = check_chat_data(path=download_path, chat_data=combined_chat_data)
        undownloaded.messages = [msg for msg in undownloaded.messages if not msg.downloaded]
        console.rule("[bold cyan]Checked Existing Local Files")
        console.rule("[bold cyan]Start Downloading Media From Link")
        for message in combined_chat_data.messages:
            if message.downloaded or not message.file:
                continue

            target_url = f"https://t.me/c/{group_id}/{message.id}"
            console.print(f"[cyan]Downloading: {target_url}  ({message.file})")
            download_command = [
                "tdl",
                "dl",
                "-u",
                target_url,
                "-d",
                str(download_path),
                "-t",
                "64",
            ]
            subprocess.run(download_command, check=True)  # noqa: S603
            message.downloaded = True

    result = check_chat_data(path=download_path, chat_data=combined_chat_data)
    save_chat_data(path=original_chat_path, chat_data=result)
    console.rule("[bold cyan]Final Data Saved")
    console.print(f"[green]Done! Final data saved to {original_chat_path}")


def main() -> None:
    group_id = "3310384808"
    download_media(group_id=group_id)


if __name__ == "__main__":
    main()
