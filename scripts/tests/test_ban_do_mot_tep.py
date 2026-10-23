"""Canh bản đồ ngoại tuyến và các cú pháp Markdown thực tế của nguồn."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "ban-do-mot-tep.py"
SPEC = importlib.util.spec_from_file_location("ban_do_mot_tep", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MAP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MAP)


class BanDoMotTepTest(unittest.TestCase):
    """Kiểm bộ chuyển và tệp thực tế, không dùng DB hoặc mạng."""

    def test_link_co_code_va_html_khong_thuc_thi(self) -> None:
        """Tên link có backtick vẫn nguyên vẹn; HTML thô không được thực thi."""
        self.assertEqual(
            MAP.inline("[`tệp`](lego/index.html)"),
            '<a href="#lego"><code>tệp</code></a>',
        )
        self.assertNotIn("<img", MAP.inline("<img src=x onerror=alert(1)>"))
        self.assertNotIn("<a", MAP.inline("[x](javascript:alert(1))"))

    def test_pipe_trong_code_khong_tao_them_cot(self) -> None:
        """Nguồn có toán tử || và union type trong bảng."""
        output = MAP.markdown("| A | B |\n|---|---|\n| `x||y` | z |")
        self.assertEqual(output.count("<td>"), 2)
        self.assertIn("<code>x||y</code>", output)

    def test_danh_sach_xuong_dong_giu_nhan_manh(self) -> None:
        """Nhấn mạnh trong báo cáo tốc độ trải qua hai dòng vật lý."""
        output = MAP.markdown("- **ba đợt\n   cách nhau** một giây")
        self.assertIn("<strong>ba đợt cách nhau</strong>", output)
        self.assertNotIn("**", output)

    def test_cau_truc_markdown(self) -> None:
        """Tiêu đề, danh sách số, quote và code được đổi thành HTML."""
        output = MAP.markdown(
            "# Một\n\n1. Một\n2. Hai\n\n> câu\n\n```py\n<x>\n```\n\n---"
        )
        for part in ("<h1", "<ol>", "<blockquote>", "&lt;x&gt;", "<hr>"):
            with self.subTest(part=part):
                self.assertIn(part, output)

    def test_nguon_that_khong_lo_ky_hieu(self) -> None:
        """Hai báo cáo phải qua bộ chuyển trọn vẹn."""
        for name in ("VIEC-CAN-LAM.md", "RA-SOAT-TOC-DO.md"):
            with self.subTest(name=name):
                output = MAP.markdown(MAP.read("docs/" + name))
                self.assertNotIn("**", output)
                self.assertNotIn("\x00", output)

    def test_du_lieu_script_khong_dong_the_script(self) -> None:
        """Nội dung nguồn không thể thoát khỏi thẻ JSON/JS đang nhúng."""
        self.assertNotIn("<", MAP.json_script({"x": "</script><img>"}))

    def test_ba_khung_tu_chua_va_giu_duong_di_lego(self) -> None:
        """Ghép bản viết tay không được xoá enrichment của generator gốc."""
        import json
        import re

        for name in ("lego", "he-thong", "so-hoc"):
            with self.subTest(name=name):
                output = MAP.frame_source(name)
                self.assertNotIn('src="data.js"', output)
                self.assertIn("clinicai:'ready'", output)
        output = MAP.frame_source("lego")
        match = re.search(r"window.LEGO=(.*?);/\*<</DU-LIEU", output, re.DOTALL)
        self.assertIsNotNone(match)
        data = json.loads(match[1])
        for consumer in data["consumer"].values():
            self.assertIn("bang_ghi", consumer)
        for operation in data["thao_tac"]:
            with self.subTest(operation=operation["id"]):
                for key in ("buoc", "qua", "ha_tang", "day_nv", "day_ht"):
                    self.assertIn(key, operation)

    def test_sinh_lap_lai_va_tran_dung_luong(self) -> None:
        """Cùng nguồn/commit/ngày phải cho cùng kết quả dưới 15 MB."""
        output = MAP.build()
        self.assertEqual(output, MAP.build())
        self.assertLess(len(output.encode()), 15 * 1024 * 1024)

    def test_cach_doc_moi_giu_du_du_lieu_va_khong_can_tep_kem(self) -> None:
        """Bản đọc và bản gốc phải cùng tập thao tác, nguồn nhúng phải đủ."""
        import json
        import re

        output = MAP.build()
        reader, _ = json.JSONDecoder().raw_decode(
            output.split("window.MAP_DATA=", 1)[1]
        )
        match = re.search(
            r"window.LEGO=(.*?);/\*<</DU-LIEU",
            MAP.frame_source("lego"),
            re.DOTALL,
        )
        source = json.loads(match[1])
        self.assertEqual(reader["lego"], source)
        self.assertEqual(len(reader["tasks"]), 10)
        self.assertEqual(
            [task["number"] for task in reader["tasks"]], list(range(1, 11))
        )
        for placeholder in (
            "__CSS__",
            "__DATA__",
            "__SHELL_JS__",
            "__OVERVIEW_JS__",
            "__LEGO_JS__",
        ):
            self.assertNotIn(placeholder, output)
        # Các tệp giao diện là nguồn lúc sinh, không thành tài nguyên lúc mở.
        self.assertNotIn('<script src="', output)
        self.assertNotIn('<link rel="stylesheet"', output)


if __name__ == "__main__":
    unittest.main()
