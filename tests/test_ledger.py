from pathlib import Path

import pytest

from conftest import CHAT, write
from tdl_export import ledger
from tdl_export.archive import Message, ChatData


class TestDisk:
    def test_sweep_removes_only_temp_files(self, tmp_path: Path) -> None:
        keep = write(tmp_path / f"{CHAT}_1_a.mp4", 1)
        write(tmp_path / f"{CHAT}_2_b.mp4.tmp", 1)
        ledger.sweep_temp_files(tmp_path)
        assert list(tmp_path.iterdir()) == [keep]

    def test_lowercase_extensions(self, tmp_path: Path) -> None:
        write(tmp_path / "a.MP4", 1)
        (tmp_path / "dir.X").mkdir()
        ledger.lowercase_extensions(tmp_path)
        assert sorted(p.name for p in tmp_path.iterdir()) == ["a.mp4", "dir.X"]

    def test_lowercase_keeps_a_file_whose_target_exists(self, tmp_path: Path) -> None:
        write(tmp_path / "a.JPG", 1)
        if (tmp_path / "a.jpg").exists():
            pytest.skip("both names can only coexist on a case-sensitive filesystem")
        write(tmp_path / "a.jpg", 2)
        ledger.lowercase_extensions(tmp_path)
        assert sorted(p.name for p in tmp_path.iterdir()) == ["a.JPG", "a.jpg"]

    def test_scan_reads_only_this_chats_prefix(self, tmp_path: Path) -> None:
        mine = write(tmp_path / f"{CHAT}_7_name_with_7_.mp4", 1)
        write(tmp_path / f"{CHAT}_8_partial.mp4.tmp", 1)
        write(tmp_path / f"9{CHAT}_9_other_chat.mp4", 1)
        write(tmp_path / "unrelated.txt", 1)
        assert ledger.scan(tmp_path, CHAT) == {7: mine}

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
        pending = ledger.find_pending(chat, current)
        assert [m.id for m in pending] == [2, 4]
        assert not truncated.exists(), "a wrong-size file is removed before it is fetched again"
        assert complete.exists()
        assert unsized.exists()

    def test_incomplete_is_missing_or_wrong_size(self, tmp_path: Path) -> None:
        write(tmp_path / f"{CHAT}_1_a", 5)
        write(tmp_path / f"{CHAT}_2_b", 3)
        write(tmp_path / f"{CHAT}_3_c", 9)
        pending = [
            Message(id=1, file="a", size=5),
            Message(id=2, file="b", size=5),
            Message(id=3, file="c", size=None),
            Message(id=4, file="d", size=5),
        ]
        assert ledger.find_incomplete(pending, tmp_path, CHAT) == [2, 4]
