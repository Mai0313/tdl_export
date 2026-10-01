import json
from typing import Any, Self
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
    monkeypatch.setattr(subprocess, "Popen", refuse)
    return tmp_path


class FakeProcess:
    """A `tdl dl` that has already written its files, and finishes or stalls as configured.

    `waits` is how many `wait` calls time out first, each adding a file to `directory` as progress;
    a negative count never finishes and never writes anything more.
    """

    def __init__(self, directory: Path, waits: int, returncode: int) -> None:
        self.directory = directory
        self.waits = waits
        self.final = returncode
        self.returncode: int | None = None
        self.terminated = False
        self.idle_waits = 0

    def __enter__(self) -> Self:
        """Mirror `subprocess.Popen` as a context manager."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Nothing to reap: the fake never started a process."""
        return

    def wait(self, timeout: float | None = None) -> int:
        if self.terminated or self.waits == 0:
            self.returncode = 1 if self.terminated else self.final
            return self.returncode
        if self.waits > 0:
            self.waits -= 1
            (self.directory / f"progress-{self.waits}.tmp").write_bytes(b"x")
        else:
            self.idle_waits += 1
            # A watchdog that never fires would otherwise hang the test instead of failing it.
            assert self.idle_waits < 3, "a download that writes nothing was never stopped"
        raise subprocess.TimeoutExpired("tdl", timeout or 0)

    def kill(self) -> None:
        self.terminated = True


class FakeTdl:
    """Stands in for the tdl binary: serves each chat's history and writes the files asked for.

    `history` maps chat id to its messages as `tdl chat export --all --with-content --raw` emits
    them. `written_size` decides how many bytes a download writes, so a test can make tdl "succeed"
    with a truncated file the way the real one does. `failing_exports` and `failing_downloads` make
    the process for those chats exit non-zero, a download only after writing its files.
    `download_waits` hands a chat's download process its `FakeProcess.waits`.
    """

    def __init__(self) -> None:
        self.history: dict[int, list[dict[str, Any]]] = {}
        self.written_size: dict[int, int] = {}
        self.failing_exports: set[int] = set()
        self.failing_downloads: set[int] = set()
        self.download_waits: dict[int, int] = {}
        self.calls: list[list[str]] = []
        self.requests: list[str] = []
        self.processes: dict[int, FakeProcess] = {}

    def add(self, chat_id: int, message_id: int, file: str = "", size: int | None = None) -> None:
        raw: dict[str, Any] = {}
        if size is not None:
            raw = {"Media": {"Document": {"Size": size}}}
        entry = {"id": message_id, "type": "message", "file": file, "date": 1700000000, "raw": raw}
        self.history.setdefault(chat_id, []).append(entry)

    @staticmethod
    def flag(command: list[str], name: str) -> str | None:
        return command[command.index(name) + 1] if name in command else None

    def __call__(self, command: list[str], check: bool) -> subprocess.CompletedProcess[str]:
        """`tdl chat export`, run to completion."""
        assert check
        assert command[1:3] == ["chat", "export"], command
        self.calls.append(command)
        chat_id = int(self.flag(command, "--chat") or "0")
        if chat_id in self.failing_exports:
            raise subprocess.CalledProcessError(1, command)
        since = int(self.flag(command, "--input") or "0")
        messages = sorted(
            (m for m in self.history.get(chat_id, []) if m["id"] >= since),
            key=lambda m: m["id"],
            reverse=True,
        )
        output = Path(self.flag(command, "--output") or "")
        output.write_text(json.dumps({"id": chat_id, "messages": messages}), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    def popen(self, command: list[str]) -> FakeProcess:
        """`tdl dl`, started in the background."""
        assert command[1] == "dl", command
        self.calls.append(command)
        request_text = Path(self.flag(command, "--file") or "").read_text(encoding="utf-8")
        self.requests.append(request_text)
        request = json.loads(request_text)
        chat_id = request["id"]
        directory = Path(self.flag(command, "--dir") or "")
        template = self.flag(command, "--template") or ""
        sizes = {
            m["id"]: m["raw"]["Media"]["Document"]["Size"]
            for m in self.history[chat_id]
            if m["raw"]
        }
        for message in request["messages"]:
            written = self.written_size.get(message["id"], sizes[message["id"]])
            name = (
                template
                .replace("{{ .DialogID }}", str(chat_id))
                .replace("{{ .MessageID }}", str(message["id"]))
                .replace("{{ filenamify .FileName }}", message["file"])
            )
            (directory / name).write_bytes(b"x" * written)
        process = FakeProcess(
            directory=directory,
            waits=self.download_waits.get(chat_id, 0),
            returncode=1 if chat_id in self.failing_downloads else 0,
        )
        self.processes[chat_id] = process
        return process


@pytest.fixture
def fake_tdl(monkeypatch: pytest.MonkeyPatch) -> FakeTdl:
    fake = FakeTdl()
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr(subprocess, "Popen", fake.popen)
    return fake
