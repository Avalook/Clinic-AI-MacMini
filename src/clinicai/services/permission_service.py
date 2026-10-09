"""Lệnh cấp và thu quyền — màn phân quyền của quản lý.

MỘT KHỐI MỘT LẦN BẤM. Quản lý không tick từng quyền lắt nhắt: bật "Sinh hiệu" là
người ấy có mọi quyền con của khối (Tuyền #133). Quyền con vẫn nằm đó để chỗ nào
cần chặt thì chặt được, và "▾ Chi tiết" trên màn sẽ bung ra.

QUẢN LÝ CHỈNH ĐƯỢC CAO NHẤT. Ai có `permission.manage` thì cấp được mọi khối cho
bất kỳ ai trong phòng khám của mình, kể cả khối không nằm trong preset vai họ —
`default_presets` chỉ là gợi ý (#132). Đổi lại: mọi lần cấp và thu đều ghi thành
sự kiện, không sửa đè, nên luôn trả lời được "ai cho ai quyền gì, lúc nào".

MỘT HÀNG RÀO KHÔNG MỞ BẰNG TICK: không cấp cho người ngoài phòng khám của mình.
(Hàng rào "chứng chỉ hành nghề" đã bỏ 24/09/2026 — Tuyền: ai được làm gì = khối
được cấp.)

TỰ CẤP CHO CHÍNH MÌNH. Không chặn: một phòng khám có thể chỉ còn một quản lý, và
chặn tự cấp là cách nhanh nhất để khoá chết cả hệ thống lúc 7 giờ sáng. Bù lại,
mọi lần tự cấp đều nằm trong sổ sự kiện với `actor` chính là người ấy.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import ValidationError
from clinicai.events.catalogue import KhoiQuyenDaCap, KhoiQuyenDaThu
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions import cache
from clinicai.permissions.can import doi_quyen
from clinicai.permissions.catalogue import (
    KHOI,
    KHOI_NOI_BO,
    LUON_BAT,
    MAN,
    MAN_THEO_VAI,
    PRESET,
    QUYEN,
    khoi_sau_khi_doi_man,
    man_dang_bat,
    quyen_cua_khoi,
)

PHAM_VI = frozenset({"CLINIC", "ROOM", "SHIFT"})


async def cap_preset_mac_dinh(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    staff_id: str,
    vai: str,
) -> list[str]:
    """Người mới vào làm được cấp sẵn các khối theo preset của vai.

    VÌ SAO Ở ĐÂY. Quyền THẬT nằm ở dòng cấp quyền, nên một người mới mà không ai
    cấp gì thì không làm được việc. Bắt quản lý tick tay cho từng người mới là
    cách chắc chắn để sáng thứ hai có người ngồi nhìn màn hình trắng.

    Đây là CHÉP, không phải thừa kế: sau khi cấp, quản lý sửa từng khối thoải
    mái, và sửa preset về sau không đụng tới người đã cấp (#132, #134).

    Chạy trong CÙNG giao dịch với việc tạo nhân sự — nửa vời là người có tên mà
    không có quyền.
    """
    # Nhóm mẫu nay là DỮ LIỆU: quản lý sửa được mà không cần deploy. Hằng số
    # `PRESET` chỉ còn là lưới an toàn cho phòng khám chưa chạy migration.
    #
    # Tra nhóm NGAY TRONG câu INSERT chứ không hỏi trước rồi mới ghi: bớt một
    # vòng hỏi database trên đường tạo nhân sự, và không để hai câu nhìn thấy
    # hai phiên bản khác nhau của cùng một nhóm.
    # Một chỗ cấp preset cho cả Python, fixture và script: hàm SQL
    # `cap_quyen_theo_preset` (migration 20260923000016). Nó bỏ qua quyền người
    # này TỪNG có, kể cả đã bị thu — cấp lại không bật lại thứ quản lý đã tắt.
    # `PRESET` chỉ còn là lưới an toàn cho phòng khám chưa có nhóm mẫu.
    ds = await conn.fetch(
        "SELECT cap AS capability"
        "  FROM public.cap_quyen_theo_preset($1::uuid, $2::uuid, $3, $4::text[],"
        "       'Cấp theo preset khi thêm nhân sự') AS cap",
        clinic_id,
        staff_id,
        vai,
        list(PRESET.get(vai, ())),
    )
    cache.quen(clinic_id, staff_id)
    return sorted(r["capability"] for r in ds)


async def giu_nguoi_cap_quyen(conn: asyncpg.Connection, clinic_id: str) -> None:
    """Chặn trước khi commit nếu phòng khám sắp không còn ai cấp được quyền.

    Postgres cũng chặn (trigger `giu_nguoi_cap_quyen_*`, lúc COMMIT) — đây chỉ
    để người dùng nhận một câu dễ hiểu thay vì lỗi database. Khoá dòng phòng
    khám như trigger, để hai người thu quyền cùng lúc không cùng thấy "còn".
    """
    await conn.execute(
        "SELECT 1 FROM public.clinic WHERE id = $1::uuid FOR UPDATE", clinic_id
    )
    con = await conn.fetchval("SELECT public.con_nguoi_cap_quyen($1::uuid)", clinic_id)
    if not con:
        raise ConflictError(
            "Không làm được: phòng khám phải còn ít nhất một người đang làm"
            " có quyền cấp quyền. Cấp quyền ấy cho người khác trước."
        )


class PermissionService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ------------------------------------------------------------------
    # Đọc
    # ------------------------------------------------------------------
    async def quyen_cua_nguoi(
        self, *, staff_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Màn quản lý: người này đang có những khối nào, quyền con nào."""
        async with self._pool.acquire() as conn:
            await doi_quyen(conn, identity, "permission.manage")
            rows = await conn.fetch(
                "SELECT capability, work_pack, scope_type, scope_id::text AS scope_id"
                "  FROM v_quyen_hieu_luc"
                " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid"
                " ORDER BY work_pack, capability",
                identity.clinic_id,
                staff_id,
            )
        theo_khoi: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            theo_khoi.setdefault(r["work_pack"], []).append(
                {
                    "quyen": r["capability"],
                    "ten": QUYEN[r["capability"]].ten
                    if r["capability"] in QUYEN
                    else r["capability"],
                    "pham_vi": r["scope_type"],
                    "pham_vi_id": r["scope_id"],
                }
            )
        return {
            "staff_id": staff_id,
            "khoi": [
                {
                    "ma": ma,
                    "ten": KHOI[ma].ten if ma in KHOI else ma,
                    "quyen": ds,
                }
                for ma, ds in theo_khoi.items()
            ],
        }

    # ------------------------------------------------------------------
    # Lệnh
    # ------------------------------------------------------------------
    async def cap_khoi(
        self,
        *,
        staff_id: str,
        khoi: str,
        identity: StaffIdentity,
        scope_type: str = "CLINIC",
        scope_id: str | None = None,
        valid_until: str | None = None,
        ly_do: str | None = None,
    ) -> dict[str, Any]:
        """`GrantWorkPack` — bật một khối công việc cho một người."""
        if khoi not in KHOI:
            raise ValidationError(f"Không có khối công việc “{khoi}”.")
        if khoi in KHOI_NOI_BO:
            raise ValidationError(
                "Khối nội bộ của đội vận hành ClinicAI — không cấp qua màn Phân quyền."
            )
        if scope_type not in PHAM_VI:
            raise ValidationError("Phạm vi phải là CLINIC, ROOM hoặc SHIFT.")
        if (scope_type == "CLINIC") != (scope_id is None):
            raise ValidationError(
                "Phạm vi hẹp phải nói rõ phòng hoặc ca; toàn phòng khám thì để trống."
            )

        ds_quyen = quyen_cua_khoi(khoi)
        if not ds_quyen:
            raise ValidationError(f"Khối “{KHOI[khoi].ten}” chưa có quyền nào.")

        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, "permission.manage")
            await self._phai_cung_phong_kham(conn, identity, staff_id)

            da_cap: list[str] = []
            for ma in ds_quyen:
                cap_moi = await conn.fetchval(
                    """
                    INSERT INTO capability_grant
                        (clinic_id, staff_id, capability, scope_type, scope_id,
                         valid_until, tu_khoi, granted_by, ly_do)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid, $6::timestamptz,
                            $7, $8::uuid, $9)
                    ON CONFLICT DO NOTHING
                    RETURNING grant_id::text
                    """,
                    identity.clinic_id,
                    staff_id,
                    ma,
                    scope_type,
                    scope_id,
                    valid_until,
                    khoi,
                    identity.staff_id,
                    ly_do,
                )
                if cap_moi is not None:
                    da_cap.append(ma)

            # Cấp lại đúng thứ đã có: không phát sự kiện giả. Không có gì xảy ra
            # thì không có gì để kể.
            if da_cap:
                await emit_event(
                    conn,
                    ten="capability.granted",
                    clinic_id=identity.clinic_id,
                    aggregate_id=staff_id,
                    payload=KhoiQuyenDaCap(
                        staff_id=staff_id,
                        work_pack=khoi,
                        capabilities=sorted(da_cap),
                        scope_type=scope_type,
                        scope_id=scope_id,
                    ),
                    boi=nguoi(identity),
                )

        # Quên bản nhớ NGAY: người vừa được cấp phải làm được ở lệnh kế tiếp.
        cache.quen(identity.clinic_id, staff_id)
        return {"ok": True, "khoi": khoi, "da_cap": sorted(da_cap)}

    async def thu_khoi(
        self,
        *,
        staff_id: str,
        khoi: str,
        identity: StaffIdentity,
        ly_do: str | None = None,
    ) -> dict[str, Any]:
        """`RevokeWorkPack` — tắt một khối. Dòng cũ KHÔNG bị xoá, chỉ đóng lại."""
        if khoi not in KHOI:
            raise ValidationError(f"Không có khối công việc “{khoi}”.")
        if khoi in KHOI_NOI_BO:
            raise ValidationError(
                "Khối nội bộ của đội vận hành ClinicAI — không thu qua màn Phân quyền."
            )

        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, "permission.manage")
            await self._phai_cung_phong_kham(conn, identity, staff_id)

            da_thu = await conn.fetch(
                """
                UPDATE capability_grant
                   SET revoked_at = now(), revoked_by = $4::uuid,
                       ly_do = COALESCE($5, ly_do)
                 WHERE clinic_id = $1::uuid AND staff_id = $2::uuid
                   AND tu_khoi = $3 AND revoked_at IS NULL
                RETURNING capability
                """,
                identity.clinic_id,
                staff_id,
                khoi,
                identity.staff_id,
                ly_do,
            )
            ds = sorted(r["capability"] for r in da_thu)
            if "permission.manage" in ds:
                await giu_nguoi_cap_quyen(conn, identity.clinic_id)
            if ds:
                await emit_event(
                    conn,
                    ten="capability.revoked",
                    clinic_id=identity.clinic_id,
                    aggregate_id=staff_id,
                    payload=KhoiQuyenDaThu(
                        staff_id=staff_id, work_pack=khoi, capabilities=ds
                    ),
                    boi=nguoi(identity),
                )

        # Thu quyền mà còn nhớ bản cũ là lỗ hổng — quên ngay, đừng đợi hết hạn.
        cache.quen(identity.clinic_id, staff_id)
        return {"ok": True, "khoi": khoi, "da_thu": ds}

    async def them_preset(
        self, *, staff_id: str, vai: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """`ApplyRolePreset` — "thêm nhanh preset Điều dưỡng".

        CHÉP một loạt khối vào người ấy. Không phải thừa kế sống: sửa preset về
        sau không đụng tới người đã cấp, và quản lý vẫn tắt được từng khối (#134).
        """
        nhom = await self._khoi_cua_nhom(vai, identity)
        ket_qua = []
        for khoi in nhom:
            ket_qua.append(
                await self.cap_khoi(
                    staff_id=staff_id,
                    khoi=khoi,
                    identity=identity,
                    ly_do=f"Thêm nhanh theo preset {vai}",
                )
            )
        return {"ok": True, "vai": vai, "khoi": [k["khoi"] for k in ket_qua]}

    # ------------------------------------------------------------------
    # LEGO theo người (Tuyền 25/09/2026): 21 công tắc = 21 node thanh bên
    # ------------------------------------------------------------------
    async def lego_cua_nguoi(
        self, *, staff_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Người này đang bật lego nào. Bật = có ĐỦ mọi khối của lego; có một
        phần = vài khối (thường vì khối ấy nằm trong lego khác đang bật)."""
        async with self._pool.acquire() as conn:
            await doi_quyen(conn, identity, "permission.manage")
            await self._phai_cung_phong_kham(conn, identity, staff_id)
            rows = await conn.fetch(
                "SELECT DISTINCT work_pack, scope_type, scope_id::text AS scope_id"
                "  FROM v_quyen_hieu_luc"
                " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid",
                identity.clinic_id,
                staff_id,
            )
            phong = await conn.fetch(
                "SELECT id::text AS id, name AS ten FROM clinic_room"
                " WHERE clinic_id = $1::uuid AND is_active ORDER BY sort, name",
                identity.clinic_id,
            )
        co = {r["work_pack"] for r in rows}
        ds = []
        for m in MAN.values():
            du = set(m.khoi) <= co
            muc: dict[str, Any] = {
                "ma": m.ma,
                "ten": m.ten,
                "cac_duong": list(m.cac_duong),
                "khoi": [{"ma": k, "ten": KHOI[k].ten} for k in m.khoi],
                "bat": du,
                "mot_phan": not du and bool(set(m.khoi) & co),
                "mac_dinh_cho": m.mac_dinh_cho,
            }
            if m.khoi_theo_phong:
                pv = [r for r in rows if r["work_pack"] == m.khoi_theo_phong]
                muc["tat_ca_phong"] = any(r["scope_type"] == "CLINIC" for r in pv)
                muc["phong_ids"] = sorted(
                    r["scope_id"] for r in pv if r["scope_type"] == "ROOM"
                )
            ds.append(muc)
        return {
            "staff_id": staff_id,
            "lego": ds,
            "luon_bat": [{"ten": t, "duong": d} for t, d in LUON_BAT],
            "phong": [dict(r) for r in phong],
        }

    async def doi_lego(
        self,
        *,
        staff_id: str,
        ma: str,
        bat: bool,
        identity: StaffIdentity,
        phong_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Bật / tắt MỘT lego cho một người — qua đúng `cap_khoi` / `thu_khoi`.

        Tắt chỉ gỡ khối KHÔNG còn lego nào khác đang bật cần (Tắt Phòng dịch vụ
        không lấy mất Ghi bệnh án của Bàn khám). Lego theo phòng (Phòng dịch vụ):
        `phong_ids` rỗng / None = tất cả phòng (phạm vi CLINIC).
        """
        if ma not in MAN:
            raise ValidationError(f"Không có lego “{ma}”.")
        lego = MAN[ma]
        hien = await self.lego_cua_nguoi(staff_id=staff_id, identity=identity)
        async with self._pool.acquire() as conn:
            co = [
                r["work_pack"]
                for r in await conn.fetch(
                    "SELECT DISTINCT work_pack FROM v_quyen_hieu_luc"
                    " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid",
                    identity.clinic_id,
                    staff_id,
                )
            ]
        if not bat:
            con = set(khoi_sau_khi_doi_man(co, ma, False))
            for k in sorted(set(co) - con):
                await self.thu_khoi(
                    staff_id=staff_id, khoi=k, identity=identity, ly_do=f"Tắt lego {ma}"
                )
            return {"ok": True, "ma": ma, "bat": False}

        phong_hop_le = {p["id"] for p in hien["phong"]}
        chon = sorted(set(phong_ids or []))
        la = [p for p in chon if p not in phong_hop_le]
        if la:
            raise ValidationError("Có phòng không thuộc phòng khám (hoặc đã tắt).")
        for k in lego.khoi:
            if k == lego.khoi_theo_phong:
                # Đổi phạm vi = thu hết rồi cấp lại đúng phòng đã chọn.
                await self.thu_khoi(
                    staff_id=staff_id,
                    khoi=k,
                    identity=identity,
                    ly_do=f"Đổi phòng {ma}",
                )
                pham_vi: list[str | None] = list(chon) or [None]
                for p in pham_vi:
                    await self.cap_khoi(
                        staff_id=staff_id,
                        khoi=k,
                        identity=identity,
                        scope_type="ROOM" if p else "CLINIC",
                        scope_id=p,
                        ly_do=f"Bật lego {ma}",
                    )
            else:
                await self.cap_khoi(
                    staff_id=staff_id, khoi=k, identity=identity, ly_do=f"Bật lego {ma}"
                )
        return {"ok": True, "ma": ma, "bat": True, "phong_ids": chon}

    # ------------------------------------------------------------------
    # Nhóm quyền mẫu — quản lý tự thêm, sửa, xoá (Tuyền 23/09/2026)
    # ------------------------------------------------------------------
    async def danh_sach_nhom(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Các nhóm mẫu của phòng khám này, kể cả nhóm đã tắt.

        Đọc thì không cần `permission.manage`: biết "nhóm Lễ tân gồm khối nào"
        không phải bí mật, và giấu nó chỉ làm người dùng đoán mò.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT ma, ten, khoi, mo_ta, he_thong, active FROM quyen_preset"
                " WHERE clinic_id = $1::uuid ORDER BY he_thong DESC, ten",
                identity.clinic_id,
            )
        return {"nhom": [dict(r) for r in rows]}

    async def luu_nhom(
        self,
        *,
        ma: str,
        ten: str,
        khoi: list[str],
        mo_ta: str | None,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """`SaveRolePreset` — thêm mới hoặc sửa một nhóm mẫu.

        Sửa nhóm KHÔNG đổi quyền của ai đã được cấp theo nhóm ấy. Nếu nó đổi
        được, thì một lần sửa nhóm là một lần âm thầm đổi quyền của mười người
        — và không ai bấm nút nào cả.
        """
        ma = ma.strip().upper()
        ten = ten.strip()
        if not ma or not ten:
            raise ValidationError("Nhóm phải có mã và tên.")
        la = [k for k in khoi if k not in KHOI]
        if la:
            raise ValidationError(f"Khối không có thật: {', '.join(sorted(la))}")
        # Nhóm mẫu được cấp cho cả loạt người (`cap_quyen_theo_preset`) — gom
        # khối nội bộ vào nhóm là đường cấp lậu.
        if KHOI_NOI_BO & set(khoi):
            raise ValidationError("Khối nội bộ của đội vận hành không vào nhóm được.")

        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, "permission.manage")
            cu = await conn.fetchrow(
                "SELECT he_thong FROM quyen_preset"
                " WHERE clinic_id = $1::uuid AND ma = $2",
                identity.clinic_id,
                ma,
            )
            await conn.execute(
                "INSERT INTO quyen_preset"
                " (clinic_id, ma, ten, khoi, mo_ta, he_thong, tao_boi, sua_boi)"
                " VALUES ($1::uuid, $2, $3, $4::text[], $5, $6, $7::uuid, $7::uuid)"
                " ON CONFLICT (clinic_id, ma) DO UPDATE"
                "    SET ten = EXCLUDED.ten, khoi = EXCLUDED.khoi,"
                "        mo_ta = EXCLUDED.mo_ta, active = true,"
                "        sua_boi = EXCLUDED.sua_boi, sua_luc = now()",
                identity.clinic_id,
                ma,
                ten,
                khoi,
                mo_ta,
                bool(cu["he_thong"]) if cu is not None else False,
                identity.staff_id,
            )
        return {"ok": True, "ma": ma, "khoi": sorted(khoi), "moi": cu is None}

    async def theo_man(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Quyền THEO MÀN: mỗi nhóm mẫu đang bật những màn nào."""
        nhom = (await self.danh_sach_nhom(identity=identity))["nhom"]
        return {
            "man": [
                {
                    "ma": m.ma,
                    "ten": m.ten,
                    "duong": m.duong,
                    "khoi": list(m.khoi),
                    "mac_dinh_cho": m.mac_dinh_cho,
                }
                for m in MAN.values()
            ],
            "man_theo_vai": [
                {"ten": ten, "mac_dinh_cho": ai} for ten, ai in MAN_THEO_VAI
            ],
            "nhom": [
                {
                    "ma": n["ma"],
                    "ten": n["ten"],
                    "active": n["active"],
                    "man_bat": man_dang_bat(list(n["khoi"] or [])),
                }
                for n in nhom
            ],
        }

    async def doi_man(
        self, *, ma_nhom: str, ma_man: str, bat: bool, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Bật/tắt MỘT MÀN cho một nhóm mẫu = thêm/gỡ các khối của màn ấy, qua
        đúng lệnh `SaveRolePreset` (cùng quyền, cùng luật: sửa nhóm KHÔNG đổi
        quyền người đã cấp)."""
        if ma_man not in MAN:
            raise ValidationError(f"Không có màn “{ma_man}”.")
        ma_nhom = ma_nhom.strip().upper()
        async with self._pool.acquire() as conn:
            dong = await conn.fetchrow(
                "SELECT ten, khoi, mo_ta FROM quyen_preset"
                " WHERE clinic_id = $1::uuid AND ma = $2",
                identity.clinic_id,
                ma_nhom,
            )
        if dong is None:
            raise ValidationError(f"Không có nhóm quyền mẫu “{ma_nhom}”.")
        moi = khoi_sau_khi_doi_man(list(dong["khoi"] or []), ma_man, bat)
        kq = await self.luu_nhom(
            ma=ma_nhom,
            ten=dong["ten"],
            khoi=moi,
            mo_ta=dong["mo_ta"],
            identity=identity,
        )
        return {**kq, "man_bat": man_dang_bat(moi)}

    async def xoa_nhom(self, *, ma: str, identity: StaffIdentity) -> dict[str, Any]:
        """`RemoveRolePreset` — bỏ một nhóm mẫu khỏi màn.

        Nhóm dựng sẵn thì TẮT chứ không xoá cứng: người cũ còn phải tra được
        "hồi ấy cấp theo nhóm nào". Nhóm quản lý tự đặt thì xoá hẳn.
        """
        ma = ma.strip().upper()
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, "permission.manage")
            dong = await conn.fetchrow(
                "SELECT he_thong FROM quyen_preset"
                " WHERE clinic_id = $1::uuid AND ma = $2 FOR UPDATE",
                identity.clinic_id,
                ma,
            )
            if dong is None:
                raise ValidationError("Không có nhóm này.")
            if dong["he_thong"]:
                await conn.execute(
                    "UPDATE quyen_preset SET active = false, sua_boi = $3::uuid,"
                    "       sua_luc = now()"
                    " WHERE clinic_id = $1::uuid AND ma = $2",
                    identity.clinic_id,
                    ma,
                    identity.staff_id,
                )
                return {"ok": True, "ma": ma, "da_tat": True}
            await conn.execute(
                "DELETE FROM quyen_preset WHERE clinic_id = $1::uuid AND ma = $2",
                identity.clinic_id,
                ma,
            )
        return {"ok": True, "ma": ma, "da_xoa": True}

    async def _khoi_cua_nhom(self, ma: str, identity: StaffIdentity) -> list[str]:
        """Khối trong một nhóm mẫu — dữ liệu trước, hằng số là lưới an toàn."""
        async with self._pool.acquire() as conn:
            khoi = await conn.fetchval(
                "SELECT khoi FROM quyen_preset"
                " WHERE clinic_id = $1::uuid AND ma = $2 AND active",
                identity.clinic_id,
                ma.upper(),
            )
        if khoi is not None:
            return list(khoi)
        if ma in PRESET:
            return list(PRESET[ma])
        raise ValidationError(f"Không có nhóm quyền mẫu “{ma}”.")

    # ------------------------------------------------------------------
    @staticmethod
    async def _phai_cung_phong_kham(
        conn: asyncpg.Connection, identity: StaffIdentity, staff_id: str
    ) -> None:
        thuoc = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM clinic_membership"
            " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid AND is_active)",
            identity.clinic_id,
            staff_id,
        )
        if not thuoc:
            raise ValidationError("Người này không làm ở phòng khám của bạn.")


__all__ = ["PermissionService"]
