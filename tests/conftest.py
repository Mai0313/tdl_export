import json
from typing import Any
from pathlib import Path
import subprocess

import pytest
from rich.console import Console

from tdl_export import cli, ledger

CHAT = 1001


def write(path: Path, size: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


@pytest.fixture(autouse=True)
def isolated_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every data path at a temp dir and refuse to run a real tdl."""
    monkeypatch.setattr(cli, "CHAT_DIR", tmp_path / "chats")
    monkeypatch.setattr(cli, "DOWNLOAD_DIR", tmp_path / "downloads")
    # Plain and wide, so assertions on the text hold whatever FORCE_COLOR or COLUMNS says.
    plain = Console(force_terminal=False, width=200)
    monkeypatch.setattr(cli, "console", plain)
    monkeypatch.setattr(ledger, "console", plain)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"unexpected subprocess call: {args} {kwargs}")

    monkeypatch.setattr(subprocess, "run", refuse)
    return tmp_path


class FakeTdl:
    """Stands in for the tdl binary: serves a chat's history and writes the files it is asked for.

    `history` maps chat id to its messages as `tdl chat export --all --with-content --raw` emits
    them. `written_size` decides how many bytes each download writes, so a test can make tdl "succeed"
    with a truncated file the way the real one does.
    """

    def __init__(self) -> None:
        self.history: dict[int, list[dict[str, Any]]] = {}
        self.written_size: dict[int, int] = {}
        self.calls: list[list[str]] = []
        self.requests: list[str] = []

    def add(self, chat_id: int, message_id: int, file: str = "", size: int | None = None) -> None:
        raw: dict[str, Any] = {}
        if size is not None:
            raw = {"Media": {"Document": {"Size": size}}}
        entry = {"id": message_id, "type": "message", "file": file, "date": 1700000000, "raw": raw}
        self.history.setdefault(chat_id, []).append(entry)

    def __call__(self, command: list[str], check: bool) -> subprocess.CompletedProcess[str]:
        assert check
        self.calls.append(command)
        if command[1:3] == ["chat", "export"]:
            self._export(command)
        elif command[1] == "dl":
            self._download(command)
        else:
            raise AssertionError(f"unexpected tdl command: {command}")
        return subprocess.CompletedProcess(command, 0)

    @staticmethod
    def _flag(command: list[str], name: str) -> str | None:
        return command[command.index(name) + 1] if name in command else None

    def _export(self, command: list[str]) -> None:
        chat_id = int(self._flag(command, "--chat") or "0")
        since = int(self._flag(command, "--input") or "0")
        messages = sorted(
            (m for m in self.history.get(chat_id, []) if m["id"] >= since),
            key=lambda m: m["id"],
            reverse=True,
        )
        output = Path(self._flag(command, "--output") or "")
        output.write_text(json.dumps({"id": chat_id, "messages": messages}), encoding="utf-8")

    def _download(self, command: list[str]) -> None:
        request_text = Path(self._flag(command, "--file") or "").read_text(encoding="utf-8")
        self.requests.append(request_text)
        request = json.loads(request_text)
        directory = Path(self._flag(command, "--dir") or "")
        sizes = {m["id"]: m for m in self.history[request["id"]]}
        for message in request["messages"]:
            full = sizes[message["id"]]["raw"]["Media"]["Document"]["Size"]
            written = self.written_size.get(message["id"], full)
            target = directory / f"{request['id']}_{message['id']}_{message['file']}"
            target.write_bytes(b"x" * written)


@pytest.fixture
def fake_tdl(monkeypatch: pytest.MonkeyPatch) -> FakeTdl:
    fake = FakeTdl()
    monkeypatch.setattr(subprocess, "run", fake)
    return fake
