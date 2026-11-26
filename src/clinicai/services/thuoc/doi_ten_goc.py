"""Đổi TÊN đơn vị gốc của một thuốc khi số tồn giữ nguyên nghĩa (kế hoạch
docs/KE-HOACH-DON-VI-ME-CON-CACH-DUNG.md mục 15, 16 dòng PR C).

Ca thật: Aktiv gốc "hộp 30 viên", Ecanix gốc "hộp 60 viên" — sau lần nhập sai (câu
hỏi cũ "1 hộp = ? hộp 30 viên") số tồn thực chất đang đếm VIÊN. Tuyền chốt 26/11:
thuốc đang đếm theo gì giữ nguyên, KHÔNG chuyển tồn hộp→viên hàng loạt. Nên ở đây
chỉ đổi CHỮ, trong MỘT giao dịch, có khoá thuốc:
  · `drug_catalog.don_vi_ban` "hộp 60 viên" → "viên"; chữ đơn vị trên các lô theo gốc;
  · đơn vị MẸ "hộp" = 60 viên mang giá gốc cũ (550.000đ là giá hộp), đặt làm mặc định
    khi kê — dòng đơn để trống vẫn là 1 hộp (luật PR A);
  · giá gốc (viên): người đổi nhập, hoặc để trống = chia từ giá hộp (`thuoc.gia_dong`
    ưu tiên giá gốc đã khai, nên giữ 550.000đ cho 1 viên là sai — phải sửa cùng lúc);
  · dòng đơn cũ ghi chữ cũ: nếu bảng đơn vị mới không tự nhận "hộp 60 viên" là mẹ thì
    thêm chữ cũ làm TÊN GỌI KHÁC của mẹ (tắt bán, cùng hệ số, cùng giá) — dòng cũ vẫn
    khớp 1 hộp. Cách an toàn: không sửa dòng đơn nào.
Từ chối khi: chữ mới trùng chữ cũ / có chữ số / trùng đơn vị đã khai, còn dòng chờ gán
lô (số chờ tính theo gốc cũ), đơn vị mẹ đã khai với hệ số khác.
Hoàn tác = lệnh bù đúng bước này (`hoan_tac_doi_ten_goc`), có sự kiện riêng.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import DonViGocDaDoiTen
from clinicai.events.emit import emit_event, nguoi
from clinicai.services.don_vi_thuoc import (
    BangDonVi,
    DonViBan,
    _gia,
    chuan,
    doc_bang,
    doi_quyen_sua_gia,
    so_dep,
    tien,
)
from clinicai.services.thuoc.don_vi_ke import kiem_ten_don_vi
from clinicai.services.thuoc.don_vi_nhap import doc_he_so

DOI_TEN = "drug_unit.base_renamed"
HOAN_TAC = "drug_unit.base_rename_undone"


def _doc_ten_don_vi(v: Any, o: str) -> str:
    ten = " ".join(str(v or "").split())
    if not ten:
        raise ValidationError(f"Nhập {o}.")
    if len(ten) > 50:
        raise ValidationError(f"{o.capitalize()} quá dài (tối đa 50 ký tự).")
    kiem_ten_don_vi(ten)
    return ten


async def _khoa_dong_thuoc(conn: asyncpg.Connection, clinic_id: str, thuoc: str) -> Any:
    r = await conn.fetchrow(
        "SELECT don_vi_ban, unit_price FROM public.drug_catalog"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
        clinic_id,
        thuoc,
    )
    if r is None:
        raise NotFoundError("Không tìm thấy thuốc này trong danh mục.")
    return r


async def _kiem_khong_cho_gan(
    conn: asyncpg.Connection, clinic_id: str, thuoc: str
) -> None:
    n = await conn.fetchval(
        "SELECT count(*) FROM public.thuoc_giao_chua_gan_lo WHERE clinic_id = $1::uuid"
        " AND drug_catalog_id = $2::uuid AND drug_batch_id IS NULL AND huy_luc IS NULL",
        clinic_id,
        thuoc,
    )
    if n:
        raise ConflictError(
            f"Thuốc còn {n} dòng đã giao chờ gán lô (số chờ tính theo đơn vị gốc "
            "hiện tại) — gán lô hoặc huỷ chờ ở Kho thuốc trước, rồi đổi tên."
        )


async def _doi_chu_lo(
    conn: asyncpg.Connection, clinic_id: str, thuoc: str, bang: BangDonVi, moi: str
) -> dict[str, str]:
    """Lô tính theo gốc cũ (cả cách viết khác: "hộp" của gốc "hộp 60 viên") → chữ
    mới. Số tồn không đổi. Trả id lô → chữ cũ để hoàn tác."""
    lo = await conn.fetch(
        "SELECT id::text AS id, unit FROM public.drug_batch"
        " WHERE clinic_id = $1::uuid AND drug_catalog_id = $2::uuid",
        clinic_id,
        thuoc,
    )
    cu = {r["id"]: r["unit"] for r in lo if r["unit"] and bang.la_goc(r["unit"])}
    if cu:
        await conn.execute(
            "UPDATE public.drug_batch SET unit = $3"
            " WHERE clinic_id = $1::uuid AND id = ANY($2::uuid[])",
            clinic_id,
            list(cu),
            moi,
        )
    return cu


async def _ghi_me(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    thuoc: str,
    me: str,
    vals: tuple[Decimal, Decimal | None, bool, bool],
) -> None:
    """Ghi dòng đơn vị `me` = (hệ số, giá, đang bán, mặc định kê)."""
    await conn.execute(
        """
        INSERT INTO public.thuoc_quy_doi
            (clinic_id, drug_catalog_id, don_vi, he_so, gia, dang_ban, mac_dinh_ke,
             cap_nhat_boi)
        VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8::uuid)
        ON CONFLICT (clinic_id, drug_catalog_id, don_vi)
        DO UPDATE SET he_so = EXCLUDED.he_so, gia = EXCLUDED.gia,
                      dang_ban = EXCLUDED.dang_ban, mac_dinh_ke = EXCLUDED.mac_dinh_ke,
                      cap_nhat_boi = EXCLUDED.cap_nhat_boi, cap_nhat_luc = now()
        """,
        identity.clinic_id,
        thuoc,
        chuan(me),
        *vals,
        identity.staff_id,
    )


async def _bo_co_me(conn: asyncpg.Connection, clinic_id: str, thuoc: str) -> None:
    await conn.execute(
        "UPDATE public.thuoc_quy_doi SET mac_dinh_ke = false WHERE clinic_id = $1::uuid"
        " AND drug_catalog_id = $2::uuid AND mac_dinh_ke",
        clinic_id,
        thuoc,
    )


def _kiem_dau_vao(
    cu: str, gia_cu: Decimal | None, ten: str, me: str, hs: Decimal, le: Decimal | None
) -> None:
    if not chuan(cu):
        raise ValidationError("Thuốc chưa khai đơn vị gốc — khai ở ô Đơn vị gốc.")
    if chuan(ten) == chuan(cu):
        raise ValidationError(f"Tên mới “{ten}” giống tên đang dùng.")
    if chuan(me) == chuan(ten):
        raise ValidationError("Đơn vị lớn phải khác đơn vị kho đếm (vd hộp ≠ viên).")
    if hs <= 1:
        raise ValidationError(f"1 {me} phải có nhiều hơn 1 {ten}.")
    if gia_cu is None:
        raise ValidationError("Thuốc chưa có giá — khai giá trước rồi đổi tên đơn vị.")
    if le is not None and le > gia_cu:
        raise ValidationError(
            f"Giá 1 {ten} ({tien(le)}) cao hơn giá 1 {me} ({tien(gia_cu)}) — "
            f"giá cũ {tien(gia_cu)} là giá {me}; nhập giá {ten} hoặc để trống."
        )


def _kiem_bang(
    bang: BangDonVi, cu: str, ten: str, me: str, hs: Decimal
) -> DonViBan | None:
    """Chữ mới chưa là đơn vị khai thêm; mẹ đã khai thì phải cùng hệ số. Trả dòng
    mẹ đang có (None = chưa có)."""
    if chuan(ten) in bang.dong:
        raise ConflictError(
            f"Thuốc đã có đơn vị “{ten}” khai thêm — chọn tên khác, hoặc tắt đơn vị đó."
        )
    truoc = bang.dong.get(chuan(me))
    if truoc is not None and truoc.he_so != hs:
        raise ConflictError(
            f"Đã khai 1 {me} có {so_dep(truoc.he_so)} {cu}, khác {so_dep(hs)} vừa "
            "nhập — sửa ở Đơn vị bán thêm trước."
        )
    return truoc


async def _dat_me_moi(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    thuoc: str,
    v: tuple[str, str, Decimal, Decimal | None],
) -> bool:
    """Mẹ mới đang bán + mặc định kê; chữ gốc cũ thành tên gọi khác của mẹ nếu bảng
    mới không tự nhận ra. Trả có thêm tên gọi khác không."""
    cu, me, hs, gia_me = v
    await _bo_co_me(conn, identity.clinic_id, thuoc)
    await _ghi_me(conn, identity, thuoc, me, (hs, gia_me, True, True))
    sau = (await doc_bang(conn, identity.clinic_id, [thuoc]))[thuoc]
    if sau.he_so(cu) == hs:
        return False
    await _ghi_me(conn, identity, thuoc, cu, (hs, gia_me, False, False))
    return True


async def doi_ten_goc(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    thuoc: str,
    ten_moi: Any,
    don_vi_me: Any,
    he_so_me: Any,
    gia_goc_moi: Any = None,
    ly_do: str | None = None,
) -> dict[str, Any]:
    """Đổi chữ đơn vị gốc "hộp 60 viên" → "viên", khai mẹ "hộp" = 60 (xem đầu tệp)."""
    ten = _doc_ten_don_vi(ten_moi, "tên đơn vị kho đếm (vd viên)")
    me = _doc_ten_don_vi(don_vi_me, "tên đơn vị lớn (vd hộp)")
    hs = doc_he_so(he_so_me)
    le = _gia(gia_goc_moi, ten)
    async with pool.acquire() as conn, conn.transaction():
        await doi_quyen_sua_gia(conn, identity)
        r = await _khoa_dong_thuoc(conn, identity.clinic_id, thuoc)
        cu = (r["don_vi_ban"] or "").strip()
        gia_cu = None if r["unit_price"] is None else Decimal(str(r["unit_price"]))
        _kiem_dau_vao(cu, gia_cu, ten, me, hs, le)
        await _kiem_khong_cho_gan(conn, identity.clinic_id, thuoc)
        bang = (await doc_bang(conn, identity.clinic_id, [thuoc]))[thuoc]
        truoc = _kiem_bang(bang, cu, ten, me, hs)
        lo = await _doi_chu_lo(conn, identity.clinic_id, thuoc, bang, ten)
        await conn.execute(
            "UPDATE public.drug_catalog SET don_vi_ban = $3, unit_price = $4"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid",
            identity.clinic_id,
            thuoc,
            ten,
            le,
        )
        gia_me = truoc.gia if truoc is not None and truoc.gia is not None else gia_cu
        bi_danh = await _dat_me_moi(conn, identity, thuoc, (cu, me, hs, gia_me))
        p = DonViGocDaDoiTen(
            drug_catalog_id=thuoc,
            ten_cu=cu,
            ten_moi=ten,
            don_vi_me=chuan(me),
            he_so_me=so_dep(hs),
            gia_goc_cu=None if gia_cu is None else int(gia_cu),
            gia_goc_moi=None if le is None else int(le),
            me_truoc=None
            if truoc is None
            else {
                "he_so": so_dep(truoc.he_so),
                "gia": None if truoc.gia is None else int(truoc.gia),
                "dang_ban": truoc.dang_ban,
            },
            me_cu=bang.me,
            bi_danh=bi_danh,
            don_vi_lo=lo,
            ly_do=(ly_do or "").strip() or None,
        )
        su_kien = await emit_event(
            conn,
            ten="drug_unit.base_renamed",
            clinic_id=identity.clinic_id,
            aggregate_id=thuoc,
            payload=p,
            boi=nguoi(identity),
        )
    cau = (
        f"Đã đổi: kho đếm theo “{ten}”, 1 {me} có {so_dep(hs)} {ten} giá "
        f"{tien(gia_me) if gia_me is not None else '—'}; {len(lo)} lô đổi chữ, số tồn "
        "giữ nguyên."
    )
    return {
        "ok": True,
        "su_kien_id": su_kien,
        "so_lo": len(lo),
        "bi_danh": bi_danh,
        "cau": cau,
    }


async def hoan_tac_doi_ten_goc(
    pool: asyncpg.Pool, *, identity: StaffIdentity, su_kien_id: str, ly_do: str
) -> dict[str, Any]:
    """Lệnh bù của `doi_ten_goc`: chữ gốc, giá gốc, chữ từng lô, dòng mẹ về như
    trước. Chỉ khi chưa ai đổi tên gốc lần nữa và không còn dòng chờ gán lô."""
    if not (ly_do or "").strip():
        raise ValidationError("Nhập lý do hoàn tác.")
    async with pool.acquire() as conn, conn.transaction():
        await doi_quyen_sua_gia(conn, identity)
        goc = await conn.fetchrow(
            "SELECT payload, aggregate_id::text AS thuoc FROM public.domain_event"
            " WHERE event_id = $1::uuid AND clinic_id = $2::uuid AND event_type = $3",
            su_kien_id,
            identity.clinic_id,
            DOI_TEN,
        )
        if goc is None:
            raise NotFoundError("Không tìm thấy lần đổi tên đơn vị này.")
        raw = goc["payload"]
        p = DonViGocDaDoiTen.model_validate(
            json.loads(raw) if isinstance(raw, str) else raw
        )
        thuoc = goc["thuoc"]
        r = await _khoa_dong_thuoc(conn, identity.clinic_id, thuoc)
        if await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM public.domain_event"
            " WHERE clinic_id = $1::uuid AND causation_id = $2::uuid"
            " AND event_type = $3)",
            identity.clinic_id,
            su_kien_id,
            HOAN_TAC,
        ):
            raise ConflictError("Lần đổi tên này đã được hoàn tác.")
        if chuan(r["don_vi_ban"]) != chuan(p.ten_moi):
            raise ConflictError(
                f"Đơn vị gốc giờ là “{r['don_vi_ban']}”, không còn là “{p.ten_moi}” — "
                "đã đổi tiếp sau lần này, không hoàn tác được."
            )
        await _kiem_khong_cho_gan(conn, identity.clinic_id, thuoc)
        await _dao_lai(conn, identity, thuoc, p)
        await emit_event(
            conn,
            ten="drug_unit.base_rename_undone",
            clinic_id=identity.clinic_id,
            aggregate_id=thuoc,
            payload=p.model_copy(update={"ly_do": ly_do.strip()}),
            boi=nguoi(identity),
            causation_id=su_kien_id,
        )
    return {
        "ok": True,
        "ten_goc": p.ten_cu,
        "cau": f"Đã hoàn tác: kho đếm lại theo “{p.ten_cu}” như trước.",
    }


async def _dao_lai(
    conn: asyncpg.Connection, identity: StaffIdentity, thuoc: str, p: DonViGocDaDoiTen
) -> None:
    ck = identity.clinic_id
    for lo, chu in p.don_vi_lo.items():
        await conn.execute(
            "UPDATE public.drug_batch SET unit = $3 WHERE clinic_id = $1::uuid"
            " AND id = $2::uuid",
            ck,
            lo,
            chu,
        )
    # Lô nhập SAU lần đổi (đếm theo chữ mới) cũng về chữ cũ — cùng nghĩa số.
    await conn.execute(
        "UPDATE public.drug_batch SET unit = $3 WHERE clinic_id = $1::uuid"
        " AND drug_catalog_id = $2::uuid AND public.chuan_don_vi(unit) = $4",
        ck,
        thuoc,
        p.ten_cu,
        chuan(p.ten_moi),
    )
    await conn.execute(
        "UPDATE public.drug_catalog SET don_vi_ban = $3, unit_price = $4"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid",
        ck,
        thuoc,
        p.ten_cu,
        p.gia_goc_cu,
    )
    await _bo_co_me(conn, ck, thuoc)
    xoa = [chuan(p.ten_cu)] if p.bi_danh else []
    if p.me_truoc is None:
        xoa.append(p.don_vi_me)
    else:
        m = p.me_truoc
        gia = None if m["gia"] is None else Decimal(str(m["gia"]))
        vals = (Decimal(str(m["he_so"])), gia, bool(m["dang_ban"]), False)
        await _ghi_me(conn, identity, thuoc, p.don_vi_me, vals)
    if xoa:
        # Dòng do chính lần đổi tạo ra — lệnh bù gỡ nó, không phải sửa quá khứ.
        await conn.execute(
            "DELETE FROM public.thuoc_quy_doi WHERE clinic_id = $1::uuid"
            " AND drug_catalog_id = $2::uuid AND don_vi = ANY($3::text[])",
            ck,
            thuoc,
            xoa,
        )
    if p.me_cu:
        await conn.execute(
            "UPDATE public.thuoc_quy_doi SET mac_dinh_ke = true"
            " WHERE clinic_id = $1::uuid AND drug_catalog_id = $2::uuid"
            " AND don_vi = $3",
            ck,
            thuoc,
            p.me_cu,
        )
