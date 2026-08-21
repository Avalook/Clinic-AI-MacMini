"""Những gì còn vướng khi Lễ tân muốn đóng lượt khám.

``build_blockers`` là hàm THUẦN và là chỗ quyết định quầy có được đóng lượt hay
không — nên mọi tổ hợp phải thử được mà không cần một lượt khám thật. Chính
docstring của nó nói vậy; các bài dưới đây là phần thực hiện lời hứa đó.

Vì sao đáng canh: mỗi vướng mắc bỏ sót là một người bệnh ra về khi phòng khám
còn nợ họ một việc (kết quả chưa về, dịch vụ chưa làm) — hoặc ngược lại, một
vướng mắc BỊA ra là một hàng người kẹt ở quầy không ai đóng lượt được.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.checkout_service import (
    CLOSE_NODE,
    CheckoutService,
    build_blockers,
)

_LUC = datetime(2026, 8, 20, 11, 0, tzinfo=timezone.utc)


def _loai(row: dict[str, Any]) -> list[str]:
    return [b["type"] for b in build_blockers(row)]


def _sach() -> dict[str, Any]:
    """Một lượt KHÔNG còn vướng gì: đã thu tiền khám, không đơn thuốc, đã rời phòng."""
    return {
        "svc_open": 0,
        "lab_pending": 0,
        "paid_service": True,
        "has_drug": False,
        "paid_drug": False,
        "current_node_code": CLOSE_NODE,
        "room_name": None,
    }


def test_luot_sach_thi_khong_vuong_gi() -> None:
    assert build_blockers(_sach()) == []


def test_dich_vu_chua_xong_va_ket_qua_chua_ve_deu_chan() -> None:
    row = _sach() | {"svc_open": 2, "lab_pending": 1}
    ket = build_blockers(row)
    assert [b["type"] for b in ket] == ["service_open", "lab_pending"]
    # Câu chữ phải nói VIỆC PHẢI LÀM kèm CON SỐ, không nói tên bảng.
    assert "2 dịch vụ" in ket[0]["message"]
    assert "1 kết quả" in ket[1]["message"]
    assert "service_log" not in ket[0]["message"]


def test_chua_thu_tien_kham_thi_chan() -> None:
    assert "unpaid_service" in _loai(_sach() | {"paid_service": False})


def test_chi_doi_thu_tien_thuoc_khi_co_don() -> None:
    """Đòi ở mọi lượt sẽ chặn phần lớn bệnh nhân — những người không kê thuốc."""
    khong_don = _sach() | {"has_drug": False, "paid_drug": False}
    assert "unpaid_drug" not in _loai(khong_don)

    co_don_chua_thu = _sach() | {"has_drug": True, "paid_drug": False}
    assert "unpaid_drug" in _loai(co_don_chua_thu)

    co_don_da_thu = _sach() | {"has_drug": True, "paid_drug": True}
    assert "unpaid_drug" not in _loai(co_don_da_thu)


def test_van_dang_o_mot_phong_thi_chan() -> None:
    row = _sach() | {"current_node_code": "LUOTKHAM-05", "room_name": "Phòng khám 2"}
    ket = build_blockers(row)
    assert [b["type"] for b in ket] == ["still_at_station"]
    assert "Phòng khám 2" in ket[0]["message"]


def test_dang_o_chinh_buoc_dong_luot_thi_khong_tinh_la_vuong() -> None:
    """Bước đóng lượt không phải "đang xử lý" — nếu không thì không ai đóng nổi."""
    row = _sach() | {"current_node_code": CLOSE_NODE, "room_name": "Quầy tiếp nhận"}
    assert _loai(row) == []


def test_co_node_nhung_khong_biet_ten_phong_thi_khong_bia_ra_vuong_mac() -> None:
    """Thiếu dữ liệu KHÔNG được biến thành một vướng mắc.

    Câu "Bệnh nhân vẫn đang ở None" vừa vô nghĩa vừa chặn quầy đóng lượt.
    """
    row = _sach() | {"current_node_code": "LUOTKHAM-05", "room_name": None}
    assert _loai(row) == []


def test_nhieu_vuong_mac_thi_liet_ke_du_khong_dung_o_cai_dau_tien() -> None:
    """Liệt kê hết trong một lượt.

    Trả về cái vướng đầu tiên rồi dừng là bắt quầy đóng lượt nhiều lần, mỗi lần
    khám phá thêm một lý do mới — kiểu giao diện làm người dùng mất niềm tin
    nhanh nhất.
    """
    row = {
        "svc_open": 1,
        "lab_pending": 2,
        "paid_service": False,
        "has_drug": True,
        "paid_drug": False,
        "current_node_code": "LUOTKHAM-05",
        "room_name": "Phòng siêu âm",
    }
    assert _loai(row) == [
        "service_open",
        "lab_pending",
        "unpaid_service",
        "unpaid_drug",
        "still_at_station",
    ]


def test_du_lieu_thieu_khong_bi_doc_thanh_da_thu_tien() -> None:
    """Dòng không có khoá `paid_service` phải bị coi là CHƯA thu.

    Hai kiểu đoán sai không ngang giá nhau: đoán nhầm "đã thu" thì người bệnh ra
    về mà phòng khám mất tiền; đoán nhầm "chưa thu" thì quầy kiểm lại một lần.
    """
    assert "unpaid_service" in _loai({})


# ── Hai danh sách của màn Check-out ────────────────────────────────────────
#
# `pending_list` (hôm nay) và `stale_list` (tồn từ hôm trước) dùng CHUNG một câu
# SQL, chỉ thay mệnh đề WHERE. Bài dưới khoá HỢP ĐỒNG của chúng với giao diện:
# tên khoá, kiểu giờ (chuỗi ISO chứ không phải đối tượng datetime), và cách suy
# ra `can_close`. Đổi hình dạng mà quên sửa màn thì màn hiện ô trống — không lỗi
# nào bật ra.


def _identity_le_tan() -> StaffIdentity:
    return StaffIdentity(
        staff_id="s-le-tan",
        auth_user_id="u1",
        full_name="Lễ tân A",
        department="Tiếp đón",
        role=ClinicRole.RECEPTION,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


def _hang_luot(**ghi_de: Any) -> dict[str, Any]:
    nen: dict[str, Any] = {
        "visit_id": "v1",
        "patient_name": "Nguyễn Thử",
        "patient_code": "BN-2026-000001",
        "room_name": None,
        "already_closed": False,
        "checked_in_at": _LUC,
        "svc_open": 0,
        "lab_pending": 0,
        "paid_service": True,
        "has_drug": False,
        "paid_drug": False,
        "current_node_code": CLOSE_NODE,
        # `readiness` đọc thêm mấy cột mà `pending_list` không dùng — giữ đủ ở
        # đây để một hàm giả phục vụ được cả hai đường.
        "room_code": None,
        "visit_status": "IN_PROGRESS",
    }
    nen.update(ghi_de)
    return nen


class _ConnDs:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.sql: str = ""

    async def fetch(self, sql: str, *_args: Any) -> list[dict[str, Any]]:
        self.sql = sql
        return self._rows


class _AcquireDs:
    def __init__(self, conn: _ConnDs) -> None:
        self._conn = conn

    async def __aenter__(self) -> _ConnDs:
        return self._conn

    async def __aexit__(self, *_: object) -> bool:
        return False


class _PoolDs:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.conn = _ConnDs(rows)

    def acquire(self) -> _AcquireDs:
        return _AcquireDs(self.conn)


def test_pending_list_suy_ra_can_close_va_tra_gio_dang_chuoi() -> None:
    pool = _PoolDs([_hang_luot(), _hang_luot(visit_id="v2", svc_open=1)])
    ra = asyncio.run(CheckoutService(pool).pending_list(identity=_identity_le_tan()))
    assert [r["visit_id"] for r in ra] == ["v1", "v2"]
    # Lượt sạch thì đóng được; lượt còn dịch vụ dở thì không.
    assert ra[0]["can_close"] is True
    assert ra[1]["can_close"] is False
    assert ra[1]["blockers"][0]["type"] == "service_open"
    # Giờ phải là CHUỖI ISO — giao diện đọc thẳng, không tự đổi kiểu.
    assert isinstance(ra[0]["checked_in_at"], str)
    assert ra[0]["checked_in_at"].startswith("2026-08-20")


def test_luot_da_dong_thi_khong_the_dong_lai() -> None:
    pool = _PoolDs([_hang_luot(already_closed=True)])
    ra = asyncio.run(CheckoutService(pool).pending_list(identity=_identity_le_tan()))
    assert ra[0]["can_close"] is False, "đã đóng thì nút phải tắt"


def test_stale_list_chi_lay_luot_con_mo_tu_nhung_ngay_truoc() -> None:
    """Mỗi dòng ở đây là một người thật không ai chịu trách nhiệm."""
    pool = _PoolDs([_hang_luot(visit_id="cu1", checked_in_at=None)])
    svc = CheckoutService(pool)
    ra = asyncio.run(svc.stale_list(identity=_identity_le_tan()))

    assert ra[0]["visit_id"] == "cu1"
    # Lượt KHÔNG CÓ giờ check-in cũng phải vào danh sách — một lượt không biết
    # bắt đầu lúc nào thì lại càng cần người xem lại.
    assert ra[0]["checked_in_at"] is None
    # Và câu SQL phải giới hạn đúng phạm vi: còn mở, và trước hôm nay.
    assert "v.status IN ('OPEN', 'IN_PROGRESS')" in pool.conn.sql
    assert "v.checked_in_at < $3" in pool.conn.sql


# ── Toàn cảnh một lượt trước khi đóng ──────────────────────────────────────


class _ConnChiTiet:
    """Định tuyến theo nội dung SQL: một `fetchrow` + ba `fetch` khác nhau."""

    def __init__(self, *, chung: dict[str, Any] | None) -> None:
        self._chung = chung

    async def fetchrow(self, *_args: Any) -> dict[str, Any] | None:
        return self._chung

    async def fetch(self, sql: str, *_args: Any) -> list[dict[str, Any]]:
        if "work_item_event" in sql:
            return [
                {
                    "occurred_at": _LUC,
                    "ten_buoc": "Xác minh người bệnh",
                    "command": "complete",
                    "to_status": "COMPLETED",
                    "nguoi_lam": "Lễ tân A",
                }
            ]
        if "follow_up_case" in sql:
            return []
        if "payment" in sql:
            return [
                {
                    "id": "pm1",
                    "kind": "SERVICE",
                    "amount": 200000,
                    "status": "PAID",
                    "da_huy": False,
                    "paid_at": _LUC,
                }
            ]
        return [
            {
                "ten_buoc": "Xác minh người bệnh",
                "nguoi_lam": "Lễ tân A",
                "vai": "RECEPTION",
                "status": "COMPLETED",
                "finished_at": _LUC,
            }
        ]


class _PoolChiTiet:
    def __init__(self, *, chung: dict[str, Any] | None) -> None:
        self._conn = _ConnChiTiet(chung=chung)

    def acquire(self) -> Any:
        conn = self._conn

        class _A:
            async def __aenter__(self) -> _ConnChiTiet:
                return conn

            async def __aexit__(self, *_: object) -> bool:
                return False

        return _A()


def test_chi_tiet_luot_khong_ton_tai_tra_ok_false_chu_khong_no() -> None:
    """Không tìm thấy là một CÂU TRẢ LỜI, không phải một ngoại lệ.

    Màn Check-out gọi hàm này mỗi lần người dùng bấm sang lượt khác; ném lỗi ở
    đây là biến một cú bấm nhầm thành một trang lỗi.
    """
    ra = asyncio.run(
        CheckoutService(_PoolChiTiet(chung=None)).chi_tiet(
            identity=_identity_le_tan(), visit_id="khong-co"
        )
    )
    assert ra == {"ok": False, "visit_id": "khong-co"}


def test_chi_tiet_gom_du_bon_muc_va_muc_ho_so_noi_ro_la_chua_co() -> None:
    """Mục ③ rỗng CÓ CHỦ Ý — và phải nói ra vì sao.

    Hệ chưa sinh tệp PDF nào và chưa có kho lưu. Vẽ bốn dòng "Sẵn sàng" không
    dựa trên gì là hứa với người bệnh một thứ phòng khám không đưa được.
    """
    ra = asyncio.run(
        CheckoutService(
            _PoolChiTiet(chung=_hang_luot(visit_status="IN_PROGRESS"))
        ).chi_tiet(identity=_identity_le_tan(), visit_id="v1")
    )
    assert ra["ok"] is True
    assert ra["can_close"] is True
    assert ra["dich_vu"][0]["ten"] == "Xác minh người bệnh"
    assert ra["tai_chinh"][0]["status"] == "PAID"
    assert ra["theo_doi"] == []
    # Mục hồ sơ trả bệnh nhân: rỗng, nhưng KÈM lý do.
    assert ra["ho_so_tra"]["muc"] == []
    assert ra["ho_so_tra"]["vi_sao_rong"], "mục rỗng phải nói vì sao nó rỗng"
    # Dòng thời gian là MỐC THẬT do người thật bấm, không phải giờ suy ra.
    assert ra["moc_thoi_gian"][0]["lenh"] == "complete"
    assert ra["moc_thoi_gian"][0]["nguoi_lam"] == "Lễ tân A"


def test_readiness_luot_khong_ton_tai_thi_bao_loi_bang_tieng_nguoi() -> None:
    """Khác `chi_tiet`: `readiness` là cổng của hành động ĐÓNG LƯỢT.

    Ở đây không thấy lượt nghĩa là ai đó đang cố đóng một thứ không thuộc phòng
    khám mình — phải chặn, và chặn kèm câu đọc được.
    """
    with pytest.raises(ValidationError) as loi:
        asyncio.run(
            CheckoutService(_PoolChiTiet(chung=None)).readiness(
                identity=_identity_le_tan(), visit_id="khong-co"
            )
        )
    assert "phòng khám" in str(loi.value)


def test_readiness_tra_du_thong_tin_de_ve_nut_dong() -> None:
    ra = asyncio.run(
        CheckoutService(
            _PoolChiTiet(
                chung=_hang_luot(
                    room_name="Phòng khám 1", current_node_code="LUOTKHAM-05"
                )
            )
        ).readiness(identity=_identity_le_tan(), visit_id="v1")
    )
    assert ra["can_close"] is False
    assert ra["blockers"][0]["type"] == "still_at_station"
