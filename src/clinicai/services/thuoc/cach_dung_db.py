"""Cách dùng có cấu trúc — phần đọc/ghi DB (luật thuần ở `cach_dung.py`).

- `tinh_don`: màn kê đơn gửi các dòng đang mở (chưa cần lưu) → số ngày, ngày hết, gợi
  ý số lượng, câu in, hoặc lý do không tính. Kinh lần cuối + chu kỳ đọc từ phiếu khám
  của lượt (`pk_*`, `sk_*`, `hmvs_w_*`) — bác sĩ nhập tay thì dùng số bác sĩ nhập.
- `chuan_hoa_dong` + `ct_json`: đường LƯU đơn — câu cách dùng của dòng có cấu trúc do
  MÁY sinh (không tin chữ màn gửi), bản chụp cấu trúc ghi vào `prescription`.
- `doc_mac_dinh` / `luu_mac_dinh`: mặc định ở danh mục + "1 [đơn vị kho] có bao nhiêu
  [viên]" (Kho thuốc › Danh mục › Sửa).
"""

from __future__ import annotations

import json
from datetime import date
from fractions import Fraction
from typing import Any

import asyncpg

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import hom_nay_vn
from clinicai.services.don_vi_thuoc import BangDonVi, chuan, doc_bang
from clinicai.services.thuoc.cach_dung import (
    LY_DO_NGOAI_DANH_MUC,
    CachDung,
    cau_cach_dung,
    chua_chon_khoang,
    doc_chu_ky,
    doc_ct,
    doc_ngay_kinh,
    lieu_ngay,
    moc_chu_ky,
    tinh_dong,
)
from clinicai.services.thuoc.tach_cau import de_xuat_cach_dung

#: Cặp ô (kinh lần cuối, chu kỳ) của các phiếu có hỏi kinh nguyệt.
O_KINH = (
    ("pk_lmp", "pk_cycle"),
    ("sk_lmp", "sk_cycle"),
    ("hmvs_w_lmp", "hmvs_w_cycle"),
)
NOI = " — "


def _gia_tri_o_phieu(o: Any) -> Any:
    """Ô phiếu lưu dạng {gia_tri, nguon}; bản cũ có thể là giá trị trần."""
    return o.get("gia_tri") if isinstance(o, dict) else o


def lieu_moi_don_vi_kho(ct: CachDung, goc: str, so_lieu: Any) -> Fraction | None:
    """1 đơn vị kho = bao nhiêu đơn vị liều. Cùng tên ("viên"/"viên") = 1; khác thì
    phải khai ở danh mục (`so_lieu_moi_don_vi_goc`) — không đoán từ tên thuốc."""
    if chuan(goc) and chuan(goc) == chuan(ct.don_vi_lieu):
        return Fraction(1)
    return Fraction(str(so_lieu)) if so_lieu is not None else None


def he_so_dong(bang: BangDonVi, don_vi: str | None) -> Fraction | None:
    """Đổi đơn vị dòng về gốc, dùng mặc định kê khi dòng để trống."""
    dv = bang.don_vi_dong(don_vi)
    if not dv:
        return Fraction(1)
    h = bang.he_so(dv)
    return Fraction(h) if h is not None else None


async def _kinh_cua_luot(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> dict[str, str | None]:
    """Chữ hai ô kinh lần cuối + chu kỳ ở phiếu sửa gần nhất có ghi (chưa đọc ngày)."""
    rows = await conn.fetch(
        "SELECT du_lieu FROM public.phieu_kham_luot"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid ORDER BY sua_luc DESC",
        clinic_id,
        visit_id,
    )
    for r in rows:
        dl = r["du_lieu"]
        dl = json.loads(dl) if isinstance(dl, str) else (dl or {})
        for o_lmp, o_ck in O_KINH:
            lmp = _gia_tri_o_phieu(dl.get(o_lmp))
            if lmp not in (None, ""):
                ck = _gia_tri_o_phieu(dl.get(o_ck))
                return {
                    "kinh_lan_cuoi": str(lmp),
                    "chu_ky": None if ck is None else str(ck),
                }
    return {"kinh_lan_cuoi": None, "chu_ky": None}


async def _ngay_ke(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str | None
) -> date:
    """Ngày kê = ngày của lượt (giờ VN); không có lượt thì hôm nay."""
    if visit_id:
        d = await conn.fetchval(
            "SELECT (coalesce(checked_in_at, created_at)"
            "        AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
            "  FROM public.visit WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
            clinic_id,
            visit_id,
        )
        if d is not None:
            return d  # type: ignore[no-any-return]
    return hom_nay_vn()


async def tinh_don(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    visit_id: str | None,
    dong: list[dict[str, Any]],
    kinh_lan_cuoi: str | None,
    chu_ky: str | None,
) -> dict[str, Any]:
    from clinicai.services.phieu_kham_service import kiem_quyen_core

    cid = identity.clinic_id
    async with pool.acquire() as conn:
        # Đọc phiếu của lượt (kinh lần cuối) = quyền xem phiếu khám.
        await kiem_quyen_core(conn, identity, "doc_phieu")
        ngay_ke = await _ngay_ke(conn, cid, visit_id)
        tu_phieu = (
            await _kinh_cua_luot(conn, cid, visit_id)
            if visit_id
            else {"kinh_lan_cuoi": None, "chu_ky": None}
        )
        ids = [str(d["drug_catalog_id"]) for d in dong if d.get("drug_catalog_id")]
        bang = await doc_bang(conn, cid, ids)
        danh_muc = {
            r["id"]: r
            for r in await conn.fetch(
                "SELECT id::text, so_lieu_moi_don_vi_goc, cach_dung_ct"
                " FROM public.drug_catalog"
                " WHERE clinic_id = $1::uuid AND id = ANY($2::uuid[])",
                cid,
                sorted(set(ids)),
            )
        }
    go_tay = bool((kinh_lan_cuoi or "").strip() or (chu_ky or "").strip())
    kinh_chu = (
        {"kinh_lan_cuoi": kinh_lan_cuoi, "chu_ky": chu_ky} if go_tay else tu_phieu
    )
    lmp = doc_ngay_kinh(kinh_chu["kinh_lan_cuoi"], ngay_ke)
    ck = doc_chu_ky(kinh_chu["chu_ky"])
    kinh = (lmp, ck) if lmp is not None and ck is not None else None

    ra = []
    for d in dong:
        ma = str(d.get("drug_catalog_id") or "")
        chu = str(d.get("chu") or "")
        # Bác sĩ không khai cấu trúc (Tuyền 26/11): đọc chữ cách dùng của dòng (mặc định
        # = chữ danh mục); đọc không ra thì lấy cấu trúc kho khai ở Danh mục.
        ct: CachDung = de_xuat_cach_dung(chu)
        if ct.kieu == "chu" and ma in danh_muc:
            ct = doc_ct(danh_muc[ma]["cach_dung_ct"]) or ct
        cau = chu
        if not ma or ma not in bang:
            kq = tinh_dong(
                None,
                so_luong=None,
                he_so=None,
                lieu_moi_kho=None,
                don_vi_kho="",
                ngay_ke=ngay_ke,
            )
            ra.append({**kq, "cau": cau, "ly_do": LY_DO_NGOAI_DANH_MUC})
            continue
        b = bang[ma]
        kq = tinh_dong(
            ct,
            so_luong=d.get("so_luong"),
            he_so=he_so_dong(b, d.get("don_vi")),
            lieu_moi_kho=lieu_moi_don_vi_kho(
                ct, b.goc, danh_muc[ma]["so_lieu_moi_don_vi_goc"]
            )
            if ct and ma in danh_muc
            else None,
            don_vi_kho=b.goc,
            ngay_ke=ngay_ke,
            kinh=kinh,
        )
        ra.append({**kq, "cau": cau})
    return {
        "ngay_ke": ngay_ke,
        "kinh": {
            **kinh_chu,
            "nguon": "go_tay"
            if go_tay
            else ("phieu" if tu_phieu["kinh_lan_cuoi"] else None),
            "doc_duoc": kinh is not None,
        },
        "dong": ra,
    }


def chuan_hoa_dong(d: dict[str, Any]) -> dict[str, Any]:
    """Đường LƯU: dòng có cấu trúc (không phải "chỉ chữ") → chữ cách dùng do máy sinh.

    `dosage` = "<đường dùng> — <câu>" như cũ (bản in, quầy, đơn quốc gia đọc chữ này).
    Dòng không gửi cấu trúc (màn cũ, quầy) đi nguyên như trước."""
    ct = d.get("cach_dung_ct")
    if isinstance(ct, dict):
        ct = CachDung.model_validate(ct)
    if not isinstance(ct, CachDung):
        return {**d, "cach_dung_ct": None}
    out = {**d, "cach_dung_ct": ct.model_dump(mode="json")}
    if ct.kieu == "chu":
        return out
    if not d.get("drug_catalog_id"):
        raise ValidationError(LY_DO_NGOAI_DANH_MUC)
    # Chưa điền đủ: vẫn lưu (màn tự lưu khi gõ — chặn thì mất cả đơn nháp), giữ chữ
    # bác sĩ đã gõ, không sinh câu thiếu đè lên. Màn tự hiện lý do "chưa tính được".
    if (
        chua_chon_khoang(ct)
        or lieu_ngay(ct) is None
        or (ct.kieu == "chu_ky" and moc_chu_ky(ct) is None)
        or not ct.don_vi_lieu.strip()
    ):
        return out
    duong = str(d.get("duong_dung") or "").strip()
    out["dosage"] = NOI.join(x for x in (duong, cau_cach_dung(ct)) if x)
    return out


def ct_ra(v: Any) -> dict[str, Any] | None:
    """jsonb đã lưu → dict trả cho màn (hỏng/rỗng → None)."""
    ct = doc_ct(v)
    return ct.model_dump(mode="json") if ct else None


def ct_json(item: dict[str, Any]) -> str | None:
    """Bản chụp cấu trúc của một dòng đơn để ghi cột jsonb (None = không có)."""
    ct = item.get("cach_dung_ct")
    return json.dumps(ct, ensure_ascii=False) if isinstance(ct, dict) else None


async def gan_mac_dinh_ke_don(
    conn: asyncpg.Connection, clinic_id: str, mau: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Ô chọn thuốc ở màn kê: gắn cách dùng mặc định có cấu trúc của danh mục."""
    ids = sorted({str(m["drug_catalog_id"]) for m in mau if m.get("drug_catalog_id")})
    rows = await conn.fetch(
        "SELECT id::text, cach_dung_ct FROM public.drug_catalog"
        " WHERE clinic_id = $1::uuid AND id = ANY($2::uuid[])"
        "   AND cach_dung_ct IS NOT NULL",
        clinic_id,
        ids,
    )
    ct = {r["id"]: doc_ct(r["cach_dung_ct"]) for r in rows}
    for m in mau:
        c = ct.get(str(m.get("drug_catalog_id") or ""))
        m["cach_dung_ct"] = c.model_dump(mode="json") if c else None
    return mau


async def doc_mac_dinh(
    pool: asyncpg.Pool, *, identity: StaffIdentity, thuoc_id: str
) -> dict[str, Any]:
    async with pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT id::text, name_raw, don_vi_ban, cach_dung, cach_dung_ct,"
            "       so_lieu_moi_don_vi_goc"
            "  FROM public.drug_catalog WHERE clinic_id = $1::uuid AND id = $2::uuid",
            identity.clinic_id,
            thuoc_id,
        )
    if r is None:
        raise ValidationError("Không tìm thấy thuốc trong danh mục.")
    ct = doc_ct(r["cach_dung_ct"])
    goc = (r["don_vi_ban"] or "").strip()
    return {
        "id": r["id"],
        "don_vi_goc": goc,
        # Kho đếm đúng đơn vị liều ("viên"/"viên") thì không cần khai — là 1.
        "can_khai_so_lieu": lieu_moi_don_vi_kho(ct or CachDung(), goc, None) is None,
        "cach_dung": r["cach_dung"] or "",
        "ct": ct,
        "so_lieu_moi_don_vi_goc": r["so_lieu_moi_don_vi_goc"],
        "cau": cau_cach_dung(ct, r["cach_dung"] or "") if ct else None,
    }


async def luu_mac_dinh(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    thuoc_id: str,
    ct: CachDung | None,
    so_lieu: Any,
) -> dict[str, Any]:
    """Ghi mặc định (không đụng chữ `cach_dung` cũ). Có nhật ký: trước / sau."""
    from clinicai.services.pharmacy_service import ghi_nhat_ky

    async with pool.acquire() as conn, conn.transaction():
        cu = await conn.fetchrow(
            "SELECT cach_dung_ct::text AS ct, so_lieu_moi_don_vi_goc AS so"
            "  FROM public.drug_catalog WHERE clinic_id = $1::uuid AND id = $2::uuid"
            "   FOR UPDATE",
            identity.clinic_id,
            thuoc_id,
        )
        if cu is None:
            raise ValidationError("Không tìm thấy thuốc trong danh mục.")
        moi = json.dumps(ct.model_dump(mode="json"), ensure_ascii=False) if ct else None
        await conn.execute(
            "UPDATE public.drug_catalog SET cach_dung_ct = $3::jsonb,"
            " so_lieu_moi_don_vi_goc = $4"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid",
            identity.clinic_id,
            thuoc_id,
            moi,
            so_lieu,
        )
        await ghi_nhat_ky(
            conn,
            identity=identity,
            event_type="pharmacy.drug_usage_set",
            aggregate_type="drug_catalog",
            aggregate_id=thuoc_id,
            payload={
                "truoc": {
                    "ct": json.loads(cu["ct"]) if cu["ct"] else None,
                    "so_lieu": str(cu["so"]) if cu["so"] is not None else None,
                },
                "sau": {
                    "ct": json.loads(moi) if moi else None,
                    "so_lieu": str(so_lieu) if so_lieu is not None else None,
                },
            },
        )
    return await doc_mac_dinh(pool, identity=identity, thuoc_id=thuoc_id)


__all__ = [
    "chuan_hoa_dong",
    "ct_json",
    "doc_mac_dinh",
    "gan_mac_dinh_ke_don",
    "he_so_dong",
    "lieu_moi_don_vi_kho",
    "luu_mac_dinh",
    "tinh_don",
]
