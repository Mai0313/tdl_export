from pathlib import Path
import tempfile

import fire
from rich.console import Console

from tdl_export import tdl, ledger, archive

console = Console()

CHAT_DIR = Path("./data/chats")
DOWNLOAD_DIR = Path("./data/downloads")

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


def download_media(chat_id: str, verify: bool = False) -> None:
    chat_id = str(chat_id)
    chat_path = CHAT_DIR / f"{chat_id}.json"
    download_path = DOWNLOAD_DIR / chat_id
    download_path.mkdir(exist_ok=True, parents=True)

    chat_data = archive.load(path=chat_path)
    # An archive holding no sizes at all predates them, and cannot be checked until it is rebuilt.
    full = verify or not any(message.size is not None for message in chat_data.messages)
    since = None if full else max(message.id for message in chat_data.messages) + 1

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        scope = "everything" if since is None else f"messages after {since - 1}"
        console.rule(f"[bold cyan]{chat_id}: exporting {scope}")
        exported = tdl.export_chat(chat_id=chat_id, output=temp_path / "export.json", since=since)
        chat_data = archive.merge(original=chat_data, new=exported)
        archive.save(path=chat_path, chat_data=chat_data)

        ledger.sweep_temp_files(path=download_path)
        ledger.lowercase_extensions(path=download_path)
        current = ledger.scan(path=download_path, chat_id=chat_id)
        pending = ledger.find_pending(chat_data=chat_data, current=current)
        console.rule(f"[bold cyan]{chat_id}: {len(current)} on disk, {len(pending)} to download")

        if pending:
            tdl.download(
                pending=pending,
                chat_id=chat_id,
                download_path=download_path,
                request_path=temp_path / "download.json",
            )
            ledger.lowercase_extensions(path=download_path)
            ledger.report_incomplete(pending=pending, chat_id=chat_id, download_path=download_path)

    console.print(f"[green]Done! {chat_id} data saved to {chat_path}")


def run(*chat_ids: str, verify: bool = False) -> None:
    for chat_id in [str(chat_id) for chat_id in chat_ids] or DEFAULT_CHAT_IDS:
        download_media(chat_id=chat_id, verify=verify)


def main() -> None:
    fire.Fire(run)


if __name__ == "__main__":
    main()
