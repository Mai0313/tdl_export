from pathlib import Path

from conftest import CHAT
from tdl_export import archive
from tdl_export.archive import Message, ChatData


class TestArchive:
    def test_missing_archive_is_empty(self, tmp_path: Path) -> None:
        assert archive.load(tmp_path / "absent.json") == ChatData()

    def test_round_trip_leaves_no_staging_file(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "chat.json"
        data = ChatData(id=CHAT, messages=[Message(id=1, file="a.jpg", size=3, text="hi")])
        archive.save(path, data)
        assert archive.load(path) == data
        assert [p.name for p in path.parent.iterdir()] == ["chat.json"]

    def test_merge_prefers_the_new_copy_and_sorts_newest_first(self) -> None:
        old = ChatData(id=CHAT, messages=[Message(id=1, text="old"), Message(id=2)])
        new = ChatData(id=CHAT, messages=[Message(id=3), Message(id=1, text="edited")])
        merged = archive.merge(old, new)
        assert [m.id for m in merged.messages] == [3, 2, 1]
        assert merged.messages[-1].text == "edited"
