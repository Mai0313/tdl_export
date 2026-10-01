import json
from typing import Any
from pathlib import Path

import pytest

from conftest import FakeTdl
from tdl_export import cli
from tdl_export.cli import Message, ChatData

CHAT = 1001


def write(path: Path, size: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


class TestGetMediaSize:
    def test_document(self) -> None:
        assert cli.get_media_size({"Media": {"Document": {"Size": 42}}}) == 42

    def test_photo_takes_the_last_size(self) -> None:
        raw = {"Media": {"Photo": {"Sizes": [{"Size": 10}, {"Size": 20}]}}}
        assert cli.get_media_size(raw) == 20

    def test_progressive_photo_takes_its_last_byte_count(self) -> None:
        raw = {"Media": {"Photo": {"Sizes": [{"Size": 10}, {"Sizes": [5, 50, 500]}]}}}
        assert cli.get_media_size(raw) == 500

    @pytest.mark.parametrize(
        "raw",
        [{}, {"Media": None}, {"Media": {"Photo": {"Sizes": []}}}, {"Media": {"Webpage": {}}}],
    )
    def test_no_downloadable_media(self, raw: dict[str, Any]) -> None:
        assert cli.get_media_size(raw) is None


class TestArchive:
    def test_missing_archive_is_empty(self, tmp_path: Path) -> None:
        assert cli.load_chat_data(tmp_path / "absent.json") == ChatData()

    def test_round_trip_leaves_no_staging_file(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "chat.json"
        data = ChatData(id=CHAT, messages=[Message(id=1, file="a.jpg", size=3, text="hi")])
        cli.save_chat_data(path, data)
        assert cli.load_chat_data(path) == data
        assert [p.name for p in path.parent.iterdir()] == ["chat.json"]

    def test_merge_prefers_the_new_copy_and_sorts_newest_first(self) -> None:
        old = ChatData(id=CHAT, messages=[Message(id=1, text="old"), Message(id=2)])
        new = ChatData(id=CHAT, messages=[Message(id=3), Message(id=1, text="edited")])
        merged = cli.merge_chat_data(old, new)
        assert [m.id for m in merged.messages] == [3, 2, 1]
        assert merged.messages[-1].text == "edited"


class TestDisk:
    def test_sweep_removes_only_temp_files(self, tmp_path: Path) -> None:
        keep = write(tmp_path / f"{CHAT}_1_a.mp4", 1)
        write(tmp_path / f"{CHAT}_2_b.mp4.tmp", 1)
        cli.sweep_temp_files(tmp_path)
        assert list(tmp_path.iterdir()) == [keep]

    def test_lowercase_extensions(self, tmp_path: Path) -> None:
        write(tmp_path / "a.MP4", 1)
        (tmp_path / "dir.X").mkdir()
        cli.lowercase_extensions(tmp_path)
        assert sorted(p.name for p in tmp_path.iterdir()) == ["a.mp4", "dir.X"]

    def test_lowercase_keeps_a_file_whose_target_exists(self, tmp_path: Path) -> None:
        write(tmp_path / "a.JPG", 1)
        if (tmp_path / "a.jpg").exists():
            pytest.skip("both names can only coexist on a case-sensitive filesystem")
        write(tmp_path / "a.jpg", 2)
        cli.lowercase_extensions(tmp_path)
        assert sorted(p.name for p in tmp_path.iterdir()) == ["a.JPG", "a.jpg"]

    def test_scan_reads_only_this_chats_prefix(self, tmp_path: Path) -> None:
        mine = write(tmp_path / f"{CHAT}_7_name_with_7_.mp4", 1)
        write(tmp_path / f"{CHAT}_8_partial.mp4.tmp", 1)
        write(tmp_path / f"9{CHAT}_9_other_chat.mp4", 1)
        write(tmp_path / "unrelated.txt", 1)
        assert cli.get_all_current_file(tmp_path, str(CHAT)) == {7: mine}

    def test_pending(self, tmp_path: Path) -> None:
        complete = write(tmp_path / f"{CHAT}_1_a", 5)
        truncated = write(tmp_path / f"{CHAT}_2_b", 3)
        unsized = write(tmp_path / f"{CHAT}_3_c", 9)
        chat = ChatData(
            id=CHAT,
            messages=[
                Message(id=1, file="a", size=5),
                Message(id=2, file="b", size=5),
                Message(id=3, file="c", size=None),
                Message(id=4, file="d", size=5),
                Message(id=5, file="", size=None),
            ],
        )
        current = {1: complete, 2: truncated, 3: unsized}
        pending = cli.get_pending_messages(chat, current)
        assert [m.id for m in pending] == [2, 4]
        assert not truncated.exists(), "a wrong-size file is removed before it is fetched again"
        assert complete.exists()
        assert unsized.exists()


class TestDownloadMedia:
    def test_first_run_exports_everything_and_downloads_every_file(
        self, fake_tdl: FakeTdl, isolated_data: Path
    ) -> None:
        fake_tdl.add(CHAT, 1, "a.jpg", 4)
        fake_tdl.add(CHAT, 2)
        fake_tdl.add(CHAT, 3, "c.mp4", 6)

        cli.download_media(str(CHAT))

        export, download = fake_tdl.calls
        assert "--input" not in export
        assert {"--all", "--with-content", "--raw"} <= set(export)
        assert download[download.index("--template") + 1] == cli.NAME_TEMPLATE
        assert "--continue" in download
        folder = isolated_data / "downloads" / str(CHAT)
        assert sorted(p.name for p in folder.iterdir()) == [f"{CHAT}_1_a.jpg", f"{CHAT}_3_c.mp4"]
        archive = cli.load_chat_data(isolated_data / "chats" / f"{CHAT}.json")
        assert [(m.id, m.size) for m in archive.messages] == [(3, 6), (2, None), (1, 4)]

    def test_request_file_puts_a_numeric_chat_id_first(self, fake_tdl: FakeTdl) -> None:
        fake_tdl.add(CHAT, 1, "a.jpg", 4)
        cli.download_media(str(CHAT))
        (request_text,) = fake_tdl.requests
        assert request_text.lstrip().startswith('{\n  "id": 1001')
        request = json.loads(request_text)
        assert request["messages"] == [{"id": 1, "type": "message", "file": "a.jpg"}]

    def test_next_run_is_incremental_and_skips_what_is_on_disk(self, fake_tdl: FakeTdl) -> None:
        fake_tdl.add(CHAT, 1, "a.jpg", 4)
        cli.download_media(str(CHAT))
        fake_tdl.add(CHAT, 5, "e.jpg", 2)
        fake_tdl.calls.clear()
        fake_tdl.requests.clear()

        cli.download_media(str(CHAT))

        export, _ = fake_tdl.calls
        assert export[export.index("--input") + 1] == "2"
        (request_text,) = fake_tdl.requests
        assert [m["id"] for m in json.loads(request_text)["messages"]] == [5]

    def test_nothing_pending_means_no_download(self, fake_tdl: FakeTdl) -> None:
        fake_tdl.add(CHAT, 1)
        cli.download_media(str(CHAT))
        assert len(fake_tdl.calls) == 1

    def test_truncated_download_is_reported_then_fetched_again(
        self, fake_tdl: FakeTdl, isolated_data: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        fake_tdl.add(CHAT, 1, "a.mp4", 10)
        fake_tdl.written_size[1] = 3

        cli.download_media(str(CHAT))
        assert "1 message(s) still missing or incomplete: 1" in capsys.readouterr().out

        del fake_tdl.written_size[1]
        cli.download_media(str(CHAT))
        assert "still missing" not in capsys.readouterr().out
        target = isolated_data / "downloads" / str(CHAT) / f"{CHAT}_1_a.mp4"
        assert target.stat().st_size == 10

    def test_an_archive_without_sizes_forces_a_full_export(
        self, fake_tdl: FakeTdl, isolated_data: Path
    ) -> None:
        cli.save_chat_data(
            isolated_data / "chats" / f"{CHAT}.json",
            ChatData(id=CHAT, messages=[Message(id=1, file="a.jpg")]),
        )
        fake_tdl.add(CHAT, 1, "a.jpg", 4)
        cli.download_media(str(CHAT))
        assert "--input" not in fake_tdl.calls[0]

    def test_verify_forces_a_full_export(self, fake_tdl: FakeTdl) -> None:
        fake_tdl.add(CHAT, 1, "a.jpg", 4)
        cli.download_media(str(CHAT))
        fake_tdl.calls.clear()
        cli.download_media(str(CHAT), verify=True)
        assert "--input" not in fake_tdl.calls[0]

    def test_stale_temp_files_and_upper_case_extensions_are_cleaned_first(
        self, fake_tdl: FakeTdl, isolated_data: Path
    ) -> None:
        folder = isolated_data / "downloads" / str(CHAT)
        write(folder / f"{CHAT}_1_a.JPG", 4)
        write(folder / f"{CHAT}_2_b.mp4.tmp", 1)
        fake_tdl.add(CHAT, 1, "a.JPG", 4)
        cli.download_media(str(CHAT))
        assert [p.name for p in folder.iterdir()] == [f"{CHAT}_1_a.jpg"]
        assert len(fake_tdl.calls) == 1, "the renamed file still counts as downloaded"


def test_run_falls_back_to_the_default_chats(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        cli, "download_media", lambda chat_id, verify: seen.append((chat_id, verify))
    )
    cli.run()
    assert seen == [(chat_id, False) for chat_id in cli.DEFAULT_CHAT_IDS]
    seen.clear()
    cli.run("5", "6", verify=True)
    assert seen == [("5", True), ("6", True)]
