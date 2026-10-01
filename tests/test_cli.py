import json
from pathlib import Path

import pytest

from conftest import CHAT, FakeTdl, write
from tdl_export import cli, tdl, archive
from tdl_export.archive import Message, ChatData


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
        assert download[download.index("--template") + 1] == tdl.NAME_TEMPLATE
        assert "--continue" in download
        folder = isolated_data / "downloads" / str(CHAT)
        assert sorted(p.name for p in folder.iterdir()) == [f"{CHAT}_1_a.jpg", f"{CHAT}_3_c.mp4"]
        saved = archive.load(isolated_data / "chats" / f"{CHAT}.json")
        assert [(m.id, m.size) for m in saved.messages] == [(3, 6), (2, None), (1, 4)]

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
        archive.save(
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
