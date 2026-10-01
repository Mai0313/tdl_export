from typing import Any, Self
from pathlib import Path
import subprocess

import pytest

from tdl_export import tdl
from tdl_export.archive import Message, ChatData


class TestGetMediaSize:
    def test_document(self) -> None:
        assert tdl.get_media_size({"Media": {"Document": {"Size": 42}}}) == 42

    def test_photo_takes_the_last_size(self) -> None:
        raw = {"Media": {"Photo": {"Sizes": [{"Size": 10}, {"Size": 20}]}}}
        assert tdl.get_media_size(raw) == 20

    def test_progressive_photo_takes_its_last_byte_count(self) -> None:
        raw = {"Media": {"Photo": {"Sizes": [{"Size": 10}, {"Sizes": [5, 50, 500]}]}}}
        assert tdl.get_media_size(raw) == 500

    @pytest.mark.parametrize(
        "raw",
        [{}, {"Media": None}, {"Media": {"Photo": {"Sizes": []}}}, {"Media": {"Webpage": {}}}],
    )
    def test_no_downloadable_media(self, raw: dict[str, Any]) -> None:
        assert tdl.get_media_size(raw) is None


def test_activity_counts_entries_and_temp_bytes(tmp_path: Path) -> None:
    (tmp_path / "done.mp4").write_bytes(b"xx")
    (tmp_path / "part.mp4.tmp").write_bytes(b"xxx")
    assert tdl.activity(tmp_path) == (2, 3)


def test_activity_sees_a_temp_file_that_is_still_being_written(tmp_path: Path) -> None:
    with (tmp_path / "part.mp4.tmp").open("wb") as handle:
        handle.write(b"x" * 1000)
        handle.flush()
        assert tdl.activity(tmp_path) == (1, 1000)


class Scripted:
    """A `tdl dl` whose `wait` calls play back `outcomes`: an exception is raised, an int returned."""

    def __init__(self, *outcomes: BaseException | int) -> None:
        self.outcomes = list(outcomes)
        self.killed = False

    def __enter__(self) -> Self:
        """Mirror `subprocess.Popen` as a context manager."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Nothing to reap."""

    def wait(self, timeout: float | None = None) -> int:
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def kill(self) -> None:
        self.killed = True


def start(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, process: Scripted) -> None:
    monkeypatch.setattr(subprocess, "Popen", lambda command: process)
    pending = ChatData(id=1, messages=[Message(id=1, file="a.jpg")])
    tdl.download(pending, tmp_path, tmp_path / "request.json", limit=4, threads=4)


def test_ctrl_c_lets_tdl_shut_down_on_its_own(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    process = Scripted(KeyboardInterrupt(), 0)
    with pytest.raises(KeyboardInterrupt):
        start(monkeypatch, tmp_path, process)
    assert not process.killed
    assert process.outcomes == [], "tdl was waited for after the interrupt"


def test_any_other_error_kills_tdl_first(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    process = Scripted(OSError("folder gone"), 0)
    with pytest.raises(OSError, match="folder gone"):
        start(monkeypatch, tmp_path, process)
    assert process.killed
