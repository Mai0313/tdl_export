from typing import Any

import pytest

from tdl_export import tdl


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
