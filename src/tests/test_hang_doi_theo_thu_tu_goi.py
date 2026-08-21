"""Hàng đợi của quầy xếp theo LUẬT GỌI SỐ, không theo "ai chờ lâu nhất".

Kiểm toán 19/08/2026 tìm ra: màn Lễ tân tự xếp ở trình duyệt theo số phút chờ,
trong khi bảng tivi và ``/api/v1/queue`` xếp theo luật thật của phòng khám. Hai
bảng nói hai thứ tự khác nhau và người ngồi chờ nhìn thấy ngay — quầy gọi tên
một người trong khi bảng đang để người khác ở đầu hàng.

Bài dưới chạy qua CHÍNH ``WorkItemService.list_worklist`` với connection giả,
nên nó canh HÀNH VI: dữ liệu vào là ba người có hoàn cảnh khác nhau, kết quả ra
phải đúng thứ tự mà ``queue_order`` quy định. Sửa cách gọi luật, đổi cầu nối,
hay lỡ tay xếp lại ở service — bài này đỏ.

VÌ SAO KHÔNG CANH BẰNG CHUỖI KÝ TỰ: một bài kiểm chỉ soi "có gọi
thu_tu_goi_theo_ngay không" vẫn xanh khi người ta gọi đúng hàm rồi vứt kết quả
đi. Ở đây kiểm con số thứ tự thật.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any, cast

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.work_item_service import WorkItemService

_NGAY = date(2026, 8, 20)
#: 18:00 giờ Việt Nam = 11:00 UTC. Khung 15 phút ⇒ đúng giờ tới 18:15.
_HEN = datetime(2026, 8, 20, 11, 0, tzinfo=timezone.utc)


def _identity() -> StaffIdentity:
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


def _hang(
    *,
    ma: str,
    ten: str,
    ve: str | None,
    den_luc: datetime | None,
    kenh: str = "ONLINE",
    hen: datetime | None = None,
) -> dict[str, Any]:
    """Một hàng SQL đúng hình dạng mà truy vấn hàng đợi trả về."""
    return {
        "id": f"w-{ma}",
        "node_code": "LUOTKHAM-02",
        "node_name": "Xác minh người bệnh",
        "workspace": "bang_dieu_phoi",
        "status": "PENDING",
        "priority": 5,
        "version": 1,
        "visit_id": f"v-{ma}",
        "appointment_id": ma,
        "assigned_to": None,
        "assigned_role": "RECEPTION",
        "actor_roles": ["RECEPTION"],
        "actionable_by_me": True,
        "blocked": False,
        "due_at": None,
        "created_at": _HEN,
        "started_at": None,
        "clinic_patient_id": f"p-{ma}",
        "patient_code": f"BN-{ma}",
        "full_name": ten,
        "date_of_birth": None,
        "gender": "Nữ",
        "phone_primary": None,
        "queue_number": ve,
        "slot_start": hen or _HEN,
        "booking_channel": kenh,
        "is_priority_slot": False,
        "service_code": None,
        "service_name": None,
        "form_code": None,
        "checked_in_at": den_luc,
        "exam_started_at": None,
        "visit_status": "IN_PROGRESS" if den_luc else None,
        "doctor_id": None,
        "slot_minutes": 15,
    }


class _Pool:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    async def fetch(self, *_args: Any) -> list[dict[str, Any]]:
        return self._rows


def _xep(rows: list[dict[str, Any]]) -> list[tuple[str, Any, Any]]:
    ket = asyncio.run(
        WorkItemService(_Pool(rows)).list_worklist(
            workspace="bang_dieu_phoi", identity=_identity(), day=_NGAY
        )
    )
    out: list[tuple[str, Any, Any]] = []
    for r in ket:
        # `list_worklist` khai kiểu trả về là dict[str, Any] nên "patient" ra
        # `object`; gán qua biến có kiểu để mypy đọc được, thay vì rắc
        # `type: ignore` — chú thích bỏ qua kiểu là chỗ bug thật hay nấp.
        benh_nhan = cast(dict[str, Any], r["patient"])
        out.append((benh_nhan["full_name"], r["call_order"], r["call_reason"]))
    return out


def test_den_dung_khung_duoc_goi_truoc_nguoi_vang_lai_toi_som_hon() -> None:
    """Đúng tình huống sinh cãi vã ở quầy.

    Chị Vãng Lai bước vào lúc 17:30 — SỚM HƠN. Chị Đúng Hẹn có lịch 18:00 và
    check-in lúc 18:05, tức vẫn trong khung 15 phút của mình. Luật của phòng
    khám cho người có hẹn đi trước; bản cũ xếp theo "chờ lâu nhất" thì làm
    ngược lại.
    """
    ra = _xep(
        [
            _hang(
                ma="a-vanglai",
                ten="Vãng Lai",
                ve="002",
                den_luc=_HEN - timedelta(minutes=30),
                kenh="WALK_IN",
            ),
            _hang(
                ma="b-dunghen",
                ten="Đúng Hẹn",
                ve="001",
                den_luc=_HEN + timedelta(minutes=5),
            ),
        ]
    )
    theo_thu_tu = [t for t, _, _ in sorted(ra, key=lambda x: x[1])]
    assert theo_thu_tu[0] == "Đúng Hẹn", (
        "người có hẹn đến trong khung phải được gọi trước khách vãng lai, "
        f"kết quả: {ra}"
    )
    ly_do = {t: r for t, _, r in ra}
    assert ly_do["Đúng Hẹn"] == "DAT_TRUOC_DUNG_GIO"
    assert ly_do["Vãng Lai"] == "DEN_TRUC_TIEP"


def test_den_muon_khoi_khung_thi_tut_xuong_lan_sau() -> None:
    """Khung 15 phút: check-in lúc 18:20 là đã muộn."""
    ra = _xep(
        [
            _hang(
                ma="a-muon",
                ten="Đến Muộn",
                ve="001",
                den_luc=_HEN + timedelta(minutes=20),
            ),
            _hang(
                ma="b-dunggio",
                ten="Đúng Giờ",
                ve="002",
                den_luc=_HEN + timedelta(minutes=2),
            ),
        ]
    )
    ly_do = {t: r for t, _, r in ra}
    assert ly_do["Đến Muộn"] == "DEN_TRE"
    assert ly_do["Đúng Giờ"] == "DAT_TRUOC_DUNG_GIO"
    thu = {t: o for t, o, _ in ra}
    assert thu["Đúng Giờ"] < thu["Đến Muộn"]


def test_ve_uu_tien_di_truoc_tat_ca() -> None:
    ra = _xep(
        [
            _hang(
                ma="a-thuong",
                ten="Thường",
                ve="001",
                den_luc=_HEN + timedelta(minutes=1),
            ),
            _hang(
                ma="b-uutien",
                ten="Ưu Tiên",
                ve="ƯT01",
                den_luc=_HEN + timedelta(minutes=9),
            ),
        ]
    )
    thu = {t: o for t, o, _ in ra}
    assert thu["Ưu Tiên"] < thu["Thường"]
    assert dict((t, r) for t, _, r in ra)["Ưu Tiên"] == "UU_TIEN"


def test_chua_check_in_van_co_mat_trong_danh_sach() -> None:
    """Chưa đến thì vẫn phải hiện — quầy cần biết ai chưa tới.

    ⚠️ GHI LẠI MỘT ĐIỂM ĐÁNG NGỜ, KHÔNG PHẢI LỖI CỦA BẢN VÁ NÀY.
    ``REASON_CHUA_DEN`` chỉ được gán khi lịch VỪA chưa check-in VỪA không ghi
    kênh đặt (`queue_order._classify`). Khách đặt online mà chưa tới thì rơi
    xuống nhánh cuối và bị dán ``DEN_TRE`` — "đặt trước nhưng đến muộn" — kể cả
    khi CHƯA tới giờ hẹn.

    Ở màn hàng đợi Lễ tân điều này không lộ ra, vì việc chỉ sinh ra SAU khi
    check-in nên mọi dòng đều đã có giờ đến. Nhưng các bảng đọc từ `appointment`
    (bảng tivi, lưới tuần) thì có hiển thị người chưa tới. Bài kiểm này khoá
    hành vi HIỆN TẠI để nếu ai sửa luật ấy thì phải sửa có ý thức."""
    ra = _xep([_hang(ma="a", ten="Chưa Tới", ve="001", den_luc=None)])
    assert ra[0][0] == "Chưa Tới", "người chưa tới vẫn phải nằm trong danh sách"
    assert ra[0][2] == "DEN_TRE", (
        "hành vi hiện tại — xem ghi chú ở đầu hàm trước khi đổi"
    )

    # Còn khi KHÔNG ghi kênh đặt thì mới là 'chưa đến' thật.
    khong_kenh = _hang(ma="b", ten="Không Kênh", ve="002", den_luc=None)
    khong_kenh["booking_channel"] = None
    assert _xep([khong_kenh])[0][2] == "CHUA_DEN"


def test_dong_khong_gan_lich_hen_khong_co_thu_hang() -> None:
    """Không có lịch hẹn ⇒ không có khung giờ để so ⇒ không xếp được.

    Trả `None` chứ KHÔNG trả 0: số 0 nghĩa là "người được gọi tiếp theo", và
    đẩy một dòng thiếu dữ liệu lên đầu hàng là cách tệ nhất để xử lý dữ liệu
    thiếu. Màn hình đọc `None` rồi cho nó xuống cuối.
    """
    mo_coi = _hang(ma="x", ten="Không Lịch", ve=None, den_luc=None)
    mo_coi["appointment_id"] = None
    ra = _xep([mo_coi])
    assert ra[0][1] is None, "dòng không gắn lịch hẹn phải có call_order = None"
    assert ra[0][2] is None


def test_moi_khoa_service_tra_ve_deu_co_trong_dto_cua_api() -> None:
    """`response_model` LỌC BỎ mọi khoá không khai báo, và lọc IM LẶNG.

    Đây là bài kiểm sinh ra từ một lần vấp thật (20/08/2026): service trả đủ
    `call_order`/`call_tier`/`call_reason`, câu SQL đúng, mọi bài kiểm xanh —
    mà API vẫn không có khoá nào, vì `WorklistItem` chưa khai chúng. Chỉ phép đo
    trên dữ liệu THẬT ở staging mới lộ ra. Chú thích trong chính
    `work_items.py` đã cảnh báo ("đã mất một lượt deploy vì chuyện này") nhưng
    không có gì canh — nên nó lặp lại.

    Bài này canh CẢ HỌ lỗi ấy, không riêng ba khoá lần này: bất kỳ ai thêm một
    khoá vào service mà quên khai trong DTO đều bị chặn ngay tại CI.
    """
    from clinicai.api.v1.routers.work_items import WorklistItem

    ket = asyncio.run(
        WorkItemService(
            _Pool([_hang(ma="a", ten="Ai Đó", ve="001", den_luc=_HEN)])
        ).list_worklist(workspace="bang_dieu_phoi", identity=_identity(), day=_NGAY)
    )
    khoa_service = set(ket[0].keys())
    khoa_dto = set(WorklistItem.model_fields.keys())
    thieu = khoa_service - khoa_dto
    assert not thieu, (
        f"Service trả các khoá này nhưng DTO chưa khai nên API sẽ NUỐT chúng: "
        f"{sorted(thieu)}"
    )
