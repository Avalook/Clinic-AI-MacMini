#!/usr/bin/env python3
"""Nhân bản cơ sở Kim Ngưu (KN) thành cơ sở Hào Nam (HN) — Tuyền chốt 08/10/2026.

Chạy TRÊN VPS, trong container api (có asyncpg + DATABASE_URL), sau khi sao lưu:

    python nhan-ban-co-so.py                    # CHẠY THỬ (mặc định): ROLLBACK
    python nhan-ban-co-so.py --that             # dựng thật (MỘT giao dịch)
    python nhan-ban-co-so.py --doi-bo B --that  # sang bộ B (đổi ngược: --doi-bo A)
    python nhan-ban-co-so.py --go --that        # gỡ HN: TẮT, không xoá
    python nhan-ban-co-so.py --chep-kho --that  # kèm chép lô thuốc (cần migration kho)

KIM NGƯU KHÔNG BỊ ĐỤNG MỘT DÒNG NÀO. Đầu và cuối giao dịch lấy dấu vân tay (số
dòng + md5 nội dung) mọi bảng của KN; lệch một byte là ném lỗi → ROLLBACK.

QUY ƯỚC MÃ
-----------
* Phòng bộ A ("y-het-kn", bật mặc định): `HN-<phần sau 'KN-'>` — chép mọi phòng
  ĐANG BẬT của KN (tên, việc chính, tầng, thứ tự, sức chứa, nhận khách, TV, đối
  tác) kèm `clinic_room_node`, `clinic_room_service`, `dispatch_threshold`.
* Phòng bộ B ("so-do-hn", dựng sẵn, TẮT): mã trong `BO_B`, hậu tố `-B`
  (`HN-TIEPDON-B`…) để không trùng mã phòng bộ A (`UNIQUE(clinic_id, code)`).
  Mỗi phòng B lấy việc / dịch vụ / ngưỡng từ (các) phòng mẫu KN; nhiều mẫu thì
  lấy HỢP, việc chính = của mẫu đầu.
* Vị trí làm việc: `HN__<mã KN>` (HAI gạch dưới; phần sau `__` là "mã mẫu" —
  `ma_mau()` cắt tiền tố `^[A-Z0-9]+__` và hậu tố `__\\d+$`). Vị trí chỉ có ở
  bộ B: `HN__T1_THUNGAN__2` (Tầng 2), `HN__T1_THUNGAN__3` (Tầng 3).
* VỊ TRÍ LÀ CỦA CƠ SỞ, KHÔNG CỦA BỘ: chỉ có MỘT tập vị trí `HN__*`. Đổi bộ thì
  cập nhật `room_id` + `tang` của từng vị trí sang phòng của bộ đích; vị trí
  không có phòng trong bộ đích thì TẮT (`room_id` NULL, tầng về tầng gốc), có
  thì BẬT (nên tắt tay một vị trí HN rồi đổi bộ / chạy lại sẽ bật lại nó).
* `vai_duoc_vao_tram`, `staff_vi_tri` của mã mẫu → chép sang mã `HN__…`.
* Quyền theo phòng (`capability_grant` scope ROOM, còn hiệu lực) của phòng KN →
  dòng mới cùng người / quyền / khối, phạm vi = phòng HN tương ứng của BỘ ĐANG
  BẬT, `ly_do` bắt đầu bằng `DAU_NGUON` (để gỡ được). Đổi bộ: thu hồi (không
  xoá) quyền do script cấp ở bộ cũ, suy lại từ KN cho bộ mới. `DIEU_PHOI` và vị
  trí không phòng: dùng chung, không chép.

* Cơ sở HN: tên, địa chỉ, SĐT, `ten_in` (tên in trên phiếu) — chạy lại thì đưa
  về đúng giá trị; cột `phone` / `ten_in` chưa có thì bỏ qua.
* `--chep-kho`: mỗi lô KN → lô HN cùng số lô, tồn 0 + MỘT dòng sổ RECEIVE (trigger
  cộng tồn) để thẻ kho khớp tồn. Chưa có cột `drug_batch.location_id` thì bỏ qua.

Không làm: tạo tài khoản đăng nhập (TV in hướng dẫn); chép `block_budget` (chỉ
tô màu ô lịch), `visit_gate_rule` (luật không gắn cơ sở áp mọi cơ sở),
`staff_node` (không theo cơ sở) — bài trọn luồng đặt lịch HN không cần chúng.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import asyncpg

MA_KN = "KN"
MA_HN = "HN"
TEN_HN = "Hào Nam"
DIA_CHI_HN = (
    "Tầng 1, 2, 3 Nhà số 24 Ngõ 168 Phố Hào Nam, Phường Ô Chợ Dừa, Thành phố Hà Nội"
)
SDT_HN = "0966 558 833"
#: Tên in trên phiếu của cơ sở (cột `ten_in`, migration 20261008100000).
TEN_IN_HN = "Phòng khám chuyên khoa - Phụ sản 4WOMEN"
TIEN_TO_VI_TRI = "HN__"
#: Dấu nguồn ghi vào `ly_do` / `ghi_chu` các dòng script tạo — để gỡ đúng dòng.
DAU_NGUON = "nhan-ban-co-so HN"
LA_VI_TRI_HN = r"LIKE 'HN\_\_%'"


@dataclass(frozen=True)
class PhongB:
    code: str
    ten: str
    tang: str
    sort: int
    mau: tuple[str, ...]  # mã phòng KN mẫu; mẫu đầu cho việc chính + thông số
    la_doi_tac: bool = False


BO_B: tuple[PhongB, ...] = (
    PhongB("HN-TIEPDON-B", "Quầy tiếp đón", "Tầng 1", 10, ("KN-TIEPDON",)),
    PhongB("HN-QUAYTHUOC-B", "Thu ngân thuốc", "Tầng 1", 20, ("KN-QUAYTHUOC",)),
    PhongB("HN-TUVAN-B", "Hỏi bệnh", "Tầng 1", 30, ("KN-TUVAN",)),
    PhongB("HN-NOITIET-B", "Phòng bác sĩ", "Tầng 1", 40, ("KN-NOITIET",)),
    PhongB("HN-SA1-B", "Phòng siêu âm tầng 2", "Tầng 2", 50, ("KN-SA1",)),
    PhongB("HN-SANCHAU-B", "Phòng thủ thuật", "Tầng 2", 60, ("KN-SANCHAU",)),
    PhongB("HN-SAN-BIO-B", "Siêu âm phụ khoa", "Tầng 3", 70, ("KN-SAN-BIO",)),
    PhongB("HN-THUTHUAT-B", "Thủ thuật", "Tầng 3", 80, ("KN-THUTHUAT",)),
    PhongB("HN-XN-B", "Bàn xét nghiệm", "Tầng 4", 90, ("KN-DOCHISO", "KN-LAYMAU")),
    PhongB("HN-SA-E10-B", "Siêu âm E10", "Tầng 4", 100, ("KN-SA1",)),
    PhongB(
        "HN-DOITAC-B", "Phòng đối tác", "Tầng 4", 110, ("KN-DOITAC",), la_doi_tac=True
    ),
)
MA_BO_B = frozenset(p.code for p in BO_B)

#: Vị trí CHỈ có ở bộ B: mã HN → (mã mẫu KN, tầng, phòng B, hậu tố tên).
VI_TRI_CHI_BO_B: dict[str, tuple[str, str, str, str]] = {
    "HN__T1_THUNGAN__2": ("T1_THUNGAN", "Tầng 2", "HN-TIEPDON-B", " tầng 2"),
    "HN__T1_THUNGAN__3": ("T1_THUNGAN", "Tầng 3", "HN-TIEPDON-B", " tầng 3"),
}

BANG = (
    "clinic_location",
    "clinic_room",
    "clinic_room_node",
    "clinic_room_service",
    "dispatch_threshold",
    "vi_tri_lam_viec",
    "vai_duoc_vao_tram",
    "staff_vi_tri",
    "capability_grant",
    "drug_batch",
    "inventory_txn",
)


def ma_phong_a(ma_kn: str) -> str:
    return "HN-" + (ma_kn[3:] if ma_kn.startswith("KN-") else ma_kn)


def ma_vi_tri_hn(ma_kn: str) -> str:
    return TIEN_TO_VI_TRI + ma_kn


def ma_mau(code: str) -> str:
    """`HN__T1_THUNGAN__2` → `T1_THUNGAN`; mã KN giữ nguyên."""
    return re.sub(r"__\d+$", "", re.sub(r"^[A-Z0-9]+__", "", code))


def _so(kq: str) -> int:
    """'INSERT 0 3' / 'UPDATE 2' → số dòng."""
    return int(kq.split()[-1])


@dataclass
class Dem:
    moi: int = 0
    co: int = 0
    doi: int = 0
    bo_qua: int = 0


@dataclass
class BaoCao:
    viec: str
    that: bool
    bo: str = "A"
    dem: dict[str, Dem] = field(default_factory=lambda: {b: Dem() for b in BANG})
    kn: dict[str, tuple[int, str]] = field(default_factory=dict)
    ghi_chu: list[str] = field(default_factory=list)

    def them(
        self, bang: str, *, moi: int = 0, co: int = 0, doi: int = 0, bo_qua: int = 0
    ) -> None:
        d = self.dem[bang]
        d.moi += moi
        d.co += co
        d.doi += doi
        d.bo_qua += bo_qua

    def in_ra(self, out: Callable[[str], Any] = print) -> None:
        kieu = "LÀM THẬT (COMMIT)" if self.that else "CHẠY THỬ (ROLLBACK)"
        out(f"\n== {self.viec} · bộ {self.bo} · {kieu}")
        out(f"  {'bảng':<22}{'tạo mới':>9}{'đã có':>8}{'đổi':>7}{'bỏ qua':>8}")
        for b, d in self.dem.items():
            out(f"  {b:<22}{d.moi:>9}{d.co:>8}{d.doi:>7}{d.bo_qua:>8}")
        out("  Kim Ngưu trước = sau (số dòng · md5):")
        for b, (n, h) in self.kn.items():
            out(f"    {b:<22}{n:>6}  {h[:12]}")
        for g in self.ghi_chu:
            out(f"  · {g}")


@dataclass
class NguCanh:
    cid: str
    kn: str
    hn: str | None
    thao_tac: str | None
    cot_co_so: frozenset[str]  # cột tuỳ chọn của clinic_location đang có
    kho_co_co_so: bool


# ----------------------------------------------------------------------------
# Ngữ cảnh + dấu vân tay Kim Ngưu
# ----------------------------------------------------------------------------
async def _co_cot(conn: asyncpg.Connection, bang: str, cot: str) -> bool:
    return bool(
        await conn.fetchval(
            "SELECT 1 FROM information_schema.columns WHERE table_schema = 'public'"
            " AND table_name = $1 AND column_name = $2",
            bang,
            cot,
        )
    )


async def _ngu_canh(conn: asyncpg.Connection, clinic_id: str | None) -> NguCanh:
    rows = await conn.fetch(
        "SELECT id::text AS id, clinic_id::text AS cid FROM clinic_location"
        " WHERE code = $1 AND ($2::uuid IS NULL OR clinic_id = $2::uuid)",
        MA_KN,
        clinic_id,
    )
    if not rows:
        raise SystemExit("✗ Không thấy cơ sở Kim Ngưu (code KN) — DỪNG.")
    if len({r["cid"] for r in rows}) > 1:
        raise SystemExit(
            f"✗ {len(rows)} phòng khám cùng có cơ sở KN — DỪNG (chỉ rõ --clinic)."
        )
    cid, kn = rows[0]["cid"], rows[0]["id"]
    hn = await conn.fetchval(
        "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid AND code = $2",
        cid,
        MA_HN,
    )
    thao_tac = await conn.fetchval(
        """
        SELECT s.id::text FROM staff s
          JOIN clinic_membership m ON m.staff_id = s.id AND m.is_active
         WHERE m.clinic_id = $1::uuid AND m.role = 'MANAGEMENT' AND s.is_active
         ORDER BY (s.full_name = 'Quản lý hệ thống') DESC, s.created_at, s.id
         LIMIT 1
        """,
        cid,
    )
    return NguCanh(
        cid=cid,
        kn=kn,
        hn=hn,
        thao_tac=thao_tac,
        cot_co_so=frozenset(
            [
                c
                for c in ("phone", "ten_in")
                if await _co_cot(conn, "clinic_location", c)
            ]
        ),
        kho_co_co_so=await _co_cot(conn, "drug_batch", "location_id"),
    )


async def dau_van_kn(
    conn: asyncpg.Connection, ctx: NguCanh
) -> dict[str, tuple[int, str]]:
    """Số dòng + md5 nội dung mọi thứ thuộc Kim Ngưu. Trước phải == sau.

    $1 = cơ sở KN, $2 = phòng khám (mọi câu nhận đủ hai tham số).
    """
    phong_kn = "(SELECT id FROM clinic_room WHERE location_id = $1::uuid)"
    co_ca_hai = "$1::uuid IS NOT NULL AND $2::uuid IS NOT NULL"
    kho = "clinic_id = $2::uuid"
    if ctx.kho_co_co_so:
        kho += (
            " AND location_id IS DISTINCT FROM (SELECT id FROM clinic_location"
            " WHERE clinic_id = $2::uuid AND code = 'HN')"
        )
    dieu_kien = {
        "clinic_location": "id = $1::uuid",
        "clinic_room": "location_id = $1::uuid",
        "clinic_room_node": f"room_id IN {phong_kn}",
        "clinic_room_service": f"room_id IN {phong_kn}",
        "dispatch_threshold": f"room_id IN {phong_kn}",
        "vi_tri_lam_viec": f"clinic_id = $2::uuid AND code NOT {LA_VI_TRI_HN}",
        "vai_duoc_vao_tram": f"clinic_id = $2::uuid AND tram_ma NOT {LA_VI_TRI_HN}",
        "staff_vi_tri": f"clinic_id = $2::uuid AND vi_tri_code NOT {LA_VI_TRI_HN}",
        "capability_grant": f"scope_type = 'ROOM' AND scope_id IN {phong_kn}",
        "drug_batch": kho,
        "inventory_txn": f"drug_batch_id IN (SELECT id FROM drug_batch WHERE {kho})",
    }
    kq: dict[str, tuple[int, str]] = {}
    for bang, dk in dieu_kien.items():
        r = await conn.fetchrow(
            "SELECT count(*) AS n,"
            " md5(coalesce(string_agg(t::text, '|' ORDER BY t::text), '')) AS h"
            f" FROM {bang} t WHERE {dk} AND {co_ca_hai}",
            ctx.kn,
            ctx.cid,
        )
        kq[bang] = (int(r["n"]), str(r["h"]))
    return kq


# ----------------------------------------------------------------------------
# Dựng
# ----------------------------------------------------------------------------
async def _co_so_hn(conn: asyncpg.Connection, ctx: NguCanh, bc: BaoCao) -> str:
    moi = ctx.hn is None
    if ctx.hn is None:
        ctx.hn = await conn.fetchval(
            "INSERT INTO clinic_location (clinic_id, code, name, is_active)"
            " VALUES ($1::uuid, $2, $3, false) RETURNING id::text",
            ctx.cid,
            MA_HN,
            TEN_HN,
        )
    assert ctx.hn is not None
    # Thông tin in trên phiếu: chạy lại thì đưa về đúng giá trị (chỉ dòng HN).
    gia_tri: dict[str, str] = {"name": TEN_HN, "address": DIA_CHI_HN}
    for cot, v in (("phone", SDT_HN), ("ten_in", TEN_IN_HN)):
        if cot in ctx.cot_co_so:
            gia_tri[cot] = v
        else:
            bc.ghi_chu.append(f"clinic_location chưa có cột {cot} — chưa ghi.")
    cots = list(gia_tri)
    n = _so(
        await conn.execute(
            "UPDATE clinic_location SET "
            + ", ".join(f"{c} = ${i}" for i, c in enumerate(cots, start=2))
            + " WHERE id = $1::uuid AND ("
            + " OR ".join(f"{c} IS DISTINCT FROM ${i}" for i, c in enumerate(cots, 2))
            + ")",
            ctx.hn,
            *gia_tri.values(),
        )
    )
    if moi:
        bc.them("clinic_location", moi=1)
    else:
        bc.them("clinic_location", co=1 - n, doi=n)
    return ctx.hn


async def _phong(
    conn: asyncpg.Connection,
    ctx: NguCanh,
    bc: BaoCao,
    *,
    code: str,
    ten: str,
    node_code: str,
    tang: str | None,
    sort: int,
    capacity: int,
    accepting: bool,
    show_on_tv: bool,
    la_doi_tac: bool,
) -> str:
    """Một phòng HN theo mã; có rồi thì giữ nguyên (không ghi đè sửa tay)."""
    r = await conn.fetchrow(
        "SELECT id::text AS id, location_id::text AS loc FROM clinic_room"
        " WHERE clinic_id = $1::uuid AND code = $2",
        ctx.cid,
        code,
    )
    if r is not None:
        if r["loc"] != ctx.hn:
            raise SystemExit(f"✗ Mã phòng {code} đã có ở cơ sở khác Hào Nam — DỪNG.")
        bc.them("clinic_room", co=1)
        return str(r["id"])
    rid = await conn.fetchval(
        """
        INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,
                                 floor, sort, capacity, accepting, show_on_tv,
                                 la_doi_tac, is_active)
        VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10, $11, false)
        RETURNING id::text
        """,
        ctx.cid,
        ctx.hn,
        code,
        ten,
        node_code,
        tang,
        sort,
        capacity,
        accepting,
        show_on_tv,
        la_doi_tac,
    )
    bc.them("clinic_room", moi=1)
    return str(rid)


async def _chep_cau_hinh_phong(
    conn: asyncpg.Connection,
    ctx: NguCanh,
    bc: BaoCao,
    hn_room: str,
    mau_ids: list[str],
    node_chinh: str,
) -> None:
    """Việc (HỢP các mẫu + việc chính), dịch vụ (HỢP), ngưỡng (mẫu đầu có)."""
    nguon = await conn.fetchval(
        "SELECT count(*) FROM (SELECT node_code FROM clinic_room_node"
        " WHERE room_id = ANY($1::uuid[]) UNION SELECT $2::text) x",
        mau_ids,
        node_chinh,
    )
    moi = _so(
        await conn.execute(
            "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
            " SELECT $1::uuid, $2::uuid, node_code FROM ("
            "   SELECT node_code FROM clinic_room_node WHERE room_id = ANY($3::uuid[])"
            "   UNION SELECT $4::text) x"
            " ON CONFLICT DO NOTHING",
            ctx.cid,
            hn_room,
            mau_ids,
            node_chinh,
        )
    )
    bc.them("clinic_room_node", moi=moi, co=int(nguon) - moi)

    nguon = await conn.fetchval(
        "SELECT count(DISTINCT service_code) FROM clinic_room_service"
        " WHERE room_id = ANY($1::uuid[])",
        mau_ids,
    )
    moi = _so(
        await conn.execute(
            "INSERT INTO clinic_room_service (clinic_id, room_id, service_code)"
            " SELECT DISTINCT $1::uuid, $2::uuid, service_code"
            "   FROM clinic_room_service WHERE room_id = ANY($3::uuid[])"
            " ON CONFLICT DO NOTHING",
            ctx.cid,
            hn_room,
            mau_ids,
        )
    )
    bc.them("clinic_room_service", moi=moi, co=int(nguon) - moi)

    nguong = await conn.fetchrow(
        "SELECT wait_minutes, max_waiting FROM dispatch_threshold"
        " WHERE room_id = ANY($1::uuid[])"
        " ORDER BY array_position($1::uuid[], room_id) LIMIT 1",
        mau_ids,
    )
    if nguong is not None:
        moi = _so(
            await conn.execute(
                "INSERT INTO dispatch_threshold"
                " (clinic_id, room_id, wait_minutes, max_waiting)"
                " VALUES ($1::uuid, $2::uuid, $3, $4)"
                " ON CONFLICT (clinic_id, room_id) WHERE room_id IS NOT NULL"
                " DO NOTHING",
                ctx.cid,
                hn_room,
                nguong["wait_minutes"],
                nguong["max_waiting"],
            )
        )
        bc.them("dispatch_threshold", moi=moi, co=1 - moi)


async def _phong_kn(
    conn: asyncpg.Connection, ctx: NguCanh
) -> dict[str, asyncpg.Record]:
    rows = await conn.fetch(
        "SELECT id::text AS id, code, name, node_code, floor, sort, capacity,"
        "       accepting, show_on_tv, la_doi_tac, is_active"
        "  FROM clinic_room WHERE location_id = $1::uuid ORDER BY sort, code",
        ctx.kn,
    )
    return {r["code"]: r for r in rows}


async def _vi_tri_kn(
    conn: asyncpg.Connection, ctx: NguCanh
) -> dict[str, asyncpg.Record]:
    """Vị trí ĐANG BẬT của KN có phòng thuộc KN (DIEU_PHOI không phòng: chung)."""
    rows = await conn.fetch(
        """
        SELECT v.code, v.ten, v.ten_ngan, v.tang, v.phong, v.nhom_nghe, v.sort,
               v.lan, r.code AS ma_phong, r.is_active AS phong_bat
          FROM vi_tri_lam_viec v
          JOIN clinic_room r ON r.id = v.room_id
         WHERE v.clinic_id = $1::uuid AND v.is_active AND r.location_id = $2::uuid
         ORDER BY v.sort, v.code
        """,
        ctx.cid,
        ctx.kn,
    )
    return {r["code"]: r for r in rows}


def _phong_b_cua(ma_kn: str) -> str | None:
    """Phòng B nhận VỊ TRÍ của phòng KN này: phòng B đầu tiên lấy nó làm mẫu."""
    for p in BO_B:
        if ma_kn in p.mau:
            return p.code
    return None


async def _chep_theo_ma_vi_tri(
    conn: asyncpg.Connection, ctx: NguCanh, bc: BaoCao, ma_hn: str
) -> None:
    """`vai_duoc_vao_tram` + `staff_vi_tri` của mã mẫu → mã HN."""
    mau = ma_mau(ma_hn)
    for bang, cot_ma, cot in (
        ("vai_duoc_vao_tram", "tram_ma", "vai, is_active"),
        ("staff_vi_tri", "vi_tri_code", "staff_id, la_chinh, so_ca_mau"),
    ):
        nguon = await conn.fetchval(
            f"SELECT count(*) FROM {bang} WHERE clinic_id = $1::uuid AND {cot_ma} = $2",
            ctx.cid,
            mau,
        )
        moi = _so(
            await conn.execute(
                f"INSERT INTO {bang} (clinic_id, {cot_ma}, {cot}, ghi_chu)"
                f" SELECT clinic_id, $3, {cot},"
                "        $4 || ' từ ' || $2 || coalesce(': ' || ghi_chu, '')"
                f"   FROM {bang} WHERE clinic_id = $1::uuid AND {cot_ma} = $2"
                " ON CONFLICT DO NOTHING",
                ctx.cid,
                mau,
                ma_hn,
                DAU_NGUON,
            )
        )
        bc.them(bang, moi=moi, co=int(nguon) - moi)


async def _dung(
    conn: asyncpg.Connection, ctx: NguCanh, bc: BaoCao, chep_kho: bool
) -> None:
    phong_kn = await _phong_kn(conn, ctx)
    if not any(r["is_active"] for r in phong_kn.values()):
        raise SystemExit("✗ Kim Ngưu không có phòng nào đang bật — DỪNG.")
    await _co_so_hn(conn, ctx, bc)

    # Bộ A: mọi phòng đang bật của KN.
    for code, r in phong_kn.items():
        if not r["is_active"]:
            continue
        hn_room = await _phong(
            conn,
            ctx,
            bc,
            code=ma_phong_a(code),
            ten=r["name"],
            node_code=r["node_code"],
            tang=r["floor"],
            sort=r["sort"],
            capacity=r["capacity"],
            accepting=r["accepting"],
            show_on_tv=r["show_on_tv"],
            la_doi_tac=r["la_doi_tac"],
        )
        await _chep_cau_hinh_phong(conn, ctx, bc, hn_room, [r["id"]], r["node_code"])

    # Bộ B: sơ đồ 4 tầng Hào Nam.
    for p in BO_B:
        mau = [phong_kn[c] for c in p.mau if c in phong_kn]
        if not mau:
            bc.them("clinic_room", bo_qua=1)
            bc.ghi_chu.append(f"Bỏ qua {p.code}: KN không có phòng mẫu {p.mau}.")
            continue
        dau = mau[0]
        hn_room = await _phong(
            conn,
            ctx,
            bc,
            code=p.code,
            ten=p.ten,
            node_code=dau["node_code"],
            tang=p.tang,
            sort=p.sort,
            capacity=dau["capacity"],
            accepting=dau["accepting"],
            show_on_tv=dau["show_on_tv"],
            la_doi_tac=p.la_doi_tac or any(m["la_doi_tac"] for m in mau),
        )
        await _chep_cau_hinh_phong(
            conn, ctx, bc, hn_room, [m["id"] for m in mau], dau["node_code"]
        )

    # Vị trí: MỘT tập HN__* (của cơ sở, không của bộ).
    vi_tri_kn = await _vi_tri_kn(conn, ctx)
    # mã HN → (vị trí mẫu, hậu tố tên, cộng thêm vào sort, tầng)
    can_tao: dict[str, tuple[asyncpg.Record, str, int, str | None]] = {}
    for code, v in vi_tri_kn.items():
        if not (v["phong_bat"] or _phong_b_cua(v["ma_phong"])):
            bc.them("vi_tri_lam_viec", bo_qua=1)
            bc.ghi_chu.append(
                f"Bỏ qua vị trí {code}: phòng {v['ma_phong']} tắt, không là mẫu bộ B."
            )
            continue
        can_tao[ma_vi_tri_hn(code)] = (v, "", 0, v["tang"])
    for ma_hn, (mau_vt, tang_b, _phong_b, hau_to) in VI_TRI_CHI_BO_B.items():
        if mau_vt not in vi_tri_kn:
            bc.them("vi_tri_lam_viec", bo_qua=1)
            bc.ghi_chu.append(f"Bỏ qua {ma_hn}: KN không có vị trí {mau_vt} đang bật.")
            continue
        them = int(ma_hn.rsplit("__", 1)[1])
        can_tao[ma_hn] = (vi_tri_kn[mau_vt], hau_to, them, tang_b)

    for ma_hn, (v, hau_to, them_sort, tang) in can_tao.items():
        moi = _so(
            await conn.execute(
                """
                INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, ten_ngan, tang,
                                             phong, nhom_nghe, sort, lan, is_active)
                VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, false)
                ON CONFLICT (clinic_id, code) DO NOTHING
                """,
                ctx.cid,
                ma_hn,
                v["ten"] + hau_to,
                v["ten_ngan"],
                tang,
                v["phong"],
                v["nhom_nghe"],
                v["sort"] + them_sort,
                v["lan"],
            )
        )
        bc.them("vi_tri_lam_viec", moi=moi, co=1 - moi)
        await _chep_theo_ma_vi_tri(conn, ctx, bc, ma_hn)

    # Bật bộ đang dùng (mới dựng / đã gỡ → A; đang B thì giữ B).
    dang_b = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM clinic_room WHERE location_id = $1::uuid"
        " AND code = ANY($2::text[]) AND is_active)",
        ctx.hn,
        sorted(MA_BO_B),
    )
    await ap_bo(conn, ctx, bc, "B" if dang_b else "A")

    if chep_kho:
        await _chep_kho(conn, ctx, bc)

    bc.ghi_chu.append(
        "TV Hào Nam: script KHÔNG tạo tài khoản. Tạo: ssh clinic-vps-moi"
        " 'cd /home/clinicai/clinicai && EMAIL=manhinh-haonam@dr4women.local"
        ' TEN="Màn hình Hào Nam" CLINIC_DB_CONTAINER=clinicai_db'
        " ./scripts/tao-tai-khoan-man-hinh.sh' — LƯU Ý: bảng gọi số lọc theo"
        " PHÒNG KHÁM, chưa theo cơ sở (TV HN thấy cả số KN)."
    )


async def _chep_kho(conn: asyncpg.Connection, ctx: NguCanh, bc: BaoCao) -> None:
    if not ctx.kho_co_co_so:
        bc.ghi_chu.append(
            "--chep-kho: chưa có migration kho (drug_batch.location_id) — bỏ qua."
        )
        return
    # Lô HN tạo với tồn 0 rồi ghi MỘT dòng sổ RECEIVE (trigger cộng vào tồn) —
    # như PharmacyService.nhap_vao_lo: tồn và sổ kho (thẻ kho) khớp nhau.
    lo_kn = await conn.fetch(
        """
        SELECT b.id::text AS id, b.drug_catalog_id::text AS thuoc, b.batch_code,
               b.expiry_date, b.quantity_on_hand, b.unit, b.cost_price,
               b.received_at,
               EXISTS (SELECT 1 FROM drug_batch x
                        WHERE x.clinic_id = b.clinic_id AND x.location_id = $3::uuid
                          AND x.batch_code = b.batch_code) AS da_co
          FROM drug_batch b
         WHERE b.clinic_id = $1::uuid AND b.location_id = $2::uuid
         ORDER BY b.batch_code
        """,
        ctx.cid,
        ctx.kn,
        ctx.hn,
    )
    for lo in lo_kn:
        if lo["da_co"]:
            bc.them("drug_batch", co=1)
            continue
        lo_hn = await conn.fetchval(
            """
            INSERT INTO drug_batch (clinic_id, location_id, drug_catalog_id,
                                    batch_code, expiry_date, quantity_on_hand, unit,
                                    cost_price, received_at)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, 0, $6, $7, $8)
            RETURNING id::text
            """,
            ctx.cid,
            ctx.hn,
            lo["thuoc"],
            lo["batch_code"],
            lo["expiry_date"],
            lo["unit"],
            lo["cost_price"],
            lo["received_at"],
        )
        bc.them("drug_batch", moi=1)
        if lo["quantity_on_hand"] > 0:
            if ctx.thao_tac is None:
                raise SystemExit("✗ Không có tài khoản Quản lý để ghi sổ kho — DỪNG.")
            await conn.execute(
                "INSERT INTO inventory_txn (clinic_id, drug_batch_id, txn_type,"
                " quantity, reason, ref_type, performed_by_staff_id, performed_at)"
                " VALUES ($1::uuid, $2::uuid, 'RECEIVE', $3, $4, 'manual',"
                " $5::uuid, now())",
                ctx.cid,
                lo_hn,
                lo["quantity_on_hand"],
                f"{DAU_NGUON} từ lô KN {lo['id']}",
                ctx.thao_tac,
            )
            bc.them("inventory_txn", moi=1)


# ----------------------------------------------------------------------------
# Đổi bộ / gỡ
# ----------------------------------------------------------------------------
async def _phong_hn(conn: asyncpg.Connection, ctx: NguCanh) -> dict[str, str]:
    rows = await conn.fetch(
        "SELECT code, id::text AS id FROM clinic_room WHERE location_id = $1::uuid",
        ctx.hn,
    )
    return {r["code"]: r["id"] for r in rows}


async def _thu_hoi(
    conn: asyncpg.Connection, ctx: NguCanh, bc: BaoCao, phong_ids: list[str]
) -> None:
    """Thu hồi (không xoá) quyền ROOM do script cấp trên các phòng này."""
    if not phong_ids:
        return
    dk = (
        " WHERE clinic_id = $1::uuid AND scope_type = 'ROOM'"
        " AND scope_id = ANY($2::uuid[]) AND revoked_at IS NULL"
        " AND ly_do LIKE $3 || '%'"
    )
    can = await conn.fetchval(
        "SELECT count(*) FROM capability_grant" + dk, ctx.cid, phong_ids, DAU_NGUON
    )
    if not can:
        return
    if ctx.thao_tac is None:
        raise SystemExit("✗ Không có tài khoản Quản lý để ghi người thu hồi — DỪNG.")
    n = _so(
        await conn.execute(
            "UPDATE capability_grant SET revoked_at = now(), revoked_by = $4::uuid"
            + dk,
            ctx.cid,
            phong_ids,
            DAU_NGUON,
            ctx.thao_tac,
        )
    )
    bc.them("capability_grant", doi=n)


async def _vi_tri_theo_bo(
    conn: asyncpg.Connection,
    ctx: NguCanh,
    bc: BaoCao,
    bo: str,
    a_ids: dict[str, str],
    b_ids: dict[str, str],
) -> None:
    """Mỗi vị trí HN__*: phòng + tầng theo bộ đích; không có phòng thì TẮT."""
    vi_tri_kn = {
        r["code"]: r
        for r in await conn.fetch(
            "SELECT v.code, v.tang, r.code AS ma_phong FROM vi_tri_lam_viec v"
            "  JOIN clinic_room r ON r.id = v.room_id"
            " WHERE v.clinic_id = $1::uuid AND v.is_active"
            "   AND r.location_id = $2::uuid",
            ctx.cid,
            ctx.kn,
        )
    }
    tang_b = {p.code: p.tang for p in BO_B}
    vi_tri_hn = await conn.fetch(
        "SELECT id::text AS id, code, room_id::text AS room_id, tang, is_active"
        f"  FROM vi_tri_lam_viec WHERE clinic_id = $1::uuid AND code {LA_VI_TRI_HN}",
        ctx.cid,
    )
    for v in vi_tri_hn:
        # Không có phòng ở bộ đích → TẮT, bỏ phòng, tầng về tầng gốc (của vị
        # trí mẫu KN / tầng riêng của vị trí chỉ-bộ-B) — để A→B→A về y như cũ.
        phong: str | None = None
        tang: str | None = v["tang"]
        if v["code"] in VI_TRI_CHI_BO_B:
            _mau, tang, ma_b, _ht = VI_TRI_CHI_BO_B[v["code"]]
            if bo == "B":
                phong = b_ids.get(ma_b)
        else:
            kn = vi_tri_kn.get(ma_mau(v["code"]))
            if kn is not None:
                tang = kn["tang"]
                if bo == "A":
                    phong = a_ids.get(ma_phong_a(kn["ma_phong"]))
                elif (ma_b := _phong_b_cua(kn["ma_phong"])) in b_ids:
                    phong, tang = b_ids[ma_b], tang_b[ma_b]
        dich = (phong, tang, phong is not None)
        if (v["room_id"], v["tang"], v["is_active"]) != dich:
            await conn.execute(
                "UPDATE vi_tri_lam_viec SET room_id = $2::uuid, tang = $3,"
                " is_active = $4 WHERE id = $1::uuid",
                v["id"],
                *dich,
            )
            bc.them("vi_tri_lam_viec", doi=1)


async def _quyen_theo_bo(
    conn: asyncpg.Connection,
    ctx: NguCanh,
    bc: BaoCao,
    bo: str,
    a_ids: dict[str, str],
    b_ids: dict[str, str],
) -> None:
    """Quyền ROOM còn hiệu lực của phòng KN → phòng HN tương ứng của bộ này."""
    cap_kn: list[str] = []
    cap_hn: list[str] = []
    for code, r in (await _phong_kn(conn, ctx)).items():
        if bo == "A":
            hn_id = a_ids.get(ma_phong_a(code)) if r["is_active"] else None
            dich = [hn_id] if hn_id else []
        else:
            dich = [b_ids[p.code] for p in BO_B if code in p.mau and p.code in b_ids]
        for d in dich:
            cap_kn.append(r["id"])
            cap_hn.append(d)
    if not cap_kn:
        return
    nguon_sql = """
          FROM capability_grant g
          JOIN unnest($2::uuid[], $3::uuid[]) AS m(kn, hn) ON g.scope_id = m.kn
         WHERE g.clinic_id = $1::uuid AND g.scope_type = 'ROOM'
           AND g.revoked_at IS NULL
           AND (g.valid_until IS NULL OR g.valid_until > now())
    """
    nguon = await conn.fetchval(
        "SELECT count(*) FROM (SELECT DISTINCT g.staff_id, g.capability, m.hn"
        + nguon_sql
        + ") x",
        ctx.cid,
        cap_kn,
        cap_hn,
    )
    moi = _so(
        await conn.execute(
            """
            INSERT INTO capability_grant
                (clinic_id, staff_id, capability, scope_type, scope_id, valid_from,
                 valid_until, tu_khoi, tu_preset, granted_by, ly_do)
            SELECT DISTINCT ON (g.staff_id, g.capability, m.hn)
                   g.clinic_id, g.staff_id, g.capability, 'ROOM', m.hn, g.valid_from,
                   g.valid_until, g.tu_khoi, g.tu_preset, $4::uuid,
                   $5 || ' bộ ' || $6 || ' từ phòng KN ' || g.scope_id::text
            """
            + nguon_sql
            + """
             ORDER BY g.staff_id, g.capability, m.hn, g.granted_at
            ON CONFLICT DO NOTHING
            """,
            ctx.cid,
            cap_kn,
            cap_hn,
            ctx.thao_tac,
            DAU_NGUON,
            bo,
        )
    )
    bc.them("capability_grant", moi=moi, co=int(nguon) - moi)


async def ap_bo(conn: asyncpg.Connection, ctx: NguCanh, bc: BaoCao, bo: str) -> None:
    """Bật bộ `bo` ("A" | "B"), tắt bộ kia; vị trí + quyền phòng theo bộ ấy."""
    if bo not in ("A", "B"):
        raise SystemExit("✗ Bộ phải là A hoặc B.")
    if ctx.hn is None:
        raise SystemExit("✗ Chưa có cơ sở Hào Nam — chạy dựng trước (không --doi-bo).")
    bc.bo = bo
    phong_hn = await _phong_hn(conn, ctx)
    a_ids = {c: i for c, i in phong_hn.items() if c not in MA_BO_B}
    b_ids = {c: i for c, i in phong_hn.items() if c in MA_BO_B}
    bat, tat = (a_ids, b_ids) if bo == "A" else (b_ids, a_ids)

    n = _so(
        await conn.execute(
            "UPDATE clinic_location SET is_active = true"
            " WHERE id = $1::uuid AND NOT is_active",
            ctx.hn,
        )
    )
    bc.them("clinic_location", doi=n)
    for ids, gia_tri in ((tat, False), (bat, True)):
        n = _so(
            await conn.execute(
                "UPDATE clinic_room SET is_active = $2, updated_at = now()"
                " WHERE id = ANY($1::uuid[]) AND is_active IS DISTINCT FROM $2",
                list(ids.values()),
                gia_tri,
            )
        )
        bc.them("clinic_room", doi=n)

    await _vi_tri_theo_bo(conn, ctx, bc, bo, a_ids, b_ids)
    # Quyền: thu hồi phần script cấp ở bộ kia, suy lại từ KN cho bộ này.
    await _thu_hoi(conn, ctx, bc, list(tat.values()))
    await _quyen_theo_bo(conn, ctx, bc, bo, a_ids, b_ids)


async def _go(conn: asyncpg.Connection, ctx: NguCanh, bc: BaoCao) -> None:
    """Gỡ Hào Nam: TẮT cơ sở + phòng + vị trí, thu hồi quyền script cấp. Không xoá."""
    if ctx.hn is None:
        bc.ghi_chu.append("Không có cơ sở Hào Nam — không có gì để gỡ.")
        return
    bc.bo = "-"
    n = _so(
        await conn.execute(
            "UPDATE clinic_location SET is_active = false"
            " WHERE id = $1::uuid AND is_active",
            ctx.hn,
        )
    )
    bc.them("clinic_location", doi=n)
    phong = list((await _phong_hn(conn, ctx)).values())
    n = _so(
        await conn.execute(
            "UPDATE clinic_room SET is_active = false, updated_at = now()"
            " WHERE id = ANY($1::uuid[]) AND is_active",
            phong,
        )
    )
    bc.them("clinic_room", doi=n)
    n = _so(
        await conn.execute(
            "UPDATE vi_tri_lam_viec SET is_active = false"
            f" WHERE clinic_id = $1::uuid AND code {LA_VI_TRI_HN} AND is_active",
            ctx.cid,
        )
    )
    bc.them("vi_tri_lam_viec", doi=n)
    await _thu_hoi(conn, ctx, bc, phong)
    bc.ghi_chu.append("Đã TẮT Hào Nam (không xoá). Mở lại: --doi-bo A --that.")


# ----------------------------------------------------------------------------
# Lõi: MỘT giao dịch
# ----------------------------------------------------------------------------
async def chay(
    conn: asyncpg.Connection,
    *,
    viec: str = "dung",
    bo: str | None = None,
    that: bool = False,
    chep_kho: bool = False,
    clinic_id: str | None = None,
) -> BaoCao:
    """`viec`: "dung" | "doi-bo" | "go". `that=False` → ROLLBACK cuối."""
    bc = BaoCao(viec=viec, that=that)
    tx = conn.transaction()
    await tx.start()
    try:
        ctx = await _ngu_canh(conn, clinic_id)
        truoc = await dau_van_kn(conn, ctx)
        if viec == "dung":
            await _dung(conn, ctx, bc, chep_kho)
        elif viec == "doi-bo":
            await ap_bo(conn, ctx, bc, bo or "")
        elif viec == "go":
            await _go(conn, ctx, bc)
        else:
            raise SystemExit(f"✗ Việc lạ: {viec}")
        sau = await dau_van_kn(conn, ctx)
        lech = [b for b in truoc if truoc[b] != sau[b]]
        if lech:
            raise RuntimeError(f"✗ Kim Ngưu bị đổi ở {lech} — ROLLBACK toàn bộ.")
        bc.kn = sau
    except BaseException:
        await tx.rollback()
        raise
    if that:
        await tx.commit()
    else:
        await tx.rollback()
    return bc


async def main() -> int:
    ap = argparse.ArgumentParser(description="Nhân bản Kim Ngưu → Hào Nam.")
    ap.add_argument("--that", action="store_true", help="COMMIT (mặc định: ROLLBACK)")
    ap.add_argument("--chay-thu", action="store_true", help="chạy thử (mặc định)")
    nhom = ap.add_mutually_exclusive_group()
    nhom.add_argument("--doi-bo", choices=("A", "B"))
    nhom.add_argument("--go", action="store_true")
    ap.add_argument("--chep-kho", action="store_true")
    ap.add_argument("--clinic", help="clinic_id khi có nhiều phòng khám")
    a = ap.parse_args()
    if a.that and a.chay_thu:
        raise SystemExit("✗ --that và --chay-thu không đi cùng nhau.")
    viec = "doi-bo" if a.doi_bo else "go" if a.go else "dung"
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        bc = await chay(
            conn,
            viec=viec,
            bo=a.doi_bo,
            that=a.that,
            chep_kho=a.chep_kho,
            clinic_id=a.clinic,
        )
    finally:
        await conn.close()
    bc.in_ra()
    if not a.that:
        print("\nĐây là CHẠY THỬ — đã ROLLBACK. Thêm --that để ghi thật.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
