import json
from pathlib import Path

from pydantic import Field, BaseModel


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


def load(path: Path) -> ChatData:
    """Read a JSON file and parse it into a ChatData. Returns an empty ChatData if file doesn't exist."""
    if not path.exists():
        return ChatData()
    content = path.read_text(encoding="utf-8")
    content_dict = json.loads(content)
    return ChatData(**content_dict)


def save(path: Path, chat_data: ChatData) -> None:
    path.parent.mkdir(exist_ok=True, parents=True)
    # Staged, because a half-written archive costs a full rate-limited re-export to rebuild.
    staging = path.with_name(f"{path.name}.tmp")
    staging.write_text(chat_data.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
    staging.replace(path)


def merge(original: ChatData, new: ChatData) -> ChatData:
    merged: dict[int, Message] = {message.id: message for message in original.messages}
    merged.update({message.id: message for message in new.messages})
    sorted_messages = sorted(merged.values(), key=lambda message: message.id, reverse=True)
    return ChatData(id=new.id, messages=sorted_messages)
