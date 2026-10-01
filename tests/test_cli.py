import sys
import json
from pathlib import Path
import subprocess

import pytest

from conftest import CHAT, FakeTdl, write
from tdl_export import cli, tdl, archive
from tdl_export.archive import Message, ChatData

OTHER = 2002


def downloads(fake: FakeTdl) -> list[list[str]]:
    return [command for command in fake.calls if command[1] == "dl"]


def exports(fake: FakeTdl) -> list[list[str]]:
    return [command for command in fake.calls if command[1] == "chat"]


def table_row(out: str, chat_id: int) -> list[str]:
    """The cells of the summary row for `chat_id`, box-drawing characters stripped."""
    for line in out.splitlines():
        cells = [cell.strip() for cell in line.strip()[1:-1].split("│")]
        if cells[0] == str(chat_id):
            return cells
    raise AssertionError(f"no summary row for {chat_id} in:\n{out}")


class TestRun:
    def test_first_run_exports_everything_and_downloads_every_file(
        self, fake_tdl: FakeTdl, isolated_data: Path
    ) -> None:
        fake_tdl.add(CHAT, 1, "a.jpg", 4)
        fake_tdl.add(CHAT, 2)
        fake_tdl.add(CHAT, 3, "c.mp4", 6)

        cli.run(CHAT)

        (export,) = exports(fake_tdl)
        assert "--input" not in export
        assert {"--all", "--with-content", "--raw"} <= set(export)
        (download,) = downloads(fake_tdl)
        assert FakeTdl.flag(download, "--template") == tdl.NAME_TEMPLATE
        assert (
            FakeTdl.flag(download, "--dir") == (isolated_data / "downloads" / str(CHAT)).as_posix()
        )
        assert "--restart" in download
        assert "--continue" not in download
        folder = isolated_data / "downloads" / str(CHAT)
        assert sorted(p.name for p in folder.iterdir()) == [f"{CHAT}_1_a.jpg", f"{CHAT}_3_c.mp4"]
        saved = archive.load(isolated_data / "chats" / f"{CHAT}.json")
        assert [(m.id, m.size) for m in saved.messages] == [(3, 6), (2, None), (1, 4)]

    def test_concurrency_is_always_passed_explicitly(self, fake_tdl: FakeTdl) -> None:
        fake_tdl.add(CHAT, 1, "a.jpg", 4)
        fake_tdl.add(OTHER, 1, "b.jpg", 4)
        cli.run(CHAT)
        cli.run(OTHER, limit=8, threads=2)
        first, second = downloads(fake_tdl)
        assert FakeTdl.flag(first, "--limit") == str(tdl.LIMIT)
        assert FakeTdl.flag(first, "--threads") == str(tdl.THREADS)
        assert FakeTdl.flag(second, "--limit") == "8"
        assert FakeTdl.flag(second, "--threads") == "2"

    def test_request_file_puts_a_numeric_chat_id_first(self, fake_tdl: FakeTdl) -> None:
        fake_tdl.add(CHAT, 1, "a.jpg", 4)
        cli.run(CHAT)
        (request_text,) = fake_tdl.requests
        assert request_text.lstrip().startswith('{\n  "id": 1001')
        request = json.loads(request_text)
        assert request["messages"] == [{"id": 1, "type": "message", "file": "a.jpg"}]

    def test_every_chat_is_exported_before_any_download(
        self, fake_tdl: FakeTdl, isolated_data: Path
    ) -> None:
        fake_tdl.add(CHAT, 1, "a.jpg", 4)
        fake_tdl.add(OTHER, 7, "b.jpg", 5)
        fake_tdl.add(3003, 1)

        cli.run(CHAT, OTHER, 3003)

        assert [command[1] for command in fake_tdl.calls] == ["chat"] * 3 + ["dl"] * 2
        assert [command.count("--file") for command in downloads(fake_tdl)] == [1, 1]
        assert (isolated_data / "downloads" / str(CHAT) / f"{CHAT}_1_a.jpg").exists()
        assert (isolated_data / "downloads" / str(OTHER) / f"{OTHER}_7_b.jpg").exists()

    def test_next_run_is_incremental_and_skips_what_is_on_disk(self, fake_tdl: FakeTdl) -> None:
        fake_tdl.add(CHAT, 1, "a.jpg", 4)
        cli.run(CHAT)
        fake_tdl.add(CHAT, 5, "e.jpg", 2)
        fake_tdl.calls.clear()
        fake_tdl.requests.clear()

        cli.run(CHAT)

        (export,) = exports(fake_tdl)
        assert FakeTdl.flag(export, "--input") == "2"
        (request_text,) = fake_tdl.requests
        assert [m["id"] for m in json.loads(request_text)["messages"]] == [5]

    def test_nothing_pending_means_no_download(self, fake_tdl: FakeTdl) -> None:
        fake_tdl.add(CHAT, 1)
        cli.run(CHAT)
        assert downloads(fake_tdl) == []

    def test_truncated_download_is_reported_then_fetched_again(
        self, fake_tdl: FakeTdl, isolated_data: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fake_tdl.add(CHAT, 1, "a.mp4", 10)
        fake_tdl.add(CHAT, 2, "b.mp4", 10)
        fake_tdl.written_size[1] = 3

        cli.run(CHAT)
        assert table_row(capsys.readouterr().out, CHAT) == [str(CHAT), "2", "1", "1"]

        del fake_tdl.written_size[1]
        cli.run(CHAT)
        assert [m["id"] for m in json.loads(fake_tdl.requests[-1])["messages"]] == [1]
        target = isolated_data / "downloads" / str(CHAT) / f"{CHAT}_1_a.mp4"
        assert target.stat().st_size == 10

    def test_an_archive_without_sizes_forces_a_full_export(
        self, fake_tdl: FakeTdl, isolated_data: Path
    ) -> None:
        archive.save(
            isolated_data / "chats" / f"{CHAT}.json",
            ChatData(id=CHAT, messages=[Message(id=1, file="a.jpg")]),
        )
        fake_tdl.add(CHAT, 1, "a.jpg", 4)
        cli.run(CHAT)
        assert "--input" not in exports(fake_tdl)[0]

    def test_verify_forces_a_full_export(self, fake_tdl: FakeTdl) -> None:
        fake_tdl.add(CHAT, 1, "a.jpg", 4)
        cli.run(CHAT)
        fake_tdl.calls.clear()
        cli.run(CHAT, verify=True)
        assert "--input" not in exports(fake_tdl)[0]

    def test_stale_temp_files_and_upper_case_extensions_are_cleaned_first(
        self, fake_tdl: FakeTdl, isolated_data: Path
    ) -> None:
        folder = isolated_data / "downloads" / str(CHAT)
        write(folder / f"{CHAT}_1_a.JPG", 4)
        write(folder / f"{CHAT}_2_b.mp4.tmp", 1)
        fake_tdl.add(CHAT, 1, "a.JPG", 4)
        cli.run(CHAT)
        assert [p.name for p in folder.iterdir()] == [f"{CHAT}_1_a.jpg"]
        assert downloads(fake_tdl) == [], "the renamed file still counts as downloaded"

    def test_a_failed_export_skips_that_chat_only(
        self, fake_tdl: FakeTdl, isolated_data: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fake_tdl.add(CHAT, 1, "a.jpg", 4)
        fake_tdl.add(OTHER, 7, "b.jpg", 5)
        fake_tdl.failing_exports.add(CHAT)

        with pytest.raises(SystemExit) as exited:
            cli.run(CHAT, OTHER)

        assert exited.value.code == 1
        assert [json.loads(text)["id"] for text in fake_tdl.requests] == [OTHER]
        assert not (isolated_data / "chats" / f"{CHAT}.json").exists()
        assert f"{CHAT}: export failed" in capsys.readouterr().out

    def test_a_failed_download_is_still_measured(
        self, fake_tdl: FakeTdl, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fake_tdl.add(CHAT, 1, "a.jpg", 4)
        fake_tdl.add(OTHER, 7, "b.jpg", 5)
        fake_tdl.failing_downloads.add(CHAT)

        with pytest.raises(SystemExit) as exited:
            cli.run(CHAT, OTHER)

        assert exited.value.code == 1
        assert len(downloads(fake_tdl)) == 2, "the other chat still gets its own download"
        out = capsys.readouterr().out
        assert table_row(out, CHAT) == [str(CHAT), "1", "1", ""]
        assert table_row(out, OTHER) == [str(OTHER), "1", "1", ""]
        assert f"{CHAT}: tdl dl stopped early" in out

    def test_an_interrupted_export_leaves_the_archive_alone(
        self, fake_tdl: FakeTdl, isolated_data: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_tdl.add(CHAT, 1, "a.jpg", 4)
        cli.run(CHAT)
        path = isolated_data / "chats" / f"{CHAT}.json"
        before = path.read_bytes()

        def interrupted(command: list[str], check: bool) -> None:
            # tdl writes valid JSON even when stopped, so only the interrupt stops the merge.
            fake_tdl(command, check)
            raise KeyboardInterrupt

        fake_tdl.add(CHAT, 9, "z.jpg", 4)
        monkeypatch.setattr(subprocess, "run", interrupted)
        with pytest.raises(KeyboardInterrupt):
            cli.run(CHAT)
        assert path.read_bytes() == before

    def test_newest_media_download_first(self, fake_tdl: FakeTdl) -> None:
        fake_tdl.add(CHAT, 1, "a.jpg", 4)
        cli.run(CHAT)
        (download,) = downloads(fake_tdl)
        assert "--desc" in download

    def test_a_stalled_download_is_stopped_and_the_next_chat_still_runs(
        self, fake_tdl: FakeTdl, isolated_data: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fake_tdl.add(CHAT, 1, "a.jpg", 4)
        fake_tdl.add(OTHER, 7, "b.jpg", 5)
        fake_tdl.download_waits[CHAT] = -1

        with pytest.raises(SystemExit) as exited:
            cli.run(CHAT, OTHER)

        assert exited.value.code == 1
        assert fake_tdl.processes[CHAT].terminated
        assert not fake_tdl.processes[OTHER].terminated
        assert (isolated_data / "downloads" / str(OTHER) / f"{OTHER}_7_b.jpg").exists()
        assert f"{CHAT}: nothing arrived for 5 minutes" in capsys.readouterr().out

    def test_slow_progress_is_not_a_stall(self, fake_tdl: FakeTdl) -> None:
        fake_tdl.add(CHAT, 1, "a.jpg", 4)
        fake_tdl.download_waits[CHAT] = 3
        cli.run(CHAT)
        assert not fake_tdl.processes[CHAT].terminated

    @pytest.mark.parametrize(("limit", "threads"), [(0, 4), (4, 0), (-1, 4)])
    def test_concurrency_below_one_is_refused(
        self, fake_tdl: FakeTdl, limit: int, threads: int
    ) -> None:
        with pytest.raises(SystemExit, match="at least 1"):
            cli.run(CHAT, limit=limit, threads=threads)
        assert fake_tdl.calls == []

    def test_no_arguments_means_the_default_chats(self, fake_tdl: FakeTdl) -> None:
        cli.run()
        chats = [int(FakeTdl.flag(command, "--chat") or "0") for command in exports(fake_tdl)]
        assert chats == cli.DEFAULT_CHAT_IDS


def test_interrupt_ends_with_a_hint_instead_of_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def interrupted() -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run", interrupted)
    monkeypatch.setattr(sys, "argv", ["tdl_export"])
    with pytest.raises(SystemExit) as exited:
        cli.main()
    assert exited.value.code == 130
    assert "Run it again" in capsys.readouterr().out
