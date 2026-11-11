"""Xét lại thư Gmail đã cất Lưu trữ vì "không xác thực" — Gmail G6 (11/11/2026).

Vì sao có: luật xác thực G3 chỉ nhận DKIM / DMARC đúng miền; HighDetect (lab máu) gửi
qua Google Workspace không DKIM riêng, không DMARC ⇒ thư thật bị xếp oan `LUU_TRU /
KHONG_XAC_THUC` trước khi G6 nhận SPF khớp miền. Máy KHÔNG nạp lại thư đã có (khoá
`(file_id, md5)`), nên các dòng đó phải được xét lại một lần.

Làm gì: mỗi thư còn `LUU_TRU / KHONG_XAC_THUC` của đối tác đang có email ⇒ đọc lại
header từ Gmail (chỉ đọc), người gửi phải đúng email đối tác, chạy LẠI đúng đường quyết
của lúc nạp (`gmail.muc_ca_thu`) trên byte PDF đã lưu ⇒ cập nhật lý do / gợi ý của dòng
(chỉ khi dòng vẫn ở đúng trạng thái đó), quyết "tự ghép" ⇒ `gmail_ghep.gan_tu_dong`
(có khoá như Gán tay). Vẫn không xác thực ⇒ để nguyên. Gọi lại an toàn.

Chạy (Tuyền, trên VPS): `docker exec clinicai_prod-drive-xn-1 python -m
clinicai.services.xet_nghiem.gmail_xet_lai` — in con số, không in dữ liệu khách.
"""

from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from typing import Any, Final

import asyncpg
import httpx
import structlog

from clinicai.core.tran import canh_bao_neu_day
from clinicai.services.xet_nghiem import gmail, gmail_api, gmail_ghep, gmail_luu

logger = structlog.get_logger()

TRAN: Final = 2000

_DONG_SQL = """
SELECT t.id::text AS id, t.doi_tac_id::text AS dt, t.email_message_id AS mid,
       t.file_id, t.khoa, t.vi_tri, d.email_gui_ket_qua AS email
  FROM drive_tep t
  JOIN doi_tac d ON d.id = t.doi_tac_id AND d.clinic_id = t.clinic_id
 WHERE t.clinic_id = $1::uuid AND t.nguon = 'GMAIL'
   AND t.ly_do_cho = 'LUU_TRU' AND t.luu_tru_vi_sao = 'KHONG_XAC_THUC'
   AND t.tep_ket_qua_id IS NULL AND t.tu_choi_luc IS NULL
   AND d.email_gui_ket_qua IS NOT NULL AND d.ngung_luc IS NULL
 ORDER BY t.email_nhan_luc, t.id
 LIMIT 2000
"""

#: Chỉ dòng VẪN ở "Lưu trữ / không xác thực" (không đè người / lượt khác đã xử lý).
_CAP_NHAT_SQL = """
UPDATE drive_tep
   SET ly_do_cho = $3, luu_tru_vi_sao = $4, goi_y_order_id = $5::uuid,
       goi_y_clinic_patient_id = coalesce($6::uuid, goi_y_clinic_patient_id)
 WHERE clinic_id = $1::uuid AND id = $2::uuid
   AND ly_do_cho = 'LUU_TRU' AND luu_tru_vi_sao = 'KHONG_XAC_THUC'
   AND tep_ket_qua_id IS NULL AND tu_choi_luc IS NULL
"""


def _part_id(file_id: str, mid: str) -> str | None:
    """`gmail:<mid>:<part_id>` (gmail_luu) ⇒ part_id. Khác khuôn ⇒ None."""
    dau = f"gmail:{mid}:"
    return file_id[len(dau) :] if file_id.startswith(dau) else None


async def xet_lai(
    pool: asyncpg.Pool, kh: httpx.AsyncClient, cid: str
) -> dict[str, int]:
    rows = await pool.fetch(_DONG_SQL, cid)
    canh_bao_neu_day("drive_tep", len(rows), TRAN, clinic_id=cid)
    theo_thu: dict[str, list[asyncpg.Record]] = defaultdict(list)
    for r in rows:
        theo_thu[r["mid"]].append(r)
    dem: Counter[str] = Counter(dong=len(rows))
    for mid, dongs in theo_thu.items():
        try:
            await _mot_thu(pool, kh, cid, mid, dongs, dem)
        except gmail_api.GmailError as e:
            dem["loi_gmail"] += len(dongs)
            logger.warning("gmail_xet_lai_loi", message_id=mid, cau=str(e)[:200])
    return dict(dem)


async def _mot_thu(
    pool: asyncpg.Pool,
    kh: httpx.AsyncClient,
    cid: str,
    mid: str,
    dongs: list[asyncpg.Record],
    dem: Counter[str],
) -> None:
    thu = await gmail_api.doc_thu(kh, mid)
    if thu is None or thu.tu != dongs[0]["email"]:
        dem["bo_qua"] += len(dongs)  # thư mất / người gửi khác email đối tác
        return
    phan = {p.part_id: p for p in thu.pdf}
    tai: list[tuple[gmail_api.PhanPdf, bytes, str]] = []
    for d in dongs:
        p = phan.get(_part_id(d["file_id"], mid) or "")
        if p is None:
            dem["bo_qua"] += 1
            continue
        tai.append((p, await gmail_luu.doc_het(d["khoa"], d["vi_tri"]), d["id"]))
    muc = await gmail.muc_ca_thu(
        pool, cid, dongs[0]["dt"], thu, [(p, b) for p, b, _ in tai]
    )
    for m, (_, _, dong_id) in zip(muc, tai, strict=True):
        await _ap(pool, cid, dong_id, m, dem)


async def _ap(
    pool: asyncpg.Pool, cid: str, dong_id: str, m: Any, dem: Counter[str]
) -> None:
    q = m.q
    if q.luu_tru_vi_sao == "KHONG_XAC_THUC":
        dem["van_khong_xac_thuc"] += 1
        return
    n = await pool.execute(
        _CAP_NHAT_SQL,
        cid,
        dong_id,
        q.ly_do,
        q.luu_tru_vi_sao,
        q.goi_y_order_id,
        q.goi_y_clinic_patient_id or q.clinic_patient_id,
    )
    if n != "UPDATE 1":
        dem["da_doi"] += 1  # dòng vừa được xử lý ở chỗ khác
        return
    if q.ly_do is None:
        ok = await gmail_ghep.gan_tu_dong(pool, cid, dong_id, q, m.data, m.p.ten)
        dem["tu_gan" if ok else "gan_loi"] += 1
    else:
        dem[
            f"ly_do:{q.ly_do}" + (f"/{q.luu_tru_vi_sao}" if q.luu_tru_vi_sao else "")
        ] += 1


async def _chay() -> None:
    from clinicai.core.database import close_pool, create_pool

    cid = gmail.phong_kham_cua_khoa()
    if not gmail_api.co_cau_hinh() or cid is None:
        print("Chưa bật Gmail (khoá / GMAIL_CLINIC_ID) — không làm gì.")
        return
    pool = await create_pool()
    try:
        async with httpx.AsyncClient(timeout=60) as kh:
            dem = await xet_lai(pool, kh, cid)
    finally:
        await close_pool(pool)
    print(
        "Xét lại thư 'không xác thực':",
        " · ".join(f"{k} {v}" for k, v in sorted(dem.items())),
    )


if __name__ == "__main__":
    asyncio.run(_chay())
