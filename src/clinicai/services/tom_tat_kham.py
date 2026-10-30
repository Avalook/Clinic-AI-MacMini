"""PHIẾU TÓM TẮT BỆNH ÁN — N lần khám gần nhất của một khách, các lượt thành cột.

Thay phiếu phòng khám đang nhập tay trên Notion (Tuyền duyệt bản demo 30/10/2026):
bác sĩ cầm một tờ là thấy xu hướng huyết áp, cân nặng, tuổi thai, cận lâm sàng.
Ba luật Tuyền chốt:

1. Lấy các LƯỢT KHÁM ĐÃ HOÀN TẤT gần nhất (mặc định 3, chọn 1–3), bỏ lượt chỉ
   mua thuốc / bán lẻ (``visit.ban_le``, nhóm ``THUOC``) và buổi điều trị
   (``DIEU_TRI`` đếm theo buổi, không phải lượt khám — ``nhan_luot.py``).
   "Hoàn tất" = cùng luật ``recall_service``: lượt đã ký (FINALIZED / AMENDED)
   hoặc phiên khám cuối đã kết thúc (``consultation`` completed, DONE /
   NO_SERVICES). Lượt còn mở (OPEN / IN_PROGRESS) và lượt INCOMPLETE (khách về
   khi khám dở) thì bỏ qua — chưa ai chịu trách nhiệm chữ trong đó.
2. Mục như demo: lý do khám · sinh hiệu · sản khoa · cận lâm sàng · chẩn đoán ·
   hướng xử lý + đơn; hành chính + dị ứng / PARA / tiền sử ở đầu phiếu.
3. Ký cuối phiếu = bác sĩ của lượt MỚI NHẤT trên phiếu.

Mọi chữ lấy từ dữ liệu đã ghi, đọc bằng ĐÚNG các hàm bản in một lượt đang dùng
(``doc_dau_phieu``, ``sinh_hieu_cua_buoi_nhieu``, ``doc_ket_qua_theo_chi_dinh``,
``chu_o`` của phiếu v5, ``thai_ky_cua_luot``). Ô không đo / không làm để TRỐNG,
không tự điền. Ngưỡng bất thường là ``canh_bao_sinh_hieu`` (cùng ngưỡng màn đo
sinh hiệu); xu hướng tính ở đây — màn chỉ vẽ.

Chỉ ĐỌC. Quyền do router gác (đọc phiếu để in — ``QUYEN_DOC_DE_IN``).
Tham số người dùng gửi (số lần, lượt bỏ) rác → mặc định, không ném.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

import asyncpg

from clinicai.api.exceptions import NotFoundError
from clinicai.core.clock import CLINIC_TZ, hom_nay_vn, now_vn
from clinicai.phieu_kham.doc_chu import chu_o
from clinicai.phieu_kham.ket_qua_chi_dinh import doc_ket_qua_theo_chi_dinh
from clinicai.phieu_kham.mang_sang import doc_dau_phieu
from clinicai.services.luot_kham_rules import Vitals, canh_bao_sinh_hieu
from clinicai.services.nhan_luot import doc_nhan_luot, tra_nhan
from clinicai.services.sinh_hieu_buoi import sinh_hieu_cua_buoi_nhieu
from clinicai.services.thai_ky_service import (
    doc_ngay_tu_do,
    thai_ky_cua_luot,
    tuoi_thai_tu_edd,
)

#: Số lần in tối đa / mặc định (khổ A4 dọc vừa ba cột).
SO_LAN_TOI_DA = 3
#: Số lượt hiện ở "Chọn lượt…" để bỏ bớt — đủ lùi vài lượt khi bỏ lượt lạc.
SO_CHON_DUOC = 12
#: Trần số lượt đọc một lần (khách lâu năm cũng vài trăm lượt).
TRAN = 500

#: Nhóm loại khám KHÔNG phải lượt khám: buổi điều trị, mua thuốc.
_NHOM_KHONG_KHAM = frozenset({"DIEU_TRI", "THUOC"})

_SQL_LUOT = f"""
SELECT v.visit_id::text, v.appointment_id::text, v.ban_le,
       coalesce(v.checked_in_at, a.slot_start, v.created_at) AS luc,
       st.name AS dich_vu, st.nhom,
       v.status <> 'INCOMPLETE'
       AND (v.status IN ('FINALIZED', 'AMENDED')
        OR EXISTS (SELECT 1 FROM public.consultation c
                    WHERE c.clinic_id = v.clinic_id AND c.visit_id = v.visit_id
                      AND c.status = 'completed'
                      AND c.outcome IN ('NO_SERVICES', 'DONE'))) AS hoan_tat
  FROM public.visit v
  LEFT JOIN public.appointment a
    ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
  LEFT JOIN public.service_type st
    ON st.id = coalesce(v.service_type_id, a.service_type_id)
 WHERE v.clinic_id = $1::uuid AND v.clinic_patient_id = $2::uuid
 ORDER BY luc DESC, v.visit_id
 LIMIT {TRAN}
"""


# ── Tham số người dùng ──────────────────────────────────────────────────────


def doc_so_lan(raw: Any) -> int:
    """Số lần in: 1–3; rác / ngoài khoảng → 3. Không ném."""
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError):
        return SO_LAN_TOI_DA
    return n if 1 <= n <= SO_LAN_TOI_DA else SO_LAN_TOI_DA


def doc_bo(raw: Any) -> set[str]:
    """Mã lượt bỏ chọn ("a,b,c"): chỉ giữ UUID hợp lệ, tối đa 50. Không ném."""
    ra: set[str] = set()
    for phan in str(raw or "").split(",")[:50]:
        try:
            ra.add(str(UUID(phan.strip())))
        except ValueError:
            continue
    return ra


# ── Chọn lượt ───────────────────────────────────────────────────────────────


def la_luot_kham(r: Mapping[str, Any]) -> bool:
    """Lượt KHÁM đã hoàn tất: không bán lẻ, không buổi điều trị / mua thuốc."""
    return (
        bool(r.get("hoan_tat"))
        and not r.get("ban_le")
        and r.get("nhom") not in _NHOM_KHONG_KHAM
    )


def chon_luot(
    luot: Sequence[Mapping[str, Any]], *, so_lan: int, bo: set[str]
) -> list[Mapping[str, Any]]:
    """``luot`` mới nhất trước → các lượt in, CŨ → MỚI (cột trái là lần cũ).

    Lọc lượt khám hoàn tất, bỏ lượt người dùng bỏ chọn, lấy ``so_lan`` lượt
    mới nhất còn lại. Thuần."""
    kham = [r for r in luot if la_luot_kham(r) and str(r["visit_id"]) not in bo]
    return list(reversed(kham[: max(1, min(so_lan, SO_LAN_TOI_DA))]))


# ── Định dạng ──────────────────────────────────────────────────────────────


def so_vn(v: Any) -> str | None:
    """36.8 → "36,8"; 54.0 → "54"; None / rác → None (kiểu Việt, một số lẻ)."""
    if v is None or isinstance(v, bool):
        return None
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None
    if d == d.to_integral_value():
        return str(int(d))
    return f"{d.quantize(Decimal('0.1'))}".replace(".", ",")


def _ngay_vn(d: date | None) -> str | None:
    return d.strftime("%d/%m/%Y") if d else None


def ngay_cua(luc: Any) -> date | None:
    """Giờ check-in → NGÀY giờ phòng khám."""
    if not isinstance(luc, datetime):
        return None
    return (
        (luc if luc.tzinfo else luc.replace(tzinfo=CLINIC_TZ))
        .astimezone(CLINIC_TZ)
        .date()
    )


def chu_tuoi_thai(t: Mapping[str, int] | None) -> str | None:
    if not t:
        return None
    return f"{t['tuan']} tuần" + (f" {t['ngay']} ngày" if t["ngay"] else "")


# ── Sinh hiệu + xu hướng ───────────────────────────────────────────────────


def sinh_hieu_luot(do: Mapping[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    """Lần đo của buổi → (ô hiển thị, các ``truong`` bất thường theo ngưỡng
    máy chủ). Chưa đo → ({}, [])."""
    if not do:
        return {}, []
    tren, duoi = do.get("systolic"), do.get("diastolic")
    o = {
        "huyet_ap": f"{tren}/{duoi}" if tren is not None and duoi is not None else None,
        "mach": so_vn(do.get("pulse")),
        "nhiet": so_vn(do.get("temperature")),
        "can_nang": so_vn(do.get("weight_kg")),
        "bmi": so_vn(do.get("bmi")),
        "spo2": so_vn(do.get("spo2")),
    }
    if tren is None or duoi is None:  # cột NOT NULL — phòng dữ liệu lạ
        return o, []
    v = Vitals(
        systolic=int(tren),
        diastolic=int(duoi),
        pulse=do.get("pulse"),
        temperature=do.get("temperature"),
        spo2=do.get("spo2"),
    )
    return o, [c["truong"] for c in canh_bao_sinh_hieu(v)]


def xu_huong_huyet_ap(tam_thu: Sequence[int]) -> str | None:
    """Tâm thu CŨ → MỚI tăng / giảm đều mọi lần → câu ngắn; còn lại None."""
    if len(tam_thu) < 2:
        return None
    cap = list(zip(tam_thu, tam_thu[1:], strict=False))
    dan = " dần" if len(tam_thu) >= 3 else ""
    if all(b > a for a, b in cap):
        return f"↑ tăng{dan}"
    if all(b < a for a, b in cap):
        return f"↓ giảm{dan}"
    return None


def _khoang(ngay: int) -> str | None:
    if ngay >= 60:
        return f"{round(ngay / 30)} tháng"
    if ngay >= 14:
        return f"{ngay // 7} tuần"
    if ngay > 0:
        return f"{ngay} ngày"
    return None


def xu_huong_can_nang(diem: Sequence[tuple[date, Any]]) -> str | None:
    """(ngày, kg) CŨ → MỚI → "+5 kg / 2 tháng"; ít hơn 2 lần cân → None."""
    so = []
    for ngay, kg in diem:
        try:
            so.append((ngay, Decimal(str(kg))))
        except (InvalidOperation, ValueError):
            continue
    if len(so) < 2:
        return None
    chenh = so[-1][1] - so[0][1]
    khoang = _khoang((so[-1][0] - so[0][0]).days)
    if chenh == 0:
        chu = "không đổi"
    else:
        chu = f"{'+' if chenh > 0 else '−'}{so_vn(abs(chenh))} kg"
    return f"{chu} / {khoang}" if khoang else chu


# ── Phiếu khám v5 → các ô của tờ tóm tắt ───────────────────────────────────

_LY_DO = re.compile(r"^\s*(\d+\.\s*)?lý do", re.IGNORECASE)
_CHAN_DOAN = re.compile(
    r"chẩn đoán|kết luận|nguyên nhân|bệnh kèm|phân loại|đánh giá|tiên lượng",
    re.IGNORECASE,
)
_NHAN_THUA = re.compile(
    r"^(chẩn đoán|kết luận|đánh giá|điều trị|xử lý|xử trí|hướng xử|lời dặn)",
    re.IGNORECASE,
)
#: Ô kinh nguyệt / hôn nhân trong nhóm "Tiền sử": không phải tiền sử bệnh.
_KHONG_PHAI_TIEN_SU = (
    "_menarche",
    "_cycle",
    "_days",
    "_flow",
    "_dysmenorrhea",
    "_lmp",
    "_marriage",
    "_marriage_age",
    "_contraception",
    "_unprotected",
)


def _json(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return None
    return v


def _nhan(ten: str, chu: str) -> str:
    """Ô có nhãn tự nói (Chẩn đoán, Lời dặn…) → chỉ chữ; còn lại "nhãn: chữ"."""
    return chu if _NHAN_THUA.match(ten) else f"{ten}: {chu}"


def noi_dung_phieu(khung: Any, du_lieu: Any) -> dict[str, Any]:
    """Một phiếu khám v5 → các ô của tờ tóm tắt. Theo KHOÁ MỤC (B/D/E/G) và
    nhãn / nhóm của khung đúng phiên bản phiếu — không đọc tên phiếu. Rác →
    các danh sách rỗng. Thuần."""
    ra: dict[str, Any] = {
        "ly_do": [],
        "sieu_am": [],
        "xet_nghiem": [],
        "chan_doan": [],
        "xu_ly": [],
        "tien_su": [],
        "para": None,
        "di_ung": None,
        "di_ung_co": None,
        "du_sinh": None,
    }
    khung, du_lieu = _json(khung), _json(du_lieu)
    if not isinstance(khung, list) or not isinstance(du_lieu, Mapping):
        return ra
    for muc in khung:
        if not isinstance(muc, Mapping):
            continue
        mm = muc.get("ma")
        for o in muc.get("block") or []:
            if not isinstance(o, Mapping):
                continue
            ma = str(o.get("ma") or "")
            nhap = du_lieu.get(ma)
            chu = chu_o(o, nhap)
            if not chu:
                continue
            ten = str(o.get("ten") or "").strip()
            nhom = str(o.get("nhom") or "").strip().lower()
            if ma.endswith("_para"):
                ra["para"] = chu
            elif ma.endswith("_allergy_co"):
                ra["di_ung_co"] = chu
            elif ma.endswith("_allergy"):
                ra["di_ung"] = chu
            elif ma == "sk_edd":
                ra["du_sinh"] = (
                    nhap.get("gia_tri") if isinstance(nhap, Mapping) else None
                )
            elif mm == "B" and (
                _LY_DO.match(ten) or (ten.lower() == "khác" and _LY_DO.match(nhom))
            ):
                ra["ly_do"].append(chu)
            elif "cận lâm sàng" in nhom:
                if "siêu âm" in ten.lower():
                    ra["sieu_am"].append(
                        chu if ten.lower() == "siêu âm" else f"{ten}: {chu}"
                    )
                else:
                    ra["xet_nghiem"].append(f"{ten}: {chu}")
            elif (
                mm == "B" and "tiền sử" in nhom and not ma.endswith(_KHONG_PHAI_TIEN_SU)
            ):
                ra["tien_su"].append(f"{ten}: {chu}")
            elif mm == "D":
                ra["chan_doan" if _CHAN_DOAN.search(ten) else "xu_ly"].append(
                    _nhan(ten, chu)
                )
            elif mm == "E":
                ra["xu_ly"].append(chu)
            elif mm == "G":
                ra["xu_ly"].append(
                    f"Tái khám {chu}" if o.get("kieu") == "ngay" else _nhan(ten, chu)
                )
    # Dị ứng: ô "Có/Không" thắng — chọn "Không" thì chữ chi tiết cũ (ô ẩn
    # `hien_khi`) không còn hiệu lực.
    co = ra.pop("di_ung_co")
    if co and str(co).strip().lower().startswith("không"):
        ra["di_ung"] = co
    else:
        ra["di_ung"] = ra["di_ung"] or co
    return ra


# ── Kết quả cận lâm sàng ───────────────────────────────────────────────────

#: Phòng làm (node) → hàng của tờ tóm tắt. Thủ thuật sang "Hướng xử lý".
_HANG_THEO_NODE: tuple[tuple[str, str], ...] = (
    ("DICHVU-SIEUAM", "sieu_am"),
    ("DICHVU-LAYMAU", "xet_nghiem"),
    ("DICHVU-SANGLOC", "xet_nghiem"),
    ("DICHVU-KETQUA-XETNGHIEM", "xet_nghiem"),
    ("DICHVU-TINHDICHDO", "xet_nghiem"),
    ("DICHVU-THUTHUAT", "thu_thuat"),
    ("DICHVU-DUYET-KETQUA", "bo"),
    ("DICHVU-THUOC", "bo"),
)


def hang_cua_node(node: Any) -> str:
    n = str(node or "")
    for dau, hang in _HANG_THEO_NODE:
        if n.startswith(dau):
            return hang
    return "cls_khac"


def _la_ket_luan(o: Mapping[str, Any]) -> bool:
    return o.get("ma") == "ket_luan" or str(
        o.get("ten") or ""
    ).strip().lower().startswith("kết luận")


def _o_phieu(k: Mapping[str, Any]) -> Iterable[tuple[Mapping[str, Any], str]]:
    """(ô, chữ) CÓ CHỮ của một phiếu kết quả, theo thứ tự khung."""
    du_lieu = k.get("du_lieu") or {}
    for m in k.get("khung") or []:
        for o in (m or {}).get("block") or []:
            chu = chu_o(o, du_lieu.get(o.get("ma")))
            if chu:
                yield o, chu


def _kem_don_vi(o: Mapping[str, Any], chu: str) -> str:
    dv = str(o.get("don_vi") or "").strip()
    return f"{chu} {dv}" if dv and not chu.endswith(dv) else chu


def tom_tat_chi_dinh(c: Mapping[str, Any]) -> dict[str, str | None]:
    """Một chỉ định CLS → {chu, tim_thai, tuoi_thai}. Kết luận nếu có; không thì
    ba số đo đầu; chỉ có tệp → "có ảnh/tệp"; chưa có → "chưa có kết quả".
    Phiếu nháp không đọc (``ket_qua_chi_dinh``: nháp không phải kết quả)."""
    ten = str(c.get("ten_hien_thi") or "Dịch vụ")
    ket_qua = c.get("ket_qua") or []
    phieu = [
        k
        for k in ket_qua
        if k.get("loai") == "PHIEU"
        and k.get("trang_thai") == "READY"
        and k.get("khung")
    ]
    ra: dict[str, str | None] = {"chu": None, "tim_thai": None, "tuoi_thai": None}
    if phieu:
        o_chu = list(_o_phieu(phieu[0]))
        for o, chu in o_chu:
            if o.get("ma") == "tim_thai":
                ra["tim_thai"] = _kem_don_vi(o, chu)
            elif o.get("ma") == "tuoi_thai_uoc_tinh":
                ra["tuoi_thai"] = chu
        ket_luan = next((chu for o, chu in o_chu if _la_ket_luan(o)), None)
        if ket_luan:
            ra["chu"] = f"{ten}: {ket_luan}"
        elif o_chu:
            dong = [f"{o.get('ten')} {_kem_don_vi(o, chu)}" for o, chu in o_chu[:3]]
            ra["chu"] = f"{ten}: " + "; ".join(dong) + ("…" if len(o_chu) > 3 else "")
        else:
            ra["chu"] = f"{ten}: chưa ghi kết quả"
    elif any(k.get("loai") == "TEP" for k in ket_qua):
        ra["chu"] = f"{ten}: có ảnh / tệp kết quả"
    else:
        ra["chu"] = f"{ten}: chưa có kết quả"
    return ra


# ── Đọc ────────────────────────────────────────────────────────────────────


def _tuoi(ngay_sinh: str | None, nam_sinh: Any, hom_nay: date) -> int | None:
    d = doc_ngay_tu_do(ngay_sinh) if ngay_sinh else None
    if d:
        return hom_nay.year - d.year - ((hom_nay.month, hom_nay.day) < (d.month, d.day))
    return hom_nay.year - int(nam_sinh) if isinstance(nam_sinh, int) else None


async def _doc_phieu_v5(
    conn: asyncpg.Connection, clinic_id: str, visit_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """{visit_id: [nội dung từng phiếu v5]} — khung đúng phiên bản đã ghim."""
    rows = await conn.fetch(
        "SELECT p.visit_id::text, p.du_lieu, d.khung"
        "  FROM phieu_kham_luot p"
        "  JOIN form_definition d"
        "    ON d.clinic_id = p.clinic_id AND d.form_id = p.form_id"
        "   AND d.version = p.version"
        " WHERE p.clinic_id = $1::uuid AND p.visit_id = ANY($2::uuid[])"
        " ORDER BY p.tao_luc",
        clinic_id,
        visit_ids,
    )
    ra: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        ra.setdefault(r["visit_id"], []).append(
            noi_dung_phieu(r["khung"], r["du_lieu"])
        )
    return ra


async def _doc_don(
    conn: asyncpg.Connection, clinic_id: str, visit_ids: list[str]
) -> dict[str, list[str]]:
    """Đơn bác sĩ kê (cùng lọc ``PhieuKhamService.doc_don_thuoc``): tên + SL."""
    rows = await conn.fetch(
        "SELECT p.visit_id::text, p.drug_name_raw, p.quantity"
        "  FROM prescription p"
        " WHERE p.clinic_id = $1::uuid AND p.visit_id = ANY($2::uuid[])"
        "   AND p.removed_at IS NULL AND p.nguon = 'BAC_SI'"
        " ORDER BY p.created_at, p.id",
        clinic_id,
        visit_ids,
    )
    ra: dict[str, list[str]] = {}
    for r in rows:
        ten = str(r["drug_name_raw"] or "").strip()
        if not ten:
            continue
        sl = str(r["quantity"] or "").strip()
        ra.setdefault(r["visit_id"], []).append(f"{ten} — {sl}" if sl else ten)
    return ra


async def _mot_luot(
    conn: asyncpg.Connection,
    clinic_id: str,
    r: Mapping[str, Any],
    *,
    do: Mapping[str, Any] | None,
    phieu: list[dict[str, Any]],
    don: list[str],
    node: Mapping[str, str | None],
) -> dict[str, Any]:
    vid = str(r["visit_id"])
    ngay = ngay_cua(r["luc"])
    dau = await doc_dau_phieu(conn, clinic_id=clinic_id, visit_id=vid)
    sh, bat_thuong = sinh_hieu_luot(do)

    gop: dict[str, list[str]] = {
        k: [x for p in phieu for x in p[k]]
        for k in ("ly_do", "sieu_am", "xet_nghiem", "chan_doan", "xu_ly")
    }
    cls_khac: list[str] = []
    xu_ly_dv: list[str] = []
    tim_thai = tuoi_thai_sa = None
    for c in await doc_ket_qua_theo_chi_dinh(conn, clinic_id=clinic_id, visit_id=vid):
        if c.get("dieu_tri"):
            xu_ly_dv.append(f"Điều trị: {c.get('ten_hien_thi')}")
            continue
        hang = hang_cua_node(node.get(str(c["service_order_id"])))
        if hang == "bo":
            continue
        if hang == "thu_thuat":
            xu_ly_dv.append(f"Thủ thuật: {c.get('ten_hien_thi')}")
            continue
        t = tom_tat_chi_dinh(c)
        tim_thai = tim_thai or t["tim_thai"]
        tuoi_thai_sa = tuoi_thai_sa or t["tuoi_thai"]
        chu = t["chu"] or ""
        (cls_khac if hang == "cls_khac" else gop[hang]).append(chu)

    # Tuổi thai: thai kỳ bao trùm ngày khám (dự sinh bác sĩ đã ghi) → phép
    # trừ 280 ngày; không có thì số siêu âm ghi "tuổi thai ước tính".
    tk = await thai_ky_cua_luot(conn, clinic_id, vid)
    edd = (tk or {}).get("edd") or next(
        (doc_ngay_tu_do(p["du_sinh"]) for p in phieu if p["du_sinh"]), None
    )
    tuoi_thai = (
        chu_tuoi_thai(tuoi_thai_tu_edd(edd, ngay) if ngay else None) or tuoi_thai_sa
    )
    return {
        "visit_id": vid,
        "ngay": ngay.isoformat() if ngay else None,
        "dich_vu": r.get("dich_vu"),
        "bac_si": dau["the_khach"]["bac_si"],
        "ly_do": gop["ly_do"],
        "sinh_hieu": sh,
        "bat_thuong": bat_thuong,
        "xu_huong": {},
        "san_khoa": {"tuoi_thai": tuoi_thai, "tim_thai": tim_thai},
        "cls": {
            "sieu_am": gop["sieu_am"],
            "xet_nghiem": gop["xet_nghiem"],
            "khac": cls_khac,
        },
        "chan_doan": gop["chan_doan"],
        "xu_ly": gop["xu_ly"] + xu_ly_dv,
        "don": don,
        "_dau": dau,
        "_phieu": phieu,
        "_tk": tk,
        "_do": do,
    }


def gan_xu_huong(luot: list[dict[str, Any]]) -> None:
    """Xu hướng huyết áp / cân nặng gắn vào lượt MỚI NHẤT có số đo ấy."""
    co_ha = [x for x in luot if (x.get("_do") or {}).get("systolic") is not None]
    if co_ha:
        xh = xu_huong_huyet_ap([int(x["_do"]["systolic"]) for x in co_ha])
        if xh:
            co_ha[-1]["xu_huong"]["huyet_ap"] = xh
    co_can = [
        x
        for x in luot
        if (x.get("_do") or {}).get("weight_kg") is not None and x.get("ngay")
    ]
    if co_can:
        xh = xu_huong_can_nang(
            [(date.fromisoformat(x["ngay"]), x["_do"]["weight_kg"]) for x in co_can]
        )
        if xh:
            co_can[-1]["xu_huong"]["can_nang"] = xh


def nen_tang(luot: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Dị ứng · PARA · tiền sử: bản ghi của lượt MỚI NHẤT có ghi. Thuần."""
    moi_truoc = [p for x in reversed(luot) for p in x["_phieu"]]

    def dau_tien(k: str) -> Any:
        return next((p[k] for p in moi_truoc if p[k]), None)

    return {
        "di_ung": dau_tien("di_ung"),
        "para": dau_tien("para"),
        "tien_su": dau_tien("tien_su") or [],
    }


async def doc(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    clinic_patient_id: str,
    so_lan: Any = None,
    bo: Any = None,
) -> dict[str, Any]:
    """Tờ tóm tắt ``so_lan`` lượt khám hoàn tất gần nhất (cũ → mới) của khách."""
    khach = await conn.fetchrow(
        "SELECT full_name, patient_code FROM patient"
        " WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid",
        clinic_id,
        clinic_patient_id,
    )
    if khach is None:
        raise NotFoundError("Không tìm thấy khách.")
    n = doc_so_lan(so_lan)
    bo_chon = doc_bo(bo)
    tat_ca = [
        dict(r) for r in await conn.fetch(_SQL_LUOT, clinic_id, clinic_patient_id)
    ]
    kham = [r for r in tat_ca if la_luot_kham(r)]
    chon = chon_luot(tat_ca, so_lan=n, bo=bo_chon)
    nhan = await doc_nhan_luot(conn, clinic_id, [clinic_patient_id]) if kham else {}
    chon_duoc = [
        {
            "visit_id": r["visit_id"],
            "ngay": (ngay_cua(r["luc"]) or date.min).isoformat(),
            "dich_vu": r["dich_vu"],
            "nhan_luot": (
                tra_nhan(
                    nhan, visit_id=r["visit_id"], appointment_id=r["appointment_id"]
                )
                or {}
            ).get("nhan"),
            "bo": r["visit_id"] in bo_chon,
        }
        for r in kham[:SO_CHON_DUOC]
    ]
    in_luc = now_vn()
    goc: dict[str, Any] = {
        "khach": {"ho_ten": khach["full_name"], "ma": khach["patient_code"]},
        "dau_trang": {},
        "nen_tang": {
            "di_ung": None,
            "para": None,
            "tien_su": [],
            "ky_kinh_cuoi": None,
            "du_sinh": None,
        },
        "co_thai": False,
        "tong_lan_kham": len(kham),
        "so_lan": n,
        "luot": [],
        "chon_duoc": chon_duoc,
        "bac_si_ky": None,
        "in_luc": in_luc.isoformat(),
    }
    if not chon:
        return goc

    ids = [str(r["visit_id"]) for r in chon]
    do = await sinh_hieu_cua_buoi_nhieu(conn, clinic_id, ids)
    phieu = await _doc_phieu_v5(conn, clinic_id, ids)
    don = await _doc_don(conn, clinic_id, ids)
    node = {
        str(r["id"]): r["node_code"]
        for r in await conn.fetch(
            "SELECT id, node_code FROM service_order"
            " WHERE clinic_id = $1::uuid AND visit_id = ANY($2::uuid[])",
            clinic_id,
            ids,
        )
    }
    luot = [
        await _mot_luot(
            conn,
            clinic_id,
            r,
            do=do.get(str(r["visit_id"])),
            phieu=phieu.get(str(r["visit_id"]), []),
            don=don.get(str(r["visit_id"]), []),
            node=node,
        )
        for r in chon
    ]
    gan_xu_huong(luot)

    moi = luot[-1]
    hc = moi["_dau"]["hanh_chinh"]
    tk_moi = moi["_tk"] or {}
    du_sinh = tk_moi.get("edd") or next(
        (doc_ngay_tu_do(p["du_sinh"]) for p in moi["_phieu"] if p["du_sinh"]), None
    )
    hom_nay = hom_nay_vn()
    goc["khach"] = {
        "ho_ten": hc.get("patient.name"),
        "ma": hc.get("patient.code"),
        "ngay_sinh": hc.get("patient.date_of_birth"),
        "nam_sinh": hc.get("patient.birth_year"),
        "tuoi": _tuoi(
            hc.get("patient.date_of_birth"), hc.get("patient.birth_year"), hom_nay
        ),
        "gioi": hc.get("patient.gender"),
        "sdt": hc.get("patient.phone"),
        "dia_chi": hc.get("patient.address"),
        "nghe_nghiep": hc.get("patient.occupation"),
    }
    tkh = moi["_dau"]["the_khach"]
    goc["dau_trang"] = {
        "phong_kham": tkh.get("phong_kham"),
        "co_so": tkh.get("co_so"),
        "dia_chi_co_so": tkh.get("dia_chi_co_so"),
    }
    goc["nen_tang"] = {
        **nen_tang(luot),
        "ky_kinh_cuoi": _ngay_vn(tk_moi.get("lmp")),
        "du_sinh": _ngay_vn(du_sinh),
    }
    goc["co_thai"] = bool(
        goc["nen_tang"]["ky_kinh_cuoi"]
        or goc["nen_tang"]["du_sinh"]
        or any(x["san_khoa"]["tuoi_thai"] or x["san_khoa"]["tim_thai"] for x in luot)
    )
    goc["bac_si_ky"] = moi["bac_si"]
    goc["luot"] = [{k: v for k, v in x.items() if not k.startswith("_")} for x in luot]
    return goc


__all__ = [
    "SO_LAN_TOI_DA",
    "chon_luot",
    "doc",
    "doc_bo",
    "doc_so_lan",
    "gan_xu_huong",
    "hang_cua_node",
    "la_luot_kham",
    "noi_dung_phieu",
    "sinh_hieu_luot",
    "so_vn",
    "tom_tat_chi_dinh",
    "xu_huong_can_nang",
    "xu_huong_huyet_ap",
]
