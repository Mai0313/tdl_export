import json
from pathlib import Path
from pydantic import BaseModel, Field
from datetime import datetime
import os


class Message(BaseModel):
    id: int = Field(..., description="The Message ID")
    type: str = Field(..., description="The type of the message")
    file: str = Field(..., description="This is the file name")
    date: datetime


def download_media(group_id: str):
    today = datetime.now().date().strftime("%Y-%m-%d")
    chat_path = Path(f"./data/{today}_{group_id}.json")

    if not chat_path.exists():
        chat_path.parent.mkdir(exist_ok=True, parents=True)
        os.system(f"tdl chat export --chat {group_id} --all --with-content --output {chat_path.as_posix()}")

    chat_content = chat_path.read_text()
    chat_dict = json.loads(chat_content)
    chat_messages = chat_dict["messages"]

    all_dates = []
    for message in chat_messages:
        message_obj = Message(**message)
        if message_obj.date not in all_dates:
            all_dates.append(message_obj.date)
            target_url = f"https://t.me/c/{group_id}/{message_obj.id}"
            os.system(f"tdl download --url {target_url} --group --skip-same")

if __name__ == "__main__":
    group_id = "3310384808"
    download_media(group_id=group_id)
