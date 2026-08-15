"""Bot lệnh Telegram — các luật giữ cho nó an toàn và nói thật."""

from __future__ import annotations

import inspect

from clinicai.services import telegram_bot as bot


class TestDocLenh:
    def test_lenh_thuong(self) -> None:
        assert bot.doc_lenh("/trangthai") == "trangthai"

    def test_lenh_kem_ten_bot_va_tham_so(self) -> None:
        assert bot.doc_lenh("/homnay@chat_Tuyen_bot xxx") == "homnay"

    def test_chu_thuong_khong_phai_lenh(self) -> None:
        assert bot.doc_lenh("xin chào") is None
        assert bot.doc_lenh("") is None
        assert bot.doc_lenh(None) is None
        assert bot.doc_lenh("/") is None


class TestLuatAnToan:
    def test_chi_tra_loi_dung_chat_da_cau_hinh(self) -> None:
        """Bot đọc được con số vận hành — người lạ nhắn thì lờ đi + ghi vết,
        không có nhánh nào trả lời chat khác chat cấu hình."""
        ma = inspect.getsource(bot.bot_lenh_loop)
        assert "chat != chat_id_cau_hinh" in ma
        assert "bot_lenh_nguoi_la" in ma

    def test_menu_tu_dang_ky_moi_lan_start(self) -> None:
        """Bot từng dính menu rác của project cũ — menu phải được ghi đè lúc
        khởi động, không phụ thuộc ai nhớ chạy lệnh tay."""
        ma = inspect.getsource(bot.bot_lenh_loop)
        assert "_dang_ky_menu" in ma
        assert "_offset_bo_ton_dong" in ma, (
            "phải bỏ lệnh gõ trước khi bot chạy — trả lời câu hỏi hôm qua "
            "bằng số hôm nay là đưa tin sai"
        )

    def test_hom_nay_chi_con_so_khong_danh_tinh(self) -> None:
        """Cùng luật với mẫu tin: không tên, không SĐT ra Telegram."""
        ma = inspect.getsource(bot._con_so_hom_nay)
        assert "full_name" not in ma and "phone" not in ma
        assert "clinic_id = $1::uuid" in ma, "đếm phải tự khoá phòng khám"

    def test_kham_suc_khoe_dung_endpoint_noi_bo(self) -> None:
        """Cùng nguồn Uptime Kuma theo dõi — hai bên không kể hai chuyện."""
        assert bot._HEALTH["API + database"].endswith("/health/db")
        assert "dashboard:3000/health" in bot._HEALTH["Dashboard"]

    def test_kham_suc_khoe_cung_luat_voi_kuma(self) -> None:
        """Dashboard /health trả 307 → 200. Kuma đi theo chuyển hướng; bot
        không đi theo thì hai người gác kể hai chuyện về cùng một endpoint
        (đo 15/08: Kuma Up, bot ❌). Cùng luật: follow redirect + nhận 2xx."""
        ma = inspect.getsource(bot._kham_suc_khoe)
        assert "follow_redirects=True" in ma
        assert "r.is_success" in ma
