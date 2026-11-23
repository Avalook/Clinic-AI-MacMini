"""Đơn thuốc của ClinicAI → gói đơn chuẩn (`GoiDon`) để gửi hệ thống quốc gia.

CHỈ ĐỌC. Đơn của một lượt = các dòng `prescription` còn hiệu lực
(`removed_at IS NULL`) do BÁC SĨ kê (`nguon = 'BAC_SI'`) — dòng quầy bán thêm
(`QUAY`) không phải đơn kê. Số lượng là số trên đơn hiện hành (kể cả quầy đã điền
khi bác sĩ để trống — C14), không phải số khách mua.

Dùng lại luật sẵn có, không viết bản thứ hai (luật thiết kế 1):
  · chẩn đoán       → `phieu_kham.mang_sang.chan_doan_tu_phieu` (đọc GỘP cả lô
                      cùng thứ tự `tao_luc` như `doc_chan_doan` — tránh N+1)
  · bác sĩ đứng tên → `bac_si_ky.sql_join_bac_si_ky_luot` (luật chốt 19/11: mọi tên
                      "bác sĩ" qua `bac_si_ky.py`; người bấm Hoàn tất nếu là bác sĩ
                      → bác sĩ chính của lượt → bác sĩ lịch hẹn). Người KÊ / nhập
                      dòng thuốc (`created_by`) KHÔNG dùng — TKYK/ĐD nhập hộ.
                      Không ai → None (đơn dừng "thiếu bác sĩ"), không lùi về người bấm.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, replace
from datetime import datetime
from typing import Any

import asyncpg

from clinicai.core.clock import CLINIC_TZ
from clinicai.phieu_kham.mang_sang import chan_doan_tu_phieu
from clinicai.ports.don_thuoc_quoc_gia import BacSiKe, DongThuoc, GoiDon, NguoiBenh
from clinicai.services.bac_si_ky import sql_join_bac_si_ky_luot

_GIOI_TINH = {"Nam": "NAM", "Nữ": "NU"}

_DONG_SQL = """
SELECT p.visit_id::text AS visit_id, p.drug_name_raw, p.quantity, p.quantity_num,
       p.unit, p.dosage_instructions, p.caution,
       c.biet_duoc, c.name_base, c.ma_hang, c.don_vi_ban
  FROM public.prescription p
  LEFT JOIN public.drug_catalog c
    ON c.id = p.drug_catalog_id AND c.clinic_id = p.clinic_id
 WHERE p.clinic_id = $1::uuid AND p.visit_id = ANY($2::uuid[])
   AND p.removed_at IS NULL AND p.nguon = 'BAC_SI'
 ORDER BY p.visit_id, p.created_at, p.id
"""

_LUOT_SQL = f"""
SELECT v.visit_id::text AS visit_id, v.closed_at,
       bsky.id::text AS bs_id, bsky.full_name AS bs_ten, sbs.license_number AS cchn,
       pt.patient_code, pt.full_name, pt.date_of_birth, pt.birth_year, pt.gender,
       pt.national_id_number, pt.address, pt.phone_primary, pt.guardian_name
  FROM public.visit v
  JOIN public.patient pt
    ON pt.clinic_patient_id = v.clinic_patient_id AND pt.clinic_id = v.clinic_id
  {sql_join_bac_si_ky_luot("v", "bsky")}
  LEFT JOIN public.staff sbs ON sbs.id = bsky.id
 WHERE v.clinic_id = $1::uuid AND v.visit_id = ANY($2::uuid[])
"""

_CHAN_DOAN_SQL = """
SELECT visit_id::text AS visit_id, du_lieu FROM public.phieu_kham_luot
 WHERE clinic_id = $1::uuid AND visit_id = ANY($2::uuid[])
 ORDER BY visit_id, tao_luc
"""


async def _chan_doan(
    conn: asyncpg.Connection, clinic_id: str, ids: list[str]
) -> dict[str, str]:
    """Chẩn đoán đầu tiên có chữ của mỗi lượt — cùng luật `doc_chan_doan`, một câu."""
    ra: dict[str, str] = {}
    for r in await conn.fetch(_CHAN_DOAN_SQL, clinic_id, ids):
        if r["visit_id"] in ra:
            continue
        dl = r["du_lieu"]
        cd = chan_doan_tu_phieu(json.loads(dl) if isinstance(dl, str) else dl)
        if cd:
            ra[r["visit_id"]] = cd
    return ra


def _dong_thuoc(r: asyncpg.Record) -> DongThuoc:
    sl = r["quantity_num"]
    return DongThuoc(
        ten_thuoc=(r["drug_name_raw"] or r["name_base"] or "").strip(),
        ma_thuoc=(r["ma_hang"] or "").strip() or None,
        hoat_chat=(r["biet_duoc"] or "").strip() or None,
        so_luong=(r["quantity"] or "").strip() or None,
        so_luong_so=float(sl) if sl is not None else None,
        don_vi=(r["unit"] or r["don_vi_ban"] or "").strip() or None,
        cach_dung=(r["dosage_instructions"] or "").strip() or None,
        luu_y=(r["caution"] or "").strip() or None,
    )


def _nguoi_benh(r: asyncpg.Record) -> NguoiBenh:
    ns = r["date_of_birth"]
    return NguoiBenh(
        ma_benh_nhan=r["patient_code"],
        ho_ten=r["full_name"],
        ngay_sinh=ns.isoformat() if ns else None,
        nam_sinh=ns.year if ns else r["birth_year"],
        gioi_tinh=_GIOI_TINH.get(r["gender"] or ""),
        so_dinh_danh=r["national_id_number"],
        dia_chi=r["address"],
        dien_thoai=r["phone_primary"],
        nguoi_giam_ho=r["guardian_name"],
    )


def _bac_si(r: asyncpg.Record, ma_lien_thong: Mapping[str, str]) -> BacSiKe | None:
    if not r["bs_id"]:
        return None
    return BacSiKe(
        r["bs_id"],
        r["bs_ten"],
        (r["cchn"] or "").strip() or None,
        ma_lien_thong.get(r["bs_id"]),
    )


async def doc_goi_don(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    visit_ids: list[str],
    ma_lien_thong: Mapping[str, str],
) -> dict[str, GoiDon]:
    """Gói đơn hiện hành (CHƯA có mã đơn — hàng chờ cấp khi vào hàng) của các
    lượt. Lượt không còn dòng thuốc nào vẫn có gói (``thuoc`` rỗng = gỡ hết).
    `ma_lien_thong`: staff_id → mã liên thông bác sĩ (từ cấu hình)."""
    ids = sorted(visit_ids)
    luot = {r["visit_id"]: r for r in await conn.fetch(_LUOT_SQL, clinic_id, ids)}
    dong: dict[str, list[asyncpg.Record]] = {}
    for r in await conn.fetch(_DONG_SQL, clinic_id, ids):
        dong.setdefault(r["visit_id"], []).append(r)
    chan_doan = await _chan_doan(conn, clinic_id, ids)
    ra: dict[str, GoiDon] = {}
    for vid, lv in luot.items():
        dong_luc: datetime | None = lv["closed_at"]
        ra[vid] = GoiDon(
            ma_don="",
            visit_id=vid,
            ngay_ke=dong_luc.astimezone(CLINIC_TZ).isoformat(timespec="seconds")
            if dong_luc
            else "",
            bac_si=_bac_si(lv, ma_lien_thong),
            nguoi_benh=_nguoi_benh(lv),
            chan_doan=chan_doan.get(vid),
            thuoc=[_dong_thuoc(d) for d in dong.get(vid, [])],
        )
    return ra


def thieu_truong(goi: GoiDon) -> list[str]:
    """HÀM THUẦN: trường tối thiểu của một đơn (TT 26/2025 PL I — mẫu đơn) còn
    trống, câu người đọc hiểu. Nhà cung cấp khai thêm ở `.thieu()` của nó."""
    thieu: list[str] = []
    if goi.bac_si is None:
        thieu.append("bác sĩ đứng tên đơn")
    elif not goi.bac_si.so_chung_chi:
        thieu.append("số chứng chỉ hành nghề của bác sĩ")
    nb = goi.nguoi_benh
    if not (nb.ho_ten or "").strip():
        thieu.append("họ tên người bệnh")
    if nb.ngay_sinh is None and nb.nam_sinh is None:
        thieu.append("ngày/năm sinh người bệnh")
    # Giới tính KHÔNG chặn: API có mã "1 = chưa có thông tin" (QĐ 808 VII.3).
    if not (goi.chan_doan or "").strip():
        thieu.append("chẩn đoán")
    if not goi.ngay_ke:
        thieu.append("ngày kê")
    for i, t in enumerate(goi.thuoc, start=1):
        if not t.ten_thuoc:
            thieu.append(f"tên thuốc dòng {i}")
        if not t.so_luong:
            thieu.append(f"số lượng dòng {i}")
        if not t.cach_dung:
            thieu.append(f"cách dùng dòng {i}")
    return thieu


def goi_sang_json(goi: GoiDon) -> dict[str, Any]:
    return asdict(goi)


def goi_tu_json(d: dict[str, Any]) -> GoiDon:
    bs = d.get("bac_si")
    return GoiDon(
        **{
            **d,
            "bac_si": BacSiKe(**bs) if bs else None,
            "nguoi_benh": NguoiBenh(**d["nguoi_benh"]),
            "thuoc": [DongThuoc(**t) for t in d.get("thuoc", [])],
        }
    )


def dau_van_tay(goi: GoiDon) -> str:
    """sha256 của NỘI DUNG đơn đã chuẩn hoá — đổi một chữ là đổi dấu. Không tính
    mã đơn (mỗi phiên bản một mã mới, dấu phải chỉ đổi khi nội dung đổi)."""
    return _bam(goi_sang_json(replace(goi, ma_don="")))


def dau_don(goi: GoiDon) -> str:
    """sha256 chỉ phần ĐƠN (thuốc, chẩn đoán, bác sĩ kê, họ tên + ngày sinh + giới
    tính người bệnh, ngày kê). Đơn ĐÃ GỬI mà chỉ đổi SĐT / địa chỉ / CCCD / người
    giám hộ / mã liên thông → KHÔNG sinh đơn thay thế (người bệnh không cầm hai mã
    cho cùng một đơn thuốc). Đơn chưa gửi thì mọi thay đổi đều vào (`dau_van_tay`)
    — để đơn dừng vì thiếu địa chỉ tự đi khi lễ tân điền."""
    nb = goi.nguoi_benh
    bs = goi.bac_si
    return _bam(
        {
            "ngay_ke": goi.ngay_ke,
            "bac_si": [bs.staff_id, bs.ho_ten, bs.so_chung_chi] if bs else None,
            "nguoi_benh": [nb.ho_ten, nb.ngay_sinh, nb.nam_sinh, nb.gioi_tinh],
            "chan_doan": goi.chan_doan,
            "ma_icd": goi.ma_icd,
            "loi_dan": goi.loi_dan,
            "thuoc": [asdict(t) for t in goi.thuoc],
        }
    )


def _bam(d: Any) -> str:
    tho = json.dumps(d, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(tho.encode("utf-8")).hexdigest()


__all__ = [
    "dau_don",
    "dau_van_tay",
    "doc_goi_don",
    "goi_sang_json",
    "goi_tu_json",
    "thieu_truong",
]
