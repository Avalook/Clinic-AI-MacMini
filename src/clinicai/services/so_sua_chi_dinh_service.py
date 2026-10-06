"""SỔ SỬA / BỎ CHỈ ĐỊNH (Khối 2, Tuyền chốt 06/10/2026).

Thao tác sửa chỉ định ĐÃ CÓ (ô tích đầu dòng → `HoanTacService.huy_chi_dinh`,
tick dịch vụ khám → `PhiKhamService.chon`, "Bỏ thuốc này" → lưu cả đơn). File
này lo phần còn thiếu:

1. **Sổ** (`so_sua_chi_dinh`, mig 20261006200000): mỗi lần THÊM / BỎ / HOÀN TÁC
   chỉ định, đủ bốn nhóm Khám · CLS · Điều trị · Thuốc. Chỉ định dịch vụ và dịch
   vụ khám ghi bằng TRIGGER (đường nào cũng để lại vết); lệnh chỉ đặt ngữ cảnh
   (`dat_ngu_canh`: người bấm, vai đang dùng, lý do). Thuốc: so đơn trước/sau
   mỗi lần lưu (`ghi_so_thuoc`, gọi trong `luu_don_chua_ky`).
2. **Quyền**: ai có quyền chỉ định thì sửa / bỏ được NGAY, có hiệu lực luôn —
   trưởng ca, quản lý ngang bác sĩ chính (hỏi QUYỀN, không hỏi vai). Không chờ
   ai xác nhận.
3. **Thông báo**: NGƯỜI KHÁC bác sĩ chính bỏ chỉ định → bác sĩ chính nhận thông
   báo, nút DUY NHẤT là "Hoàn tác" (`bao_bac_si_chinh`).
4. **Hoàn tác** = đặt lại đúng chỉ định ấy, ghi thêm dòng sổ
   (`SoSuaChiDinhService.hoan_tac`). Mỗi dòng BỎ hoàn tác đúng MỘT lần — ép ở
   Postgres (`uq_so_sua_chi_dinh_hoan_tac`).
5. Lượt chuyển từ hồ sơ cũ (Notion, 20261006100000) chỉ xem (`chan_ho_so_cu`).

Thuốc bỏ đi chỉ ghi sổ (không có nút Hoàn tác): kê lại dòng thuốc là một thao
tác của chính màn kê đơn.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.tran import canh_bao_neu_day
from clinicai.events.catalogue import ChiDinhDatLai, DichVuKhamDaDoi
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import doi_quyen
from clinicai.services.audit import record_event
from clinicai.services.lenh_kham_core import (
    LuotKhamConflictError,
    LuotKhamValidationError,
    khoa_luot,
)
from clinicai.services.lenh_kham_core import ma_uuid as _uuid
from clinicai.services.nhan_vai import nhan_vai
from clinicai.services.thong_bao_service import ghi_thong_bao_nguoi
from clinicai.services.xem_luot_service import goi_duoc

ORIGIN = "api:so-sua-chi-dinh"

QUYEN_CHI_DINH = "clinical.order.place"

#: Cùng người sửa cùng dòng thuốc trong chừng này phút → gộp vào dòng sổ đang
#: mở (đơn tự lưu theo nhịp gõ; cùng luật lịch sử sửa phiếu).
GOP_PHUT = 10

NHAN_NHOM: dict[str, str] = {
    "KHAM": "Khám",
    "CLS": "Cận lâm sàng",
    "DIEU_TRI": "Điều trị",
    "THUOC": "Thuốc",
}

NHAN_HANH_DONG: dict[str, str] = {
    "THEM": "Thêm",
    "BO": "Bỏ",
    "HOAN_TAC": "Hoàn tác bỏ",
    "DOI": "Đổi",
}

#: Trường so của một dòng thuốc → nhãn người đọc.
TRUONG_THUOC: dict[str, str] = {
    "ten": "Tên thuốc",
    "so_luong": "Số lượng",
    "cach_dung": "Cách dùng",
    "luu_y": "Lưu ý",
}


# ---------------------------------------------------------------------------
# Phần thuần
# ---------------------------------------------------------------------------


def _chu(v: Any) -> str:
    """Giá trị một ô đơn → chuỗi so được (None / rác / số → chuỗi gọn)."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return " ".join(str(v).split())


def _khoa_thuoc(d: dict[str, Any]) -> str:
    """Khoá nhận ra CÙNG một thuốc khi dòng bị thay (đính chính đổi mã dòng)."""
    ma = d.get("drug_catalog_id")
    if ma:
        return f"kho:{ma}"
    return "ten:" + "".join(_chu(d.get("drug_name_raw")).split()).lower()


def _anh_thuoc(d: dict[str, Any]) -> dict[str, str]:
    return {
        "ten": _chu(d.get("drug_name_raw")),
        "so_luong": _chu(d.get("quantity")),
        "cach_dung": _chu(d.get("dosage_instructions")),
        "luu_y": _chu(d.get("caution")),
    }


@dataclass
class ThayDoiThuoc:
    hanh_dong: str  # THEM | BO | DOI
    dong_id: str | None
    ma: str | None
    ten: str
    truoc: dict[str, str] = field(default_factory=dict)
    sau: dict[str, str] = field(default_factory=dict)


def so_sanh_don(
    truoc: list[dict[str, Any]], sau: list[dict[str, Any]]
) -> list[ThayDoiThuoc]:
    """So đơn TRƯỚC / SAU một lần lưu → dòng thêm, dòng bỏ, dòng đổi.

    Ghép theo MÃ DÒNG trước; dòng còn lẻ ghép theo THUỐC (đính chính thay dòng
    mới cho cùng thuốc). Rác (không phải dict, thiếu tên) bỏ qua, không ném.
    """
    t = [d for d in truoc if isinstance(d, dict)]
    s = [d for d in sau if isinstance(d, dict)]
    t_id = {str(d.get("id")): d for d in t if d.get("id") is not None}
    s_id = {str(d.get("id")): d for d in s if d.get("id") is not None}
    cap: list[tuple[dict[str, Any], dict[str, Any]]] = [
        (t_id[i], s_id[i]) for i in t_id if i in s_id
    ]
    t_le = [d for d in t if str(d.get("id")) not in s_id]
    s_le = [d for d in s if str(d.get("id")) not in t_id]
    con_t = list(t_le)
    s_moi: list[dict[str, Any]] = []
    for d in s_le:
        k = _khoa_thuoc(d)
        hop = next((x for x in con_t if _khoa_thuoc(x) == k), None)
        if hop is None:
            s_moi.append(d)
        else:
            con_t.remove(hop)
            cap.append((hop, d))
    ra: list[ThayDoiThuoc] = []
    for a, b in cap:
        aa, bb = _anh_thuoc(a), _anh_thuoc(b)
        doi = {k: aa[k] for k in aa if aa[k] != bb[k]}
        if doi:
            ra.append(
                ThayDoiThuoc(
                    "DOI",
                    str(b.get("id")) if b.get("id") is not None else None,
                    _ma(b),
                    bb["ten"] or aa["ten"],
                    truoc={k: aa[k] for k in doi},
                    sau={k: bb[k] for k in doi},
                )
            )
    for d in con_t:
        a = _anh_thuoc(d)
        if a["ten"]:
            ra.append(
                ThayDoiThuoc(
                    "BO",
                    str(d.get("id")) if d.get("id") is not None else None,
                    _ma(d),
                    a["ten"],
                    truoc=a,
                )
            )
    for d in s_moi:
        b = _anh_thuoc(d)
        if b["ten"]:
            ra.append(
                ThayDoiThuoc(
                    "THEM",
                    str(d.get("id")) if d.get("id") is not None else None,
                    _ma(d),
                    b["ten"],
                    sau=b,
                )
            )
    return ra


def _ma(d: dict[str, Any]) -> str | None:
    ma = d.get("drug_catalog_id")
    return str(ma) if ma else None


def _tien(v: int) -> str:
    return f"{v:,}".replace(",", ".") + "đ"


def cau_so(d: dict[str, Any]) -> str:
    """Một dòng sổ → câu người đọc. "Bỏ CLS “Siêu âm …” · đã thu 300.000đ →
    tiền thừa 300.000đ". Thiếu dữ liệu thì bỏ vế ấy, không ném."""
    hd = NHAN_HANH_DONG.get(str(d.get("hanh_dong")), str(d.get("hanh_dong") or ""))
    nhom = NHAN_NHOM.get(str(d.get("nhom")), "")
    cau = f"{hd} {nhom.lower()} “{d.get('ten_muc') or '?'}”".strip()
    if d.get("hanh_dong") == "DOI":
        ct = d.get("chi_tiet") or {}
        truoc = ct.get("truoc") or {}
        sau = ct.get("sau") or {}
        ve = [
            f"{TRUONG_THUOC.get(k, k)}: {truoc.get(k) or '—'} → {sau.get(k) or '—'}"
            for k in TRUONG_THUOC
            if k in truoc or k in sau
        ]
        if ve:
            cau += " · " + "; ".join(ve)
    da_thu = int(d.get("da_thu") or 0)
    if d.get("hanh_dong") == "BO" and da_thu > 0:
        thua = _tien(int(d.get("tien_thua") or 0))
        cau += f" · đã thu {_tien(da_thu)} → tiền thừa {thua}"
    return cau


def _iso(v: Any) -> str | None:
    return v.isoformat() if isinstance(v, datetime) else None


def dong_so(r: dict[str, Any], *, chi_xem: bool = False) -> dict[str, Any]:
    """Một dòng `so_sua_chi_dinh` → dạng màn đọc (nhãn do máy chủ đặt)."""
    ct = r.get("chi_tiet")
    if isinstance(ct, str):
        try:
            ct = json.loads(ct)
        except ValueError:
            ct = {}
    r = {**r, "chi_tiet": ct if isinstance(ct, dict) else {}}
    hoan_tac_duoc = (
        not chi_xem
        and r.get("hanh_dong") == "BO"
        and r.get("nhom") != "THUOC"
        and r.get("hoan_tac_luc") is None
        and bool(r.get("con_bo"))
    )
    return {
        "id": str(r["id"]),
        "luc": _iso(r.get("luc")),
        "sua_luc": _iso(r.get("sua_luc")),
        "nhom": r.get("nhom"),
        "nhom_nhan": NHAN_NHOM.get(str(r.get("nhom")), ""),
        "hanh_dong": r.get("hanh_dong"),
        "hanh_dong_nhan": NHAN_HANH_DONG.get(str(r.get("hanh_dong")), ""),
        "ten_muc": r.get("ten_muc"),
        "cau": cau_so(r),
        "boi": r.get("boi_ten"),
        "boi_vai": nhan_vai(r.get("boi_vai"))[0] or None,
        "phong_kham": r.get("phong_kham_ten"),
        "bac_si_chinh": r.get("bac_si_chinh_ten"),
        "chi_dinh_goc_boi": r.get("chi_dinh_goc_boi_ten"),
        "da_thu": int(r.get("da_thu") or 0),
        "tien_thua": int(r.get("tien_thua") or 0),
        "ly_do": r.get("ly_do"),
        "da_bao_bac_si_luc": _iso(r.get("da_bao_bac_si_luc")),
        "hoan_tac_boi": r.get("hoan_tac_boi_ten"),
        "hoan_tac_luc": _iso(r.get("hoan_tac_luc")),
        "hoan_tac_duoc": hoan_tac_duoc,
    }


# ---------------------------------------------------------------------------
# Nền dùng chung (gọi TRONG giao dịch của lệnh)
# ---------------------------------------------------------------------------


async def dat_ngu_canh(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    *,
    ly_do: str | None = None,
    hoan_tac_cua: str | None = None,
) -> None:
    """Người bấm + vai ĐANG DÙNG + lý do cho trigger sổ — sống tới hết giao dịch."""
    await conn.execute(
        "SELECT set_config('clinicai.so_nguoi', $1, true),"
        "       set_config('clinicai.so_vai', $2, true),"
        "       set_config('clinicai.so_ly_do', $3, true),"
        "       set_config('clinicai.so_hoan_tac_cua', $4, true)",
        str(identity.staff_id),
        identity.role.value,
        (ly_do or "")[:500],
        hoan_tac_cua or "",
    )


async def la_ho_so_cu(conn: asyncpg.Connection, visit_id: str) -> bool:
    return bool(
        await conn.fetchval("SELECT public.la_luot_ho_so_cu($1::uuid)", visit_id)
    )


async def chan_ho_so_cu(conn: asyncpg.Connection, visit_id: str) -> None:
    """Lượt chuyển từ hồ sơ cũ (Notion) chỉ xem — không sửa / bỏ chỉ định."""
    if await la_ho_so_cu(conn, visit_id):
        raise LuotKhamConflictError(
            "HO_SO_CU",
            "Lượt này chuyển từ hồ sơ cũ (trước 10/2026) — chỉ xem, không sửa"
            " hay bỏ chỉ định được.",
        )


async def dong_bo_moi_nhat(
    conn: asyncpg.Connection,
    *,
    service_order_id: str | None = None,
    luot_phi_kham_id: str | None = None,
) -> str | None:
    """Dòng BỎ vừa ghi (chưa hoàn tác) của một chỉ định / một dịch vụ khám."""
    if service_order_id:
        cot, ma = "service_order_id", service_order_id
    elif luot_phi_kham_id:
        cot, ma = "luot_phi_kham_id", luot_phi_kham_id
    else:
        return None
    v = await conn.fetchval(
        f"SELECT id::text FROM so_sua_chi_dinh WHERE {cot} = $1::uuid"
        " AND hanh_dong = 'BO' AND hoan_tac_luc IS NULL ORDER BY stt DESC LIMIT 1",
        ma,
    )
    return str(v) if v is not None else None


async def bao_bac_si_chinh(
    conn: asyncpg.Connection, identity: StaffIdentity, so_id: str | None
) -> bool:
    """NGƯỜI KHÁC bác sĩ chính bỏ chỉ định → báo bác sĩ chính (nút DUY NHẤT là
    Hoàn tác). Ghi lúc báo vào dòng sổ. Trả True khi có báo."""
    if not so_id:
        return False
    so = await conn.fetchrow(
        """
        SELECT s.id::text, s.visit_id::text, s.nhom, s.ten_muc, s.boi_staff_id::text,
               s.boi_ten, s.boi_vai, s.bac_si_chinh_id::text, s.da_thu, s.tien_thua,
               s.ly_do, p.full_name AS ten_khach
          FROM so_sua_chi_dinh s
          LEFT JOIN visit v ON v.visit_id = s.visit_id AND v.clinic_id = s.clinic_id
          LEFT JOIN patient p ON p.clinic_patient_id = v.clinic_patient_id
         WHERE s.id = $1::uuid
        """,
        so_id,
    )
    if so is None or not so["bac_si_chinh_id"]:
        return False
    if so["bac_si_chinh_id"] == so["boi_staff_id"]:
        return False  # chính bác sĩ chính bỏ — không tự báo mình
    vai = nhan_vai(so["boi_vai"])[0]
    noi = f"{so['boi_ten'] or 'Một người'}{f' ({vai})' if vai else ''} bỏ"
    noi += f" {NHAN_NHOM.get(so['nhom'], '').lower()} “{so['ten_muc']}”"
    if int(so["da_thu"] or 0) > 0:
        noi += (
            f" — đã thu {_tien(int(so['da_thu']))}, thành tiền thừa"
            f" {_tien(int(so['tien_thua'] or 0))} ở quầy"
        )
    if so["ly_do"]:
        noi += f". Lý do: {so['ly_do']}"
    tb_id = await ghi_thong_bao_nguoi(
        conn,
        identity=identity,
        nguoi_nhan_staff_id=so["bac_si_chinh_id"],
        tieu_de=f"Chỉ định bị bỏ — {so['ten_khach'] or 'khách'}",
        noi_dung=noi + ".",
        nguon="bo_chi_dinh",
        nguon_id=so["id"],
        duong_dan="/ban-kham",
    )
    await conn.execute(
        "UPDATE so_sua_chi_dinh SET da_bao_bac_si_luc = now(),"
        "       thong_bao_id = coalesce($2::uuid, thong_bao_id)"
        " WHERE id = $1::uuid",
        so_id,
        tb_id,
    )
    return True


async def ghi_so_thuoc(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    visit_id: str,
    staff_id: str | None,
    vai: str | None,
    truoc: list[dict[str, Any]],
    sau: list[dict[str, Any]],
    ly_do: str | None,
) -> int:
    """So đơn trước/sau một lần lưu, ghi sổ nhóm THUỐC. Trả số thay đổi.

    Cùng người sửa CÙNG dòng trong `GOP_PHUT` phút → gộp vào dòng sổ đang mở
    (thêm rồi gõ tiếp liều, đổi liều nhiều lần): giữ "trước" của lần đầu, lấy
    "sau" mới nhất. Người gọi đã khoá lượt nên hai lần lưu nối tiếp nhau.
    """
    thay = so_sanh_don(truoc, sau)
    if not thay:
        return 0
    nc = await conn.fetchrow(
        "SELECT * FROM public.so_chi_dinh_ngu_canh($1::uuid, $2::uuid)",
        clinic_id,
        visit_id,
    )
    ten_nguoi = (
        await conn.fetchval("SELECT full_name FROM staff WHERE id = $1::uuid", staff_id)
        if staff_id
        else None
    )
    if staff_id and not vai:
        vai = await conn.fetchval(
            "SELECT role FROM clinic_membership WHERE clinic_id = $1::uuid"
            " AND staff_id = $2::uuid AND is_active ORDER BY created_at LIMIT 1",
            clinic_id,
            staff_id,
        )
    ly = (ly_do or "").strip()[:500] or None
    for t in thay:
        if t.hanh_dong == "DOI" and t.dong_id:
            mo = await conn.fetchrow(
                """
                SELECT id::text, hanh_dong, chi_tiet FROM so_sua_chi_dinh
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   AND nhom = 'THUOC' AND hanh_dong IN ('THEM', 'DOI')
                   AND boi_staff_id IS NOT DISTINCT FROM $3::uuid
                   AND (dong_thuoc_id = $4::uuid
                        OR chi_tiet -> 'sau' ->> 'ten' = $5)
                   AND sua_luc > now() - make_interval(mins => $6)
                 ORDER BY stt DESC LIMIT 1
                """,
                clinic_id,
                visit_id,
                staff_id,
                t.dong_id,
                t.truoc.get("ten") or t.ten,
                GOP_PHUT,
            )
            if mo is not None:
                ct = mo["chi_tiet"]
                ct = json.loads(ct) if isinstance(ct, str) else dict(ct or {})
                if mo["hanh_dong"] == "THEM":
                    ct["sau"] = {**(ct.get("sau") or {}), **t.sau}
                else:
                    truoc_cu = dict(ct.get("truoc") or {})
                    for k, v in t.truoc.items():
                        truoc_cu.setdefault(k, v)
                    ct["truoc"] = truoc_cu
                    ct["sau"] = {**(ct.get("sau") or {}), **t.sau}
                await conn.execute(
                    "UPDATE so_sua_chi_dinh SET chi_tiet = $2::jsonb, ten_muc = $3,"
                    "       dong_thuoc_id = $4::uuid, sua_luc = now(),"
                    "       ly_do = coalesce($5, ly_do)"
                    " WHERE id = $1::uuid",
                    mo["id"],
                    json.dumps(ct, ensure_ascii=False),
                    t.ten,
                    t.dong_id,
                    ly,
                )
                continue
        await conn.execute(
            """
            INSERT INTO so_sua_chi_dinh
                (clinic_id, visit_id, nhom, hanh_dong, dong_thuoc_id, ma_muc,
                 ten_muc, chi_tiet, boi_staff_id, boi_ten, boi_vai,
                 phong_kham_ten, bac_si_chinh_id, bac_si_chinh_ten, ly_do)
            VALUES ($1::uuid, $2::uuid, 'THUOC', $3, $4::uuid, $5, $6, $7::jsonb,
                    $8::uuid, $9, $10, $11, $12::uuid, $13, $14)
            """,
            clinic_id,
            visit_id,
            t.hanh_dong,
            t.dong_id,
            t.ma,
            t.ten,
            json.dumps({"truoc": t.truoc, "sau": t.sau}, ensure_ascii=False),
            staff_id,
            ten_nguoi,
            vai,
            nc["phong_kham_ten"] if nc else None,
            nc["bac_si_chinh_id"] if nc else None,
            nc["bac_si_chinh_ten"] if nc else None,
            ly,
        )
    return len(thay)


async def doc_don_de_so(
    conn: asyncpg.Connection, clinic_id: str | None, visit_id: Any
) -> list[dict[str, Any]]:
    """Đơn bác sĩ HIỆN HÀNH của lượt — ảnh để so trước/sau một lần lưu."""
    return [
        dict(r)
        for r in await conn.fetch(
            "SELECT id::text AS id, drug_catalog_id::text AS drug_catalog_id,"
            "       drug_name_raw, quantity, dosage_instructions, caution"
            "  FROM prescription WHERE visit_id = $1::uuid AND clinic_id = $2::uuid"
            "   AND removed_at IS NULL AND nguon = 'BAC_SI' ORDER BY created_at, id",
            visit_id,
            clinic_id,
        )
    ]


_SQL_SO = """
    SELECT s.*,
           CASE WHEN s.service_order_id IS NOT NULL
                THEN o.exec_status = 'cancelled'
                WHEN s.luot_phi_kham_id IS NOT NULL
                THEN k.bo_luc IS NOT NULL
                ELSE false END AS con_bo
      FROM so_sua_chi_dinh s
      LEFT JOIN service_order o ON o.id = s.service_order_id
      LEFT JOIN luot_phi_kham k ON k.id = s.luot_phi_kham_id
     WHERE s.clinic_id = $1::uuid AND s.visit_id = $2::uuid
     ORDER BY s.stt DESC
     LIMIT 300
"""

#: Trần số dòng sổ một lượt trả về (một lượt thật vài chục dòng). Chạm trần thì
#: log kêu (`canh_bao_neu_day`) và màn nhận `bi_cat` — không cắt im lặng.
TRAN_SO = 300


async def doc_so(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> dict[str, Any]:
    """Sổ của một lượt (mới nhất trước) + cờ chỉ xem (hồ sơ cũ)."""
    chi_xem = await la_ho_so_cu(conn, visit_id)
    rows = await conn.fetch(_SQL_SO, clinic_id, visit_id)
    bi_cat = canh_bao_neu_day("so_sua_chi_dinh", len(rows), TRAN_SO, visit_id=visit_id)
    return {
        "chi_xem": chi_xem,
        "bi_cat": bi_cat,
        "dong": [dong_so(dict(r), chi_xem=chi_xem) for r in rows],
    }


# ---------------------------------------------------------------------------
# Lệnh
# ---------------------------------------------------------------------------


class SoSuaChiDinhService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def doc(self, *, visit_id: str, identity: StaffIdentity) -> dict[str, Any]:
        """Lịch sử sửa chỉ định của một lượt — mọi thành viên nội bộ (cùng cửa
        Xem lượt / Hành trình)."""
        if not goi_duoc(identity):
            raise SafetyGateError("Tài khoản của bạn không xem lịch sử lượt khám.")
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        async with self._pool.acquire() as conn:
            co = await conn.fetchval(
                "SELECT 1 FROM visit"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
                identity.clinic_id,
                vid,
            )
            if co is None:
                raise NotFoundError("Không tìm thấy lượt khám.")
            return await doc_so(conn, identity.clinic_id, vid)

    async def hoan_tac(
        self,
        *,
        so_id: str,
        identity: StaffIdentity,
        ly_do: Any = None,
    ) -> dict[str, Any]:
        """HOÀN TÁC một lần bỏ chỉ định: đặt lại đúng chỉ định / dịch vụ khám
        ấy, ghi thêm dòng sổ, đóng thông báo của bác sĩ chính. Có hiệu lực
        ngay; bấm hai lần (hay hai máy) = lần sau trả `already`."""
        from clinicai.services.hang_cho import cap_nhat_vi_tri
        from clinicai.services.hoan_tac_service import doc_ly_do, mo_lai_moc_kham_xong
        from clinicai.services.luot_kham_service import LuotKhamService
        from clinicai.services.phi_kham_service import (
            _co_quyen_tick,
            chan_trung_dich_vu_kham,
        )

        cid = identity.clinic_id
        sid = _uuid(so_id, "Mã dòng sổ không hợp lệ.")
        ly = doc_ly_do(ly_do)
        async with self._pool.acquire() as conn, conn.transaction():
            so = await conn.fetchrow(
                "SELECT id::text, visit_id::text, nhom, hanh_dong,"
                "       service_order_id::text, luot_phi_kham_id::text, ten_muc,"
                "       chi_tiet, hoan_tac_luc"
                "  FROM so_sua_chi_dinh WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                sid,
            )
            if so is None:
                raise NotFoundError("Không tìm thấy dòng lịch sử này.")
            if (
                so["hanh_dong"] != "BO"
                or so["nhom"] == "THUOC"
                or not (so["service_order_id"] or so["luot_phi_kham_id"])
            ):
                raise LuotKhamValidationError(
                    "KHONG_HOAN_TAC_DUOC",
                    "Chỉ hoàn tác được một lần BỎ chỉ định dịch vụ / dịch vụ khám.",
                )
            if so["service_order_id"]:
                await doi_quyen(
                    conn,
                    identity,
                    QUYEN_CHI_DINH,
                    cau="Bạn không có quyền chỉ định dịch vụ nên không hoàn tác được.",
                )
            elif not await _co_quyen_tick(conn, identity):
                raise SafetyGateError("Bạn không có quyền chọn dịch vụ khám.")
            vid = so["visit_id"]
            await chan_ho_so_cu(conn, vid)
            await khoa_luot(conn, cid, vid, cho_phep_ve_giua_chung=True)
            if so["hoan_tac_luc"] is not None:
                return {"ok": True, "already": True, "so_id": sid, "visit_id": vid}
            await dat_ngu_canh(conn, identity, ly_do=ly, hoan_tac_cua=sid)

            if so["service_order_id"]:
                kq = await self._dat_lai_chi_dinh(conn, identity, so, ly)
            else:
                kq = await self._tick_lai_kham(
                    conn, identity, so, chan_trung_dich_vu_kham
                )
            if kq.get("already"):
                return {"ok": True, "already": True, "so_id": sid, "visit_id": vid}

            luot = LuotKhamService(pool=None)
            await mo_lai_moc_kham_xong(conn, cid, vid)
            await luot._evaluate_rounds(conn, identity, vid)
            await cap_nhat_vi_tri(conn, cid, vid)
            # Thông báo "chỉ định bị bỏ" của bác sĩ chính: đã xử lý (bằng hoàn tác).
            await conn.execute(
                "UPDATE thong_bao SET da_xu_ly_luc = now(), da_xu_ly_boi = $3::uuid,"
                "       ghi_chu_xu_ly = 'Hoàn tác bỏ chỉ định',"
                "       da_doc_luc = coalesce(da_doc_luc, now())"
                " WHERE clinic_id = $1::uuid AND nguon = 'bo_chi_dinh'"
                "   AND nguon_id = $2 AND da_xu_ly_luc IS NULL",
                cid,
                sid,
                identity.staff_id,
            )
            await record_event(
                conn,
                event_type="service_order.restored",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={
                    "visit_id": vid,
                    "so_sua_id": sid,
                    "order_id": so["service_order_id"],
                    "luot_phi_kham_id": so["luot_phi_kham_id"],
                },
            )
        return {"ok": True, "so_id": sid, "visit_id": vid}

    async def _dat_lai_chi_dinh(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        so: asyncpg.Record,
        ly: str | None,
    ) -> dict[str, Any]:
        cid = identity.clinic_id
        oid = so["service_order_id"]
        o = await conn.fetchrow(
            "SELECT id::text, visit_id::text, service_code, service_name,"
            "       exec_status, nguon_lam_them"
            "  FROM service_order WHERE clinic_id = $1::uuid AND id = $2::uuid"
            "   FOR UPDATE",
            cid,
            oid,
        )
        if o is None or o["exec_status"] != "cancelled":
            return {"already": True}
        trung = await conn.fetchval(
            "SELECT service_name FROM service_order WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid AND service_code = $3 AND id <> $4::uuid"
            " AND exec_status NOT IN ('cancelled', 'not_performed', 'draft')"
            " LIMIT 1",
            cid,
            o["visit_id"],
            o["service_code"],
            oid,
        )
        if trung:
            raise LuotKhamConflictError(
                "DA_CO_CHI_DINH_MOI",
                f"Lượt đã có chỉ định “{trung}” còn hiệu lực (chỉ định lại sau khi"
                " bỏ) — không đặt lại lần nữa.",
            )
        ct = so["chi_tiet"]
        ct = json.loads(ct) if isinstance(ct, str) else dict(ct or {})
        truoc = ct.get("truoc") or {}
        try:
            await conn.execute(
                """
                UPDATE service_order
                   SET exec_status = 'authorized',
                       execution_status = CASE WHEN $3::text IS NULL THEN NULL
                                               ELSE 'PENDING' END,
                       execution_revision = execution_revision + 1,
                       routing_status = CASE WHEN $4::text IS NULL THEN NULL
                                             ELSE 'UNASSIGNED' END,
                       room_id = NULL, assigned_by = NULL, assigned_at = NULL,
                       routing_revision = routing_revision + 1,
                       selection_status = coalesce($5::text, selection_status),
                       authorized_by = coalesce(authorized_by, recorded_by),
                       authorized_at = coalesce(authorized_at, created_at),
                       cancelled_by = NULL, cancel_reason = NULL,
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                oid,
                truoc.get("execution_status"),
                truoc.get("routing_status"),
                truoc.get("selection_status"),
            )
        except asyncpg.UniqueViolationError:
            raise LuotKhamConflictError(
                "DA_CO_CHI_DINH_MOI",
                f"Dịch vụ “{o['service_name']}” đã được tick lại ở quầy — không đặt"
                " lại lần nữa.",
            ) from None
        await emit_event(
            conn,
            ten="service_order.restored",
            clinic_id=cid,
            aggregate_id=oid,
            so_ke_tiep=True,
            payload=ChiDinhDatLai(
                visit_id=o["visit_id"],
                service_order_id=oid,
                service_code=o["service_code"],
                service_name=o["service_name"],
                so_sua_id=so["id"],
                ly_do=ly,
            ),
            boi=nguoi(identity),
            correlation_id=o["visit_id"],
        )
        return {"ok": True}

    async def _tick_lai_kham(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        so: asyncpg.Record,
        chan_trung: Any,
    ) -> dict[str, Any]:
        cid = identity.clinic_id
        k = await conn.fetchrow(
            "SELECT k.visit_id::text, k.service_price_id::text, sp.name,"
            "       sp.unit_price"
            "  FROM luot_phi_kham k JOIN service_price sp ON sp.id = k.service_price_id"
            " WHERE k.clinic_id = $1::uuid AND k.id = $2::uuid",
            cid,
            so["luot_phi_kham_id"],
        )
        if k is None:
            return {"already": True}
        song = await conn.fetchval(
            "SELECT 1 FROM luot_phi_kham WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid AND service_price_id = $3::uuid"
            " AND bo_luc IS NULL",
            cid,
            k["visit_id"],
            k["service_price_id"],
        )
        if song:
            return {"already": True}
        await chan_trung(conn, cid, k["visit_id"], id_tick=[k["service_price_id"]])
        await conn.execute(
            "INSERT INTO luot_phi_kham"
            " (clinic_id, visit_id, service_price_id, chon_boi)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid)",
            cid,
            k["visit_id"],
            k["service_price_id"],
            identity.staff_id,
        )
        await emit_event(
            conn,
            ten="visit.exam_service_changed",
            clinic_id=cid,
            aggregate_id=k["visit_id"],
            so_ke_tiep=True,
            payload=DichVuKhamDaDoi(
                visit_id=k["visit_id"],
                them=[
                    {
                        "id": k["service_price_id"],
                        "ten": k["name"],
                        "gia": int(k["unit_price"])
                        if k["unit_price"] is not None
                        else None,
                    }
                ],
            ),
            boi=nguoi(identity),
            correlation_id=k["visit_id"],
        )
        return {"ok": True}


__all__ = [
    "GOP_PHUT",
    "NHAN_HANH_DONG",
    "NHAN_NHOM",
    "SoSuaChiDinhService",
    "ThayDoiThuoc",
    "bao_bac_si_chinh",
    "cau_so",
    "chan_ho_so_cu",
    "dat_ngu_canh",
    "doc_don_de_so",
    "doc_so",
    "dong_bo_moi_nhat",
    "dong_so",
    "ghi_so_thuoc",
    "la_ho_so_cu",
    "so_sanh_don",
]
