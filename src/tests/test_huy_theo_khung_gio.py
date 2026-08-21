"""Gỡ ca huỷ theo KHUNG GIỜ, không theo ngày (Tuyền 17/08/2026).

"Xoá ca sáng để thêm cả ngày thì sao — về bản chất bác sĩ vẫn khám." Bản cũ
hỏi thô "còn ca nào trong ngày không" nên sai cả hai chiều: xoá SÁNG còn
CHIỀU thì lịch sáng sống sót mồ côi; xoá SÁNG rồi thêm CẢ NGÀY thì lịch
sáng bị huỷ oan. Các bài dưới chạy qua CHÍNH RosterService.remove với
connection giả — luật lọc theo hợp-các-ca-còn-lại là hành vi, không phải
chuỗi ký tự.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.config_service import RosterService


def _identity() -> StaffIdentity:
    return StaffIdentity(
        staff_id="s1",
        auth_user_id="u1",
        full_name="Quản lý A",
        department="Điều hành",
        role=ClinicRole.MANAGEMENT,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


class _GiaoDich:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_: object) -> bool:
        return False


_CA = {
    "staff_id": "bs000000-0000-4000-8000-000000000001",
    "work_date": date(2026, 8, 20),
    "station": "LICH_KHAM",
}

# Giờ mở cửa 07:00–20:00; hai lịch: 08:00 (sáng) và 15:00 (chiều).
_UNG_VIEN = [
    {"id": "sang8h", "phut": 8 * 60, "gio": "08:00"},
    {"id": "chieu15h", "phut": 15 * 60, "gio": "15:00"},
]


def _ca_con_lai(shift: str) -> dict[str, Any]:
    # `settings` đi cùng giờ mở cửa từ 21/08/2026: giờ của từng ca là cấu hình
    # của phòng khám, không còn là hằng số trong code. None ⇒ dùng mặc định
    # (sáng 08:00–13:00 · chiều 14:00–17:30 · tối 17:30–21:30).
    return {
        "shift": shift,
        "open_minute": 7 * 60,
        "close_minute": 20 * 60,
        "settings": None,
    }


class _Conn:
    """Định tuyến theo nội dung SQL — vòng gọi thay đổi theo dry_run/dữ liệu."""

    def __init__(
        self,
        *,
        con_lai: list[dict[str, Any]],
        ung_vien: list[dict[str, Any]] | None = None,
    ) -> None:
        self._con_lai = con_lai
        # Bài nào cần lịch ở giờ khác thì tự mang dữ liệu riêng. SỬA biến dùng
        # chung là cách làm hỏng ba bài kiểm khác mà không ai ngờ tới.
        self._ung_vien = ung_vien if ung_vien is not None else list(_UNG_VIEN)
        self.da_xoa_ca = False
        self.ids_huy: list[str] | None = None
        self.so_event = 0

    def transaction(self) -> _GiaoDich:
        return _GiaoDich()

    async def fetchrow(self, sql: str, *args: object) -> dict[str, Any]:
        assert "FROM work_roster" in sql
        return dict(_CA)

    async def fetch(self, sql: str, *args: object) -> list[dict[str, Any]]:
        if "clinic_hours_for_date" in sql:
            assert "coalesce(w.status, 'APPROVED') = 'APPROVED'" in sql, (
                "PENDING chưa phải ca trực — không được tính là phủ"
            )
            return self._con_lai
        assert "FROM public.appointment" in sql
        return list(self._ung_vien)

    async def execute(self, sql: str, *args: object) -> None:
        if "DELETE FROM work_roster" in sql:
            self.da_xoa_ca = True
        elif "UPDATE public.appointment" in sql:
            gia_tri = args[1]
            assert isinstance(gia_tri, list)
            self.ids_huy = [str(x) for x in gia_tri]
        elif "appointment.doctor_removed" in sql:
            self.so_event += 1


class _Pool:
    def __init__(self, conn: _Conn) -> None:
        self._conn = conn

    def acquire(self) -> "_Pool":
        return self

    async def __aenter__(self) -> _Conn:
        return self._conn

    async def __aexit__(self, *_: object) -> None:
        return None


def _go(conn: _Conn, *, dry_run: bool = False) -> dict[str, Any]:
    service = RosterService(_Pool(conn))
    return asyncio.run(
        service.remove(
            roster_id="ca000000-0000-4000-8000-000000000001",
            identity=_identity(),
            dry_run=dry_run,
        )
    )


class TestHuyTheoKhungGio:
    def test_xoa_sang_con_chieu_thi_chi_lich_sang_bi_huy(self) -> None:
        """Chiều bác sĩ vẫn ngồi bàn khám — lịch 15:00 phải ở yên."""
        conn = _Conn(con_lai=[_ca_con_lai("CHIEU")])
        ket = _go(conn)
        assert ket["so_lich_huy"] == 1 and ket["gio"] == ["08:00"]
        assert conn.ids_huy == ["sang8h"]
        assert conn.so_event == 1

    def test_them_ca_ngay_truoc_roi_xoa_sang_thi_khong_huy_gi(self) -> None:
        """Đường đổi ca an toàn: THÊM cả-ngày trước, xoá sáng sau — mọi giờ
        vẫn được phủ, không lịch nào chết oan."""
        conn = _Conn(con_lai=[_ca_con_lai("FULL")])
        ket = _go(conn)
        assert ket["so_lich_huy"] == 0
        assert conn.ids_huy is None and conn.so_event == 0

    def test_het_ca_thi_huy_ca_ngay_nhu_cu(self) -> None:
        conn = _Conn(con_lai=[])
        ket = _go(conn)
        assert ket["so_lich_huy"] == 2
        assert conn.ids_huy == ["sang8h", "chieu15h"]

    def test_dry_run_do_ma_khong_cat(self) -> None:
        """Hộp xác nhận cần con số TRƯỚC khi xoá — và đo thì không được để
        lại vết gì: không xoá ca, không huỷ lịch, không event."""
        conn = _Conn(con_lai=[_ca_con_lai("CHIEU")])
        ket = _go(conn, dry_run=True)
        assert ket == {"so_lich_huy": 1, "gio": ["08:00"]}
        assert conn.da_xoa_ca is False
        assert conn.ids_huy is None and conn.so_event == 0


class TestBaCa:
    """Ba ca (21/08/2026) — và luật "thêm trước, gỡ sau" phải sống qua đợt sửa.

    Tuyền nhắc lại nguyên văn luật này khi giao việc, nên nó được canh bằng
    đúng câu chuyện đã kể: *"bệnh nhân Hoa khám 8h sáng, bác sĩ Thành đang ca
    sáng, giờ muốn đổi thành cả ngày — phải thêm ca cả ngày TRƯỚC rồi mới xoá
    ca sáng thì lịch của Hoa mới không bị ảnh hưởng."*
    """

    def test_con_ca_toi_thi_chi_lich_toi_song(self) -> None:
        """Gỡ ca sáng, còn ca tối: lịch sáng và chiều chết, lịch tối sống."""
        conn = _Conn(
            con_lai=[_ca_con_lai("TOI")],
            ung_vien=[
                {"id": "sang8h", "phut": 8 * 60, "gio": "08:00"},
                {"id": "chieu15h", "phut": 15 * 60, "gio": "15:00"},
                {"id": "toi19h", "phut": 19 * 60, "gio": "19:00"},
            ],
        )
        ket = _go(conn)
        assert ket["so_lich_huy"] == 2
        assert conn.ids_huy == ["sang8h", "chieu15h"]

    def test_ca_ngay_phu_ca_ba_lich_ke_ca_buoi_toi(self) -> None:
        """FULL = hợp cả ba ca, nên lịch 19:00 cũng được phủ."""
        conn = _Conn(
            con_lai=[_ca_con_lai("FULL")],
            ung_vien=[
                {"id": "sang8h", "phut": 8 * 60, "gio": "08:00"},
                {"id": "toi19h", "phut": 19 * 60, "gio": "19:00"},
            ],
        )
        ket = _go(conn)
        assert ket["so_lich_huy"] == 0
        assert conn.ids_huy is None

    def test_chuyen_hoa_8h_tu_ca_sang_sang_ca_ngay_khong_mat_lich(self) -> None:
        """CÂU CHUYỆN CỦA TUYỀN, chạy qua chính hàm gỡ ca.

        Thứ tự đúng: thêm ca CẢ NGÀY trước → lúc gỡ ca sáng, hợp các ca còn lại
        đã phủ 08:00 → lịch của Hoa nguyên vẹn.
        """
        conn = _Conn(con_lai=[_ca_con_lai("FULL")])
        assert _go(conn)["so_lich_huy"] == 0

    def test_lam_nguoc_thu_tu_thi_hoa_mat_lich(self) -> None:
        """Và đây là vì sao thứ tự quan trọng — chiều ngược của bài trên.

        Gỡ ca sáng TRƯỚC khi thêm ca mới: khoảnh khắc ấy bác sĩ không còn ca
        nào phủ 08:00, và lịch 8 giờ của Hoa bị huỷ. Bài kiểm này tồn tại để
        không ai "sửa cho tiện" thành gỡ-trước-thêm-sau.
        """
        conn = _Conn(con_lai=[])
        ket = _go(conn)
        assert "08:00" in ket["gio"], "lịch của Hoa nằm trong danh sách bị huỷ"

    def test_nghi_trua_khong_thuoc_ca_nao_nen_lich_1330_bi_huy(self) -> None:
        """Lịch rơi vào giờ nghỉ trưa thì không ca nào cứu được nó.

        Không phải lỗi của bản vá này: một lịch 13:30 lẽ ra không đặt được từ
        đầu (Tuyền chốt 21/08: ngoài ba ca thì không đặt lịch). Bài kiểm ghi
        lại hành vi để nếu sau này phòng khám bỏ nghỉ trưa thì có chỗ đối
        chiếu — và để người đọc biết ca CẢ NGÀY cũng không phủ giờ nghỉ.
        """
        conn = _Conn(
            con_lai=[_ca_con_lai("FULL")],
            ung_vien=[{"id": "trua1330", "phut": 13 * 60 + 30, "gio": "13:30"}],
        )
        ket = _go(conn)
        assert ket["so_lich_huy"] == 1
        assert ket["gio"] == ["13:30"]
