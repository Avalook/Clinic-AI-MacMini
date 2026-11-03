"""Công cụ của trợ lý — CHỈ ĐỌC, và chỉ đọc dữ liệu CÔNG KHAI của phòng khám
(giá, giờ, cơ sở, khung giờ còn chỗ). Không bảng nào chứa thông tin khách: tin
gửi lên model không kéo theo hồ sơ của ai (NĐ 13/2023 — cùng lằn ranh với
`agent_tom_tat.py`).

Phòng khám và cơ sở do SERVER khoá lúc dựng bộ công cụ, không phải tham số
model điền: model chọn được `clinic_id` là model đọc được phòng khám khác.

Mọi lỗi trả về `{"loi": "…"}` cho model đọc, không ném — một công cụ hỏng không
được làm sập cả lượt trả lời.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any, Protocol

import asyncpg
import structlog

from clinicai.core.clock import now_vn
from clinicai.ports.mo_hinh import CongCu
from clinicai.services.capacity_service import CapacityService
from clinicai.services.tro_ly_khach.luat_chan import bo_dau

logger = structlog.get_logger()

CHUYEN_NGUOI = "chuyen_nguoi"
SO_NGAY_XEM_TRUOC = 60
#: Số dịch vụ trả một lần — đủ cho câu hỏi cụ thể; hỏi rộng thì `con_nua` > 0
#: và lời nhắc bảo model tra lại cụ thể hơn.
TOI_DA_GIA = 15
_THU_DOW = ("Chủ nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy")

DANH_SACH: tuple[CongCu, ...] = (
    CongCu(
        ten="tra_gia_dich_vu",
        mo_ta="Tra giá niêm yết dịch vụ theo từ khoá — dùng ĐÚNG cụm khách nói "
        "(vd 'siêu âm đầu dò', 'xét nghiệm HPV'). Giá đã gồm thuế. `chua_co_gia` = "
        "phòng khám có làm nhưng chưa niêm yết giá. `con_nua` > 0 = còn kết quả, "
        "tra cụ thể hơn.",
        tham_so={
            "type": "object",
            "properties": {"tu_khoa": {"type": "string"}},
            "required": [],
        },
    ),
    CongCu(
        ten="thong_tin_phong_kham",
        mo_ta="Giờ mở cửa từng ngày trong tuần, địa chỉ và số điện thoại các cơ sở.",
        tham_so={"type": "object", "properties": {}, "required": []},
    ),
    CongCu(
        ten="lich_trong",
        mo_ta="Các khung giờ còn nhận lịch hẹn trong một ngày, dạng YYYY-MM-DD. "
        "Chỉ để tham khảo, nhân viên xác nhận lại.",
        tham_so={
            "type": "object",
            "properties": {"ngay": {"type": "string", "description": "YYYY-MM-DD"}},
            "required": ["ngay"],
        },
    ),
    CongCu(
        ten=CHUYEN_NGUOI,
        mo_ta="Chuyển cuộc trò chuyện cho nhân viên thật. Gọi khi: câu hỏi y khoa, "
        "khách chốt đặt/đổi/huỷ lịch, than phiền, hoặc không chắc câu trả lời.",
        tham_so={
            "type": "object",
            "properties": {
                "ly_do": {"type": "string"},
                "ghi_chu": {"type": "string", "description": "vd ngày giờ khách chọn"},
            },
            "required": ["ly_do"],
        },
    ),
)


class BoCongCu(Protocol):
    def danh_sach(self) -> tuple[CongCu, ...]: ...

    async def chay(self, ten: str, tham_so: dict[str, Any]) -> dict[str, Any]: ...


def doc_ngay(s: Any) -> date | None:
    """Ngày do MODEL điền — rác thì None, không ném (luật backend)."""
    if not isinstance(s, str):
        return None
    try:
        return date.fromisoformat(s.strip()[:10])
    except ValueError:
        return None


def _tu(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", bo_dau(s))


def ket_qua_gia(
    dong: list[dict[str, Any]], tu_khoa: str, toi_da: int = TOI_DA_GIA
) -> dict[str, Any]:
    """Kết quả tra giá cho model. `dong`: {"ten", "gia_vnd", "gia_tam"};
    `gia_vnd` rỗng / 0 = có trong bảng giá nhưng CHƯA có giá.

    Khớp theo TỪ (bỏ dấu), không theo chuỗi con: "am" của "siêu âm" không được
    dính "tâm", "nam". Có tên chứa ĐỦ mọi từ thì chỉ trả những tên đó (tên ngắn
    trước — ít chữ thừa nhất là gần nhất). Không có thì trả MỌI tên khớp ít nhất
    một từ, nhiều từ khớp trước, kèm `khop_mot_phan` — KHÔNG chấm điểm để chọn hộ:
    trên bảng giá staging 30/10, "xét nghiệm HPV" theo số từ khớp ra "Xét nghiệm
    máu", theo độ hiếm cũng vậy ("xét" có 2 tên, "hpv" 3). Đưa cả hai nhóm để
    model chọn hoặc hỏi lại khách.

    Dịch vụ chưa có giá đi vào `chua_co_gia` chứ không bị coi là "không có":
    staging 30/10 — HPV ba dịch vụ đều 0đ, công cụ cũ báo "không thấy", khách sẽ
    hiểu là phòng khám không làm HPV.
    """
    tu = set(_tu(tu_khoa))
    so_khop = [len(tu & set(_tu(str(d["ten"])))) for d in dong]
    if tu and max(so_khop, default=0) == 0:
        return {
            "khong_thay": True,
            "mot_so_dich_vu": [d["ten"] for d in dong if d.get("gia_vnd")][:15],
        }
    cap = [(n, d) for n, d in zip(so_khop, dong) if not tu or n == len(tu)]
    mot_phan = not cap
    if mot_phan:
        cap = [(n, d) for n, d in zip(so_khop, dong) if n > 0]
    cap.sort(key=lambda nd: (-nd[0], len(_tu(str(nd[1]["ten"]))), str(nd[1]["ten"])))
    khop = [d for _, d in cap]
    co_gia = [d for d in khop if d.get("gia_vnd")]
    chua = [str(d["ten"]) for d in khop if not d.get("gia_vnd")]
    ra: dict[str, Any] = {
        "dich_vu": [
            {
                "ten": d["ten"],
                "gia_vnd": d["gia_vnd"],
                "gia_tam": d.get("gia_tam", False),
            }
            for d in co_gia[:toi_da]
        ],
        "con_nua": max(len(co_gia) - toi_da, 0),
    }
    if chua:
        ra["chua_co_gia"] = chua[:toi_da]
    if mot_phan:
        ra["khop_mot_phan"] = True
    return ra


def kiem_ngay_xem(ngay: Any, luc: datetime) -> date | dict[str, Any]:
    d = doc_ngay(ngay)
    if d is None:
        return {"loi": "Ngày không hợp lệ, cần dạng YYYY-MM-DD."}
    if d < luc.date():
        return {"loi": "Ngày này đã qua."}
    if d > luc.date() + timedelta(days=SO_NGAY_XEM_TRUOC):
        return {"loi": f"Chỉ xem được trong {SO_NGAY_XEM_TRUOC} ngày tới."}
    return d


def khung_con_cho(quote: dict[str, Any], d: date, luc: datetime) -> dict[str, Any]:
    """Rút gọn kết quả `CapacityService.quote` cho model.

    Tuần chưa công bố lịch trực thì trần KHÔNG chặn (`regular_chan=False`) — khi
    đó mọi khung trong giờ mở cửa đều nhận lịch, đừng báo "hết chỗ" vì đã đầy
    trần. Hôm nay thì bỏ khung đã kết thúc (`quote` không tự loại).
    """
    if quote.get("closed") or not quote.get("slots"):
        return {"ngay": d.isoformat(), "dong_cua": True, "khung_con_cho": []}
    chan = bool(quote.get("regular_chan", True))
    phut = luc.hour * 60 + luc.minute if d == luc.date() else -1
    gio = [
        str(s["time"])
        for s in quote["slots"]
        if int(s["minute_of_day"]) + int(s.get("slot_minutes") or 0) > phut
        and (not chan or int(s.get("con_lai") or 0) > 0)
    ]
    return {
        "ngay": d.isoformat(),
        "thu": _THU_DOW[(d.weekday() + 1) % 7],
        "dong_cua": False,
        "khung_con_cho": gio,
        "ghi_chu": "Tham khảo; nhân viên xác nhận lại khi đặt.",
    }


class CongCuPhongKham:
    """Bộ công cụ đọc DB thật, khoá vào một phòng khám + một cơ sở."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        clinic_id: str,
        location_id: str | None,
        dong_ho: Callable[[], datetime] = now_vn,
    ) -> None:
        self._pool = pool
        self._clinic_id = clinic_id
        self._location_id = location_id
        self._dong_ho = dong_ho

    def danh_sach(self) -> tuple[CongCu, ...]:
        return DANH_SACH

    async def chay(self, ten: str, tham_so: dict[str, Any]) -> dict[str, Any]:
        try:
            if ten == "tra_gia_dich_vu":
                return await self._gia(str(tham_so.get("tu_khoa") or ""))
            if ten == "thong_tin_phong_kham":
                return await self._thong_tin()
            if ten == "lich_trong":
                return await self._lich_trong(tham_so.get("ngay"))
        except Exception as e:  # noqa: BLE001
            logger.exception("tro_ly_cong_cu_hong", cong_cu=ten)
            return {"loi": f"Công cụ lỗi ({type(e).__name__}), hãy chuyen_nguoi."}
        return {"loi": f"Không có công cụ {ten!r}."}

    async def _gia(self, tu_khoa: str) -> dict[str, Any]:
        rows = await self._pool.fetch(
            """
            SELECT name, unit_price, coalesce(gia_tam, false) AS gia_tam
              FROM public.service_price
             WHERE clinic_id = $1::uuid AND "group" = 'dich_vu' AND active
             ORDER BY name
            """,
            self._clinic_id,
        )
        dong = [
            {
                "ten": r["name"],
                "gia_vnd": int(r["unit_price"]) if r["unit_price"] else None,
                "gia_tam": r["gia_tam"],
            }
            for r in rows
        ]
        return ket_qua_gia(dong, tu_khoa)

    async def _thong_tin(self) -> dict[str, Any]:
        co_so = await self._pool.fetch(
            """
            SELECT name, address, phone FROM public.clinic_location
             WHERE clinic_id = $1::uuid AND is_active ORDER BY name
            """,
            self._clinic_id,
        )
        gio = await self._pool.fetch(
            """
            SELECT key::int AS dow, value->>'open' AS mo, value->>'close' AS dong
              FROM public.clinic c, jsonb_each(c.settings->'hours')
             WHERE c.id = $1::uuid
            """,
            self._clinic_id,
        )
        theo_dow = {r["dow"]: (r["mo"], r["dong"]) for r in gio}
        lich = {}
        for dow in (1, 2, 3, 4, 5, 6, 0):
            mo, dong = theo_dow.get(dow, (None, None))
            lich[_THU_DOW[dow]] = (
                f"{mo}–{dong}" if mo and dong and mo != dong else "nghỉ"
            )
        return {
            "co_so": [
                {"ten": r["name"], "dia_chi": r["address"], "dien_thoai": r["phone"]}
                for r in co_so
            ],
            "gio_mo_cua": lich,
        }

    async def _lich_trong(self, ngay: Any) -> dict[str, Any]:
        luc = self._dong_ho()
        d = kiem_ngay_xem(ngay, luc)
        if isinstance(d, dict):
            return d
        q = await CapacityService(self._pool).quote(
            date=d.isoformat(),
            location_id=self._location_id,
            doctor_id=None,
            clinic_id=self._clinic_id,
        )
        return khung_con_cho(q, d, luc)


class CongCuMau:
    """Dữ liệu GIẢ cho bộ chấm chạy không cần DB. Số ở đây không phải giá thật —
    chỉ để đo model có gọi đúng công cụ và nói đúng theo kết quả hay không."""

    GIA = (
        {"ten": "Khám phụ khoa", "gia_vnd": 300000, "gia_tam": False},
        {"ten": "Siêu âm đầu dò", "gia_vnd": 350000, "gia_tam": False},
        {"ten": "Siêu âm tuyến vú", "gia_vnd": 300000, "gia_tam": False},
        {"ten": "Xét nghiệm Pap smear", "gia_vnd": 450000, "gia_tam": False},
        {"ten": "Xét nghiệm HPV", "gia_vnd": 650000, "gia_tam": False},
        {"ten": "Trị liệu sàn chậu Bio (1 buổi)", "gia_vnd": 600000, "gia_tam": False},
        {"ten": "Soi cổ tử cung", "gia_vnd": None, "gia_tam": False},
    )

    def __init__(self, dong_ho: Callable[[], datetime] = now_vn) -> None:
        self._dong_ho = dong_ho

    def danh_sach(self) -> tuple[CongCu, ...]:
        return DANH_SACH

    async def chay(self, ten: str, tham_so: dict[str, Any]) -> dict[str, Any]:
        if ten == "tra_gia_dich_vu":
            return ket_qua_gia(list(self.GIA), str(tham_so.get("tu_khoa") or ""))
        if ten == "thong_tin_phong_kham":
            return {
                "co_so": [
                    {
                        "ten": "Cơ sở mẫu",
                        "dia_chi": "(địa chỉ mẫu)",
                        "dien_thoai": "(mẫu)",
                    }
                ],
                "gio_mo_cua": {
                    **{t: "08:00–20:00" for t in _THU_DOW[1:6]},
                    "Thứ Bảy": "08:00–17:00",
                    "Chủ nhật": "nghỉ",
                },
            }
        if ten == "lich_trong":
            luc = self._dong_ho()
            d = kiem_ngay_xem(tham_so.get("ngay"), luc)
            if isinstance(d, dict):
                return d
            slots = [
                {
                    "time": f"{h:02d}:{m:02d}",
                    "minute_of_day": h * 60 + m,
                    "slot_minutes": 30,
                    "con_lai": 0 if h == 9 else 2,
                }
                for h in range(8, 20)
                for m in (0, 30)
            ]
            q = {"closed": d.weekday() == 6, "slots": slots, "regular_chan": True}
            return khung_con_cho(q, d, luc)
        return {"loi": f"Không có công cụ {ten!r}."}


def ket_qua_chu(kq: dict[str, Any]) -> str:
    return json.dumps(kq, ensure_ascii=False, default=str)


__all__ = [
    "CHUYEN_NGUOI",
    "DANH_SACH",
    "BoCongCu",
    "CongCuMau",
    "CongCuPhongKham",
    "doc_ngay",
    "ket_qua_chu",
    "khung_con_cho",
    "ket_qua_gia",
    "kiem_ngay_xem",
]
