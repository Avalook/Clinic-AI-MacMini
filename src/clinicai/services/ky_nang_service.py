"""Phân quyền theo KỸ NĂNG (Tuyền chốt 28/09/2026, bản "D").

Phòng khám giao việc theo kỹ năng (file "Sáng Ý - Thông tin nhân sự": Phụ SA,
Phụ sàn chậu, Bio, TKYK, Lấy mẫu…). Một kỹ năng = một tập LEGO (mã MAN của
permissions/catalogue.py) + các PHÒNG làm (phạm vi của lego "phong").

QUYỀN THẬT KHÔNG ĐỔI CHỖ: vẫn là capability_grant. Tick / bỏ tick một kỹ năng
chỉ ghi `nhan_su_ky_nang` rồi gọi ĐÚNG `PermissionService.doi_lego` — cùng một
đường cấp quyền, cùng sổ kiểm toán, cùng cache. Không có đường cấp thứ hai.

Luật gộp (hàm thuần, test không cần DB):
  * Bật kỹ năng S: bật mọi lego của S. Lego "phong": phòng = phòng đang có ∪
    phòng của S (không lấy mất phòng người ấy đang có vì kỹ năng khác / ngoại lệ).
  * Bỏ kỹ năng S: tắt lego của S mà KHÔNG kỹ năng còn lại nào cần. Lego "phong"
    còn cần thì bỏ đúng những phòng CHỈ S mở.
  * Kỹ năng có lego "phong" mà không khai phòng = mọi phòng (phạm vi CLINIC).

SỬA ĐỊNH NGHĨA kỹ năng thì KHÔNG tự đổi quyền của người đã có (cùng nguyên tắc
nhóm quyền mẫu: một lần sửa không được âm thầm đổi quyền của mười người) — chưa
làm màn sửa ở bản này.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import ValidationError
from clinicai.permissions.can import doi_quyen
from clinicai.permissions.catalogue import MAN
from clinicai.services.permission_service import PermissionService

_VN = ZoneInfo("Asia/Ho_Chi_Minh")
PHONG = "phong"


@dataclass(frozen=True)
class KyNang:
    ma: str
    lego: frozenset[str]
    #: Rỗng + có lego "phong" = mọi phòng.
    phong: frozenset[str]


@dataclass(frozen=True)
class KeHoach:
    """Những lego cần bật / tắt sau một lần tick. `phong` = danh sách phòng
    cho lego "phong" (None = mọi phòng); chỉ có nghĩa khi "phong" trong `bat`."""

    bat: frozenset[str]
    tat: frozenset[str]
    phong: tuple[str, ...] | None


def _phong_cua(ks: Iterable[KyNang]) -> tuple[bool, set[str]]:
    """(có kỹ năng mở MỌI phòng?, hợp phòng) của các kỹ năng có lego "phong"."""
    moi = False
    hop: set[str] = set()
    for k in ks:
        if PHONG in k.lego:
            if not k.phong:
                moi = True
            hop |= k.phong
    return moi, hop


def ke_hoach(
    *,
    ky_nang: KyNang,
    bat: bool,
    con_lai: Sequence[KyNang],
    lego_dang_co: Iterable[str],
    phong_dang_co: Iterable[str] | None,
) -> KeHoach:
    """Thuần: tick (bat=True) / bỏ tick kỹ năng → lego nào bật, tắt, phòng nào.

    `con_lai` = các kỹ năng KHÁC người này vẫn giữ. `phong_dang_co` = phòng
    hiện có của lego "phong" (None = đang mọi phòng).
    """
    dang_co = set(lego_dang_co)
    if bat:
        phong: tuple[str, ...] | None = None
        if PHONG in ky_nang.lego:
            if not ky_nang.phong or phong_dang_co is None and PHONG in dang_co:
                phong = None
            else:
                phong = tuple(sorted(set(phong_dang_co or ()) | ky_nang.phong))
        return KeHoach(bat=frozenset(ky_nang.lego), tat=frozenset(), phong=phong)

    can_giu = set().union(*(k.lego for k in con_lai)) if con_lai else set()
    tat = frozenset((ky_nang.lego - can_giu) & dang_co)
    bat_lai: set[str] = set()
    phong = None
    if PHONG in ky_nang.lego and PHONG in can_giu:
        moi, hop_con_lai = _phong_cua(con_lai)
        if not moi:
            hien = set(phong_dang_co or ())
            chi_cua_s = ky_nang.phong - hop_con_lai
            phong = tuple(sorted((hien - chi_cua_s) | hop_con_lai))
            bat_lai.add(PHONG)
    return KeHoach(bat=frozenset(bat_lai), tat=tat, phong=phong)


class KyNangService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _doc_ky_nang(
        self, conn: asyncpg.Connection, clinic_id: str
    ) -> list[asyncpg.Record]:
        return list(
            await conn.fetch(
                "SELECT ma, ten, nhom, thu_tu, lego, phong_ids::text[] AS phong_ids"
                "  FROM ky_nang WHERE clinic_id = $1::uuid AND active"
                " ORDER BY thu_tu, ten",
                clinic_id,
            )
        )

    async def danh_sach(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Mọi kỹ năng + mở màn nào, phòng nào, bao nhiêu người — cho cột phải."""
        async with self._pool.acquire() as conn:
            await doi_quyen(conn, identity, "permission.manage")
            kn = await self._doc_ky_nang(conn, identity.clinic_id)
            phong = {
                r["id"]: r["name"]
                for r in await conn.fetch(
                    "SELECT id::text AS id, name FROM clinic_room"
                    " WHERE clinic_id = $1::uuid",
                    identity.clinic_id,
                )
            }
            thanh_vien: dict[str, list[str]] = {}
            for r in await conn.fetch(
                "SELECT staff_id::text AS staff_id, ky_nang_ma FROM nhan_su_ky_nang"
                " WHERE clinic_id = $1::uuid",
                identity.clinic_id,
            ):
                thanh_vien.setdefault(r["staff_id"], []).append(r["ky_nang_ma"])
            dem: dict[str, int] = {}
            for ks in thanh_vien.values():
                for k in ks:
                    dem[k] = dem.get(k, 0) + 1
        return {
            "ky_nang": [
                {
                    "ma": r["ma"],
                    "ten": r["ten"],
                    "nhom": r["nhom"],
                    "man": [MAN[m].ten for m in r["lego"] if m in MAN],
                    "phong": [phong.get(p, "Phòng đã xoá") for p in r["phong_ids"]],
                    "moi_phong": PHONG in r["lego"] and not r["phong_ids"],
                    "so_nguoi": dem.get(r["ma"], 0),
                }
                for r in kn
            ],
            # Ai có kỹ năng nào — cột trái ghi kỹ năng dưới tên mỗi người.
            "thanh_vien": thanh_vien,
        }

    async def cua_nguoi(
        self, *, staff_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Kỹ năng người này đang có + lịch HÔM NAY (đứng vị trí nào, phòng nào)."""
        async with self._pool.acquire() as conn:
            await doi_quyen(conn, identity, "permission.manage")
            await PermissionService._phai_cung_phong_kham(conn, identity, staff_id)
            co = [
                r["ky_nang_ma"]
                for r in await conn.fetch(
                    "SELECT ky_nang_ma FROM nhan_su_ky_nang"
                    " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid",
                    identity.clinic_id,
                    staff_id,
                )
            ]
            lich = await conn.fetch(
                """
                SELECT w.shift, coalesce(v.ten, w.station) AS vi_tri,
                       r.name AS phong
                  FROM work_roster w
                  LEFT JOIN vi_tri_lam_viec v
                    ON v.clinic_id = w.clinic_id AND v.code = w.station
                  LEFT JOIN clinic_room r ON r.id = v.room_id
                 WHERE w.clinic_id = $1::uuid AND w.staff_id = $2::uuid
                   AND w.work_date = $3::date AND w.status = 'APPROVED'
                 ORDER BY w.sort, w.shift
                """,
                identity.clinic_id,
                staff_id,
                datetime.now(_VN).date(),
            )
        return {
            "staff_id": staff_id,
            "ky_nang": co,
            "hom_nay": [dict(r) for r in lich],
        }

    async def doi(
        self, *, staff_id: str, ma: str, bat: bool, identity: StaffIdentity
    ) -> dict[str, Any]:
        """`SetStaffSkill` — tick / bỏ tick một kỹ năng cho một người."""
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, "permission.manage")
            await PermissionService._phai_cung_phong_kham(conn, identity, staff_id)
            tat_ca = {
                r["ma"]: KyNang(
                    r["ma"], frozenset(r["lego"]), frozenset(r["phong_ids"])
                )
                for r in await self._doc_ky_nang(conn, identity.clinic_id)
            }
            if ma not in tat_ca:
                raise ValidationError("Không có kỹ năng này (hoặc đã tắt).")
            dang_co = {
                r["ky_nang_ma"]
                for r in await conn.fetch(
                    "SELECT ky_nang_ma FROM nhan_su_ky_nang"
                    " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid",
                    identity.clinic_id,
                    staff_id,
                )
            }
            if bat == (ma in dang_co):
                return {"ok": True, "ma": ma, "bat": bat, "already": True}
            if bat:
                await conn.execute(
                    "INSERT INTO nhan_su_ky_nang"
                    " (clinic_id, staff_id, ky_nang_ma, gan_boi)"
                    " VALUES ($1::uuid, $2::uuid, $3, $4::uuid)",
                    identity.clinic_id,
                    staff_id,
                    ma,
                    identity.staff_id,
                )
            else:
                await conn.execute(
                    "DELETE FROM nhan_su_ky_nang WHERE clinic_id = $1::uuid"
                    " AND staff_id = $2::uuid AND ky_nang_ma = $3",
                    identity.clinic_id,
                    staff_id,
                    ma,
                )
            con_lai = [tat_ca[k] for k in dang_co if k != ma and k in tat_ca]

        # Lego đi qua ĐÚNG đường cấp quyền hiện có (mỗi lệnh một giao dịch, có
        # sổ kiểm toán + xoá cache). Hỏng giữa chừng thì tick lại là đủ: kế
        # hoạch tính từ trạng thái hiện tại, chạy lại được.
        svc = PermissionService(self._pool)
        hien = await svc.lego_cua_nguoi(staff_id=staff_id, identity=identity)
        lego_co = {m["ma"] for m in hien["lego"] if m["bat"] or m["mot_phan"]}
        muc_phong = next((m for m in hien["lego"] if m["ma"] == PHONG), None)
        phong_co: list[str] | None = None
        if muc_phong and not muc_phong.get("tat_ca_phong"):
            phong_co = list(muc_phong.get("phong_ids") or [])
        kh = ke_hoach(
            ky_nang=tat_ca[ma],
            bat=bat,
            con_lai=con_lai,
            lego_dang_co=lego_co,
            phong_dang_co=phong_co,
        )
        for m in sorted(kh.tat):
            await svc.doi_lego(staff_id=staff_id, ma=m, bat=False, identity=identity)
        bat_du = {m["ma"] for m in hien["lego"] if m["bat"]}
        for m in sorted(kh.bat):
            # Lego đã bật đủ thì khỏi cấp lại (sổ kiểm toán không đầy dòng thừa);
            # lego "phong" chỉ ghi lại khi tập phòng thật sự đổi.
            if m in bat_du and (
                m != PHONG
                or (kh.phong is None and phong_co is None)
                or (kh.phong is not None and set(kh.phong) == set(phong_co or ()))
            ):
                continue
            await svc.doi_lego(
                staff_id=staff_id,
                ma=m,
                bat=True,
                identity=identity,
                phong_ids=list(kh.phong) if m == PHONG and kh.phong else None,
            )
        return {
            "ok": True,
            "ma": ma,
            "bat": bat,
            "lego_bat": sorted(kh.bat),
            "lego_tat": sorted(kh.tat),
        }

    async def chep(
        self, *, staff_id: str, tu_staff_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Chép kỹ năng từ người khác — THÊM những kỹ năng còn thiếu, không bỏ gì."""
        nguon = await self.cua_nguoi(staff_id=tu_staff_id, identity=identity)
        dich = await self.cua_nguoi(staff_id=staff_id, identity=identity)
        them = [k for k in nguon["ky_nang"] if k not in dich["ky_nang"]]
        for k in them:
            await self.doi(staff_id=staff_id, ma=k, bat=True, identity=identity)
        return {"ok": True, "them": them}


__all__ = ["KeHoach", "KyNang", "KyNangService", "ke_hoach"]
