"""Lệnh `PlaceServiceOrders` — bác sĩ/thư ký y khoa chốt chỉ định dịch vụ.

LÁT CD-01. Đặc tả đầy đủ: `docs/slices/CD-01-bac-si-chi-dinh-dich-vu.md`.

VÌ SAO CÓ FILE MỚI THAY VÌ SỬA ĐƯỜNG CŨ. Đường cũ là hai bước: thư ký gửi
`draft-orders`, rồi bác sĩ bấm `authorize-orders`. Tuyền đã chốt (22/09, tin
#149): **thư ký y khoa ngang quyền bác sĩ về chỉ định, chỉ định là chỉ định
luôn**, không có bước duyệt. Nhưng đường cũ đang phục vụ bệnh nhân thật, nên nó
được GIỮ NGUYÊN và lệnh mới nằm cạnh — đổi đường bằng cách chuyển màn sang gọi
lệnh mới, không phải bằng cách sửa ruột đường cũ (branch by abstraction). Khi
màn cuối cùng đã chuyển, đường cũ bị xoá trong một commit.

KHÁC ĐƯỜNG CŨ Ở BỐN CHỖ
  1. Một lệnh thay hai bước; không còn trạng thái `draft`.
  2. Thư ký y khoa (TKYK) chỉ định được, không cần ai duyệt.
  3. Mỗi dịch vụ phát một sự kiện `service_order.placed` vào `domain_event`,
     cùng giao dịch với việc ghi chỉ định.
  4. Chống bấm trùng bằng `Idempotency-Key`, và biên nhận nằm TRONG chính giao
     dịch ấy.

CÁI GIỮ NGUYÊN: tự xếp phòng sau khi chỉ định, và `record_event` vào nhật ký
thao tác — vì màn "Lịch sử thao tác" đang đọc sổ ấy. Ghi cả hai sổ ở giai đoạn
giao thời là có chủ ý, và sẽ bỏ khi màn nhật ký chuyển sang đọc `domain_event`.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import (
    ChiDinhDaDat,
    ChiDinhDoiBatBuoc,
    ChiDinhMangSang,
    ChiDinhTraVe,
)
from clinicai.events.emit import HE_THONG, emit_event, nguoi
from clinicai.permissions.can import doi_quyen
from clinicai.services import finance_gate
from clinicai.services.audit import record_event
from clinicai.services.lenh_kham_core import (
    LuotKhamConflictError,
    bien_nhan_doc,
    bien_nhan_ghi,
    khoa_luot,
    luot_cua,
)
from clinicai.services.lenh_kham_core import (
    LuotKhamValidationError as ValidationError,
)
from clinicai.services.lenh_kham_core import ma_uuid as _uuid
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.so_sua_chi_dinh_service import dat_ngu_canh

#: Quyền cần có để chỉ định. KHÔNG phải một tập vai: ai được cấp khối "Chỉ định
#: dịch vụ" thì làm được, kể cả vai mà hôm nay chưa nghĩ tới. Bác sĩ và thư ký y
#: khoa có sẵn trong preset (Tuyền, tin #149); quản lý cấp thêm cho ai là việc
#: của màn phân quyền, không phải việc của file này.
QUYEN_CHI_DINH = "clinical.order.place"

#: Chỉ định chưa trả mang sang được (lịch đi thẳng phòng): còn phải thu,
#: khách chưa chọn, miễn phí, hoặc đối tác tự thu. Có dấu vết tiền bất thường
#: thì không đụng.
_CHUA_THU_MANG_DUOC = frozenset(
    {
        finance_gate.DUE,
        finance_gate.NOT_APPLICABLE,
        finance_gate.NOT_REQUIRED,
        finance_gate.PARTNER_COLLECTS,
    }
)

ACTION = "chi_dinh.dat"


def doc_lan_dang_thay(v: Any) -> int | None:
    """Lần hiện tại màn gửi kèm lệnh "mở lần mới" → số nguyên 0..9999, rác → None
    (không ném: đầu vào người dùng)."""
    if isinstance(v, bool):
        return None
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if 0 <= n <= 9999 else None


async def dat_mo_lan_moi(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str, thay: int | None
) -> None:
    """Báo trigger `gan_lan_chi_dinh`: giao dịch này MỞ LẦN MỚI. Không biết màn
    thấy lần nào thì lấy lần hiện tại (= luôn mở lần kế)."""
    if thay is None:
        thay = int(
            await conn.fetchval(
                "SELECT coalesce(hien_tai, 0) FROM public.lan_chi_dinh_cua_luot("
                "$1::uuid, $2::uuid)",
                clinic_id,
                visit_id,
            )
            or 0
        )
    await conn.execute(
        "SELECT set_config($1, $2, true)",
        "clinicai.lan_moi_" + str(visit_id).replace("-", ""),
        str(thay),
    )


async def lan_cua_luot(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> dict[str, Any]:
    """Lần hiện tại / lần nút "Chỉ định thêm" sẽ mở — màn chỉ vẽ, không tự đếm."""
    r = await conn.fetchrow(
        "SELECT hien_tai, ke_tiep, mo_moi_duoc"
        "  FROM public.lan_chi_dinh_cua_luot($1::uuid, $2::uuid)",
        clinic_id,
        visit_id,
    )
    if r is None:
        return {"hien_tai": None, "ke_tiep": 1, "mo_moi_duoc": False}
    return {
        "hien_tai": r["hien_tai"],
        "ke_tiep": int(r["ke_tiep"]),
        "mo_moi_duoc": bool(r["mo_moi_duoc"]),
    }


ORIGIN = "api:chi-dinh"


class ChiDinhService:
    """Cửa duy nhất để tạo chỉ định chính thức theo lát CD-01."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def dat_chi_dinh(
        self,
        *,
        consultation_id: str,
        service_codes: list[str],
        identity: StaffIdentity,
        idempotency_key: str | None = None,
        bat_buoc_codes: list[str] | None = None,
        lan_moi: bool = False,
        lan_dang_thay: Any = None,
    ) -> dict[str, Any]:
        """Chốt một loạt chỉ định cho phiên khám. Trả về danh sách id đã tạo
        + `lan` máy chủ gán.

        `bat_buoc_codes`: dịch vụ bác sĩ tick "Bắt buộc" (Tuyền 25/09/2026) —
        quầy thu không bỏ được.

        LẦN (Tuyền 06/10/2026): mặc định vào LẦN HIỆN TẠI của lượt — vào ra màn,
        tải lại, bấm gửi nhiều lần không đổi lần. Chỉ `lan_moi=True` (nút "Chỉ
        định thêm (lần N)") mới mở lần kế; `lan_dang_thay` = lần hiện tại màn
        đang thấy, để hai người cùng bấm mở lần mới không đẻ hai lần (luật ở
        trigger `gan_lan_chi_dinh`, mig 20261006200001).
        """
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        codes = [c.strip() for c in service_codes if isinstance(c, str) and c.strip()]
        if not codes:
            raise ValidationError("NO_SERVICE", "Chưa chọn dịch vụ nào.")
        # Bấm nhầm hai lần cùng một dịch vụ trong một lần gửi: coi là một.
        codes = list(dict.fromkeys(codes))

        bat_buoc = {c.strip() for c in (bat_buoc_codes or []) if isinstance(c, str)}
        thay = doc_lan_dang_thay(lan_dang_thay)
        payload_bien_nhan: dict[str, Any] = {
            "consultation_id": con_id,
            "codes": sorted(codes),
            "bat_buoc": sorted(bat_buoc & set(codes)),
        }
        if lan_moi:
            payload_bien_nhan["lan_moi"] = thay
        luot_kham = LuotKhamService(self._pool)

        async with self._pool.acquire() as conn, conn.transaction():
            # Kiểm quyền TRƯỚC mọi thứ khác, và kiểm trong chính giao dịch này.
            await doi_quyen(conn, identity, QUYEN_CHI_DINH)
            vid = await luot_cua(conn, "consultation", cid, con_id)
            await khoa_luot(conn, cid, vid)
            # Sổ sửa chỉ định (Khối 2): trigger ghi "Thêm" — người bấm + vai.
            await dat_ngu_canh(conn, identity)

            cached = await bien_nhan_doc(
                conn, identity, ACTION, idempotency_key, payload_bien_nhan
            )
            if cached is not None:
                return cached

            consultation = await luot_kham._consultation_in_progress(conn, cid, con_id)
            if lan_moi:
                await dat_mo_lan_moi(conn, cid, vid, thay)

            dich_vu = await luot_kham._services(conn, cid, codes, visit_id=vid)
            # ĐIỀU TRỊ (07/10/2026): lượt đặt lịch Điều trị đã SINH SẴN chỉ định
            # (consumer `dieu_tri`); kê lại cùng dịch vụ điều trị trong lượt thì
            # KHÔNG đẻ dòng thứ hai — quầy thu đúng một lần. Trả chỉ định đang có.
            from clinicai.services.dieu_tri_ban_kham import (
                chi_dinh_dieu_tri_dang_co,
            )

            da_co = await chi_dinh_dieu_tri_dang_co(
                conn, cid, vid, [s["service_code"] for s in dich_vu]
            )
            ids: list[str] = []
            for s in dich_vu:
                if s["service_code"] in da_co:
                    ids.append(da_co[s["service_code"]])
                    continue
                order_id = await conn.fetchval(
                    """
                    INSERT INTO service_order
                        (clinic_id, visit_id, consultation_id, service_code,
                         service_name, node_code, exec_status, recorded_by,
                         authorized_by, authorized_at, selection_status,
                         routing_status, bat_buoc)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6,
                            'authorized', $7::uuid, $7::uuid, now(),
                            'PENDING', 'UNASSIGNED', $8)
                    RETURNING id::text
                    """,
                    cid,
                    vid,
                    con_id,
                    s["service_code"],
                    s["name"],
                    s["node_code"],
                    identity.staff_id,
                    s["service_code"] in bat_buoc,
                )
                ids.append(order_id)

                # Sự kiện đi CÙNG giao dịch với chỉ định: lệnh hỏng thì không có
                # sự kiện mồ côi, và ngược lại.
                await emit_event(
                    conn,
                    ten="service_order.placed",
                    clinic_id=cid,
                    aggregate_id=order_id,
                    aggregate_version=1,
                    payload=ChiDinhDaDat(
                        order_id=order_id,
                        service_code=s["service_code"],
                        service_name=s["name"],
                        consultation_id=con_id,
                        visit_id=vid,
                        selection_status="PENDING",
                        billing_status="UNPAID",
                    ),
                    boi=nguoi(identity),
                    # Cả chuỗi việc của một lượt khám nối với nhau bằng đây.
                    correlation_id=vid,
                )

            # KHÔNG tự xếp phòng ở đây nữa (24/09): chỉ định đời mới chỉ vào
            # hàng phòng sau khi khách chọn + trả tiền (khối Hành trình, H4).
            # `_tu_xep_phong` chỉ còn chạy cho chỉ định đời cũ
            # (`selection_status IS NULL`) nên lời gọi này vốn không làm gì.

            await record_event(
                conn,
                event_type="service_order.placed",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={
                    "visit_id": vid,
                    "consultation_id": con_id,
                    "order_ids": [i for i in ids if i not in da_co.values()],
                    "round_no": consultation["round_no"],
                },
            )

            lan = (
                await conn.fetchval(
                    "SELECT lan_chi_dinh FROM service_order"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    identity.clinic_id,
                    ids[0],
                )
                if ids
                else None
            )
            result = {
                "ok": True,
                "order_ids": ids,
                "lan": lan,
                "da_co_san": sorted(da_co),
            }
            await bien_nhan_ghi(
                conn,
                identity,
                ACTION,
                idempotency_key,
                payload_bien_nhan,
                con_id,
                result,
            )
        return result

    async def doi_bat_buoc(
        self, *, order_id: str, bat_buoc: bool, identity: StaffIdentity
    ) -> dict[str, Any]:
        """`SetServiceOrderRequired` — người chỉ định bật / tắt "Bắt buộc" sau khi
        đã chỉ định (Tuyền 25/09/2026). Chỉ khi dịch vụ CHƯA thu tiền.

        Khoá dòng chỉ định (FOR UPDATE) — cùng dòng quầy thu khoá khi chốt lựa
        chọn, nên hai lệnh chạy nối tiếp: không có kẽ "bác sĩ vừa tick đúng lúc
        quầy thu vừa bỏ".
        """
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_CHI_DINH)
            vid = await luot_cua(conn, "service_order", cid, oid)
            await khoa_luot(conn, cid, vid)
            o = await conn.fetchrow(
                """
                SELECT o.exec_status, o.bat_buoc,
                       EXISTS (
                           SELECT 1 FROM payment_bill_line bl
                             JOIN payment_cycle c
                               ON c.clinic_id = bl.clinic_id
                              AND c.payment_cycle_id = bl.payment_cycle_id
                            WHERE bl.clinic_id = o.clinic_id
                              AND bl.source_type = 'service_order'
                              AND bl.source_id = o.id::text
                              AND bl.billing_owner = 'CLINIC'
                              AND c.status IN ('PENDING_VERIFICATION', 'PAID')
                       ) AS da_thu
                  FROM service_order o
                 WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
                   FOR UPDATE OF o
                """,
                cid,
                oid,
            )
            if o is None or o["exec_status"] in ("draft", "cancelled"):
                raise LuotKhamConflictError(
                    "ORDER_NOT_ACTIVE", "Chỉ định không còn hiệu lực."
                )
            if o["da_thu"]:
                raise LuotKhamConflictError(
                    "SERVICE_ALREADY_PAID",
                    "Dịch vụ đã thu tiền — không đổi “bắt buộc” được nữa.",
                )
            if bool(o["bat_buoc"]) == bool(bat_buoc):
                return {"ok": True, "order_id": oid, "bat_buoc": bool(bat_buoc)}
            await conn.execute(
                "UPDATE service_order SET bat_buoc = $3, version = version + 1,"
                " updated_at = now() WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                oid,
                bool(bat_buoc),
            )
            await emit_event(
                conn,
                ten="service_order.required_changed",
                clinic_id=cid,
                aggregate_id=oid,
                payload=ChiDinhDoiBatBuoc(
                    visit_id=vid, service_order_id=oid, bat_buoc=bool(bat_buoc)
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
        return {"ok": True, "order_id": oid, "bat_buoc": bool(bat_buoc)}

    @staticmethod
    async def mang_sang_luot_moi(
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        visit_id: str,
        causation_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Lệnh `CarryOverUnfinishedOrders` — dây H2 (Tuyền chốt 24/09/2026).

        Khách check-in một lượt mới; chỉ định của các lượt TRƯỚC mà chưa làm:
          * ĐÃ TRẢ TIỀN → mang sang, không thu lại (mọi loại lịch);
          * lịch "đi thẳng phòng" (thủ thuật / sàn chậu, `service_type
            .di_thang_phong`) → mang sang cả chỉ định CHƯA TRẢ, kể cả cái hôm
            trước khách không làm — ngoài đời "hẹn hôm khác làm" và "không làm"
            là cùng một cú bỏ tick ở quầy. Cái khách không làm được HỎI LẠI
            (về "chờ quyết"); lễ tân thu rồi H4 xếp phòng.
          * lịch ĐIỀU TRỊ dịch vụ X (Tuyền chốt 09/10/2026) → DÙNG LUÔN chỉ định
            X bác sĩ đã kê mà chưa làm, chưa thu — kể cả lượt khám ấy còn mở
            hôm nay. Không đẻ chỉ định thứ hai (`sinh_chi_dinh_dieu_tri` thấy có
            sẵn thì thôi), không thu hai lần; kết quả phòng điền về đúng thẻ.

        Chỉ định ĐI THEO KHÁCH, không đi theo lượt: dời `visit_id` sang lượt mới,
        giữ nguyên mã — dấu vết tiền (payment_bill_line) trỏ theo mã chỉ định nên
        FinanceGate vẫn thấy "đã trả"; buổi liệu trình gắn theo mã nên đi theo.
        Món kèm (phụ thu) CHƯA THU đi theo chỉ định — để lại thì quầy lượt cũ thu
        món kèm của một dịch vụ không còn ở đó. Nguồn cũ ở `mang_tu_visit_id`
        (lượt cũ đọc được "đã chuyển sang") + sự kiện `service_order
        .carried_over`. Phòng cũ (nếu có) bỏ: lượt mới xếp lại.

        Không mang: đã làm/đang làm/kết thúc, chưa trả mà lượt mới là lượt khám
        thường, còn chỗ chờ sống ở lượt cũ, cũ quá 180 ngày, tiền đang dở (chờ
        xác minh, đang hoàn, thiếu dấu vết — ngoài `_CHUA_THU_MANG_DUOC`), việc
        khác của lượt đang mở hôm nay. Chạy lại được: chỉ định đã ở lượt mới thì
        không còn là "của lượt trước". Người gọi đã khoá lượt mới.
        """
        moi = await conn.fetchrow(
            """
            SELECT v.clinic_patient_id::text AS pid, v.created_at,
                   coalesce(st.di_thang_phong, false) AS di_thang_phong,
                   (SELECT sp.service_code FROM service_price sp
                     WHERE st.nhom = 'DIEU_TRI' AND sp.id = st.service_price_id
                       AND sp.clinic_id = v.clinic_id) AS ma_dieu_tri
              FROM visit v
              LEFT JOIN appointment a
                ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
              LEFT JOIN service_type st
                ON st.id = coalesce(v.service_type_id, a.service_type_id)
             WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
            """,
            clinic_id,
            visit_id,
        )
        if moi is None:
            return []
        cu = await conn.fetch(
            """
            SELECT o.id::text AS id, o.visit_id::text AS tu_visit_id,
                   o.service_code, o.selection_status, o.lan_chi_dinh
              FROM service_order o
              JOIN visit v ON v.clinic_id = o.clinic_id AND v.visit_id = o.visit_id
             WHERE o.clinic_id = $1::uuid
               AND v.clinic_patient_id = $3::uuid
               AND o.visit_id <> $2::uuid
               AND v.created_at < $4
               -- Lượt cũ đã đóng, hoặc từ hôm trước (lượt hôm nay còn mở là
               -- chính khách đang ở đây — không kéo việc của nó đi). Riêng dịch
               -- vụ của lượt Điều trị thì lượt khám hôm nay còn mở cũng mang:
               -- khách sang làm đúng việc bác sĩ vừa kê.
               AND (v.closed_at IS NOT NULL
                    OR v.created_at < date_trunc('day', $4 AT TIME ZONE
                                                  'Asia/Ho_Chi_Minh')
                                      AT TIME ZONE 'Asia/Ho_Chi_Minh'
                    OR o.service_code = $5::text)
               AND o.created_at >= $4 - interval '180 days'
               AND o.exec_status IN ('authorized', 'assigned')
               AND coalesce(o.execution_status, 'PENDING') = 'PENDING'
               AND o.selection_status IS NOT NULL
               AND NOT EXISTS (
                   SELECT 1 FROM queue_entry q
                    WHERE q.clinic_id = o.clinic_id AND q.reason = 'SERVICE'
                      AND q.ref_id = o.id
                      AND q.status IN ('blocked', 'waiting', 'called', 'serving'))
             ORDER BY o.created_at, o.id
               FOR UPDATE OF o
            """,
            clinic_id,
            visit_id,
            moi["pid"],
            moi["created_at"],
            moi["ma_dieu_tri"],
        )
        if not cu:
            return []
        tai_chinh = await finance_gate.states_for_orders(
            conn, clinic_id, [o["id"] for o in cu]
        )
        chon = chon_mang_sang(
            [
                (o["id"], o["service_code"], _tien_cua(tai_chinh.get(o["id"])))
                for o in cu
            ],
            di_thang_phong=bool(moi["di_thang_phong"]),
            ma_dieu_tri=moi["ma_dieu_tri"],
        )
        mang: list[dict[str, Any]] = []
        for o in cu:
            if o["id"] not in chon:
                continue
            da_thu = chon[o["id"]]
            await conn.execute(
                """
                UPDATE service_order
                   SET mang_tu_visit_id = visit_id, visit_id = $3::uuid,
                       mang_sang_luc = now(), hold_until_round = NULL,
                       routing_status = CASE WHEN routing_status IS NULL
                                             THEN NULL ELSE 'UNASSIGNED' END,
                       routing_revision = routing_revision + 1,
                       room_id = NULL, assigned_by = NULL, assigned_at = NULL,
                       exec_status = 'authorized',
                       -- Hôm trước khách không làm → hỏi lại hôm nay.
                       selection_status = CASE
                           WHEN selection_status = 'NOT_SELECTED' THEN 'PENDING'
                           ELSE selection_status END,
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                clinic_id,
                o["id"],
                visit_id,
            )
            await _doi_luot_mon_kem(
                conn, clinic_id, o["id"], tu=o["tu_visit_id"], sang=visit_id
            )
            await emit_event(
                conn,
                ten="service_order.carried_over",
                clinic_id=clinic_id,
                aggregate_id=o["id"],
                so_ke_tiep=True,
                payload=ChiDinhMangSang(
                    visit_id=visit_id,
                    service_order_id=o["id"],
                    tu_visit_id=o["tu_visit_id"],
                    service_code=o["service_code"],
                    da_thu_tien=da_thu,
                    lan_chi_dinh=o["lan_chi_dinh"],
                ),
                boi=HE_THONG,
                correlation_id=visit_id,
                causation_id=causation_id,
            )
            mang.append({"id": o["id"], "da_thu_tien": da_thu})
        return mang

    @staticmethod
    async def tra_ve_luot_cu(
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        visit_id: str,
        identity: StaffIdentity,
    ) -> list[str]:
        """Lệnh `ReturnCarriedOrders` — HOÀN TÁC của mang sang (09/10/2026).

        Lượt nhận chỉ định mang sang bị hoàn tác check-in / huỷ lịch: chỉ định
        CHƯA ĐỘNG TỚI (chưa làm) quay về đúng lượt nó từ đó tới, đúng lần chỉ
        định cũ — thẻ bác sĩ ở lượt cũ hết "đã chuyển sang", quầy lượt cũ thấy
        lại khoản chưa thu (khoản đã thu đi theo mã chỉ định, không thu lại).
        Check-in lại thì H2 mang sang lần nữa. Người gọi đã khoá lượt.
        """
        rows = await conn.fetch(
            """
            SELECT o.id::text AS id, o.mang_tu_visit_id::text AS ve,
                   o.service_code,
                   (SELECT (e.payload ->> 'lan_chi_dinh')::smallint
                      FROM domain_event e
                     WHERE e.aggregate_id = o.id
                       AND e.event_type = 'service_order.carried_over'
                     ORDER BY e.seq DESC LIMIT 1) AS lan
              FROM service_order o
             WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
               AND o.mang_tu_visit_id IS NOT NULL
               AND o.exec_status IN ('authorized', 'assigned')
               AND coalesce(o.execution_status, 'PENDING') = 'PENDING'
             ORDER BY o.created_at, o.id
               FOR UPDATE OF o
            """,
            clinic_id,
            visit_id,
        )
        for o in rows:
            await conn.execute(
                """
                UPDATE service_order
                   SET visit_id = mang_tu_visit_id, mang_tu_visit_id = NULL,
                       mang_sang_luc = NULL, lan_chi_dinh = $3,
                       routing_status = CASE WHEN routing_status IS NULL
                                             THEN NULL ELSE 'UNASSIGNED' END,
                       routing_revision = routing_revision + 1,
                       room_id = NULL, assigned_by = NULL, assigned_at = NULL,
                       exec_status = 'authorized',
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                clinic_id,
                o["id"],
                o["lan"],
            )
            await _doi_luot_mon_kem(conn, clinic_id, o["id"], tu=visit_id, sang=o["ve"])
            await emit_event(
                conn,
                ten="service_order.carry_returned",
                clinic_id=clinic_id,
                aggregate_id=o["id"],
                so_ke_tiep=True,
                payload=ChiDinhTraVe(
                    visit_id=o["ve"],
                    service_order_id=o["id"],
                    tu_visit_id=visit_id,
                    service_code=o["service_code"],
                ),
                boi=nguoi(identity),
                correlation_id=o["ve"],
            )
        return [o["id"] for o in rows]


def _tien_cua(q: finance_gate.FinanceDecision | None) -> str | None:
    return q.finance_state if q is not None else None


def chon_mang_sang(
    cu: list[tuple[str, str, str | None]],
    *,
    di_thang_phong: bool,
    ma_dieu_tri: str | None,
) -> dict[str, bool]:
    """Chỉ định nào của lượt trước mang sang lượt mới — hàm THUẦN.

    ``cu``: (mã chỉ định, mã dịch vụ, trạng thái tiền FinanceGate) theo thứ tự
    kê (cũ trước). Trả {mã chỉ định: đã thu?}.

    * Đã thu → mang (mọi loại lịch).
    * Lịch đi thẳng phòng → mang cả cái chưa thu (tiền không dở).
    * Lịch ĐIỀU TRỊ dịch vụ ``ma_dieu_tri`` → MỘT chỉ định chưa thu đúng dịch
      vụ ấy (cái kê gần nhất) — một buổi là một chỉ định; đã có cái đúng dịch
      vụ ấy đi theo thì thôi (không thành hai dòng).
    """
    chon: dict[str, bool] = {}
    for oid, _ma, tien in cu:
        if tien == finance_gate.PAID:
            chon[oid] = True
        elif di_thang_phong and tien in _CHUA_THU_MANG_DUOC:
            chon[oid] = False
    if ma_dieu_tri and not any(ma == ma_dieu_tri and oid in chon for oid, ma, _ in cu):
        chua_thu = [
            oid
            for oid, ma, tien in cu
            if ma == ma_dieu_tri and tien in _CHUA_THU_MANG_DUOC
        ]
        if chua_thu:
            chon[chua_thu[-1]] = False
    return chon


async def _doi_luot_mon_kem(
    conn: asyncpg.Connection, clinic_id: str, order_id: str, *, tu: str, sang: str
) -> None:
    """Món kèm CHƯA THU của chỉ định đi theo nó sang lượt khác (hoá đơn đọc món
    kèm theo lượt). Món đã thu ở lượt cũ ở yên — dấu vết tiền của lượt ấy."""
    await conn.execute(
        """
        UPDATE luot_phu_thu p SET visit_id = $4::uuid
         WHERE p.clinic_id = $1::uuid AND p.service_order_id = $2::uuid
           AND p.visit_id = $3::uuid AND p.bo_luc IS NULL
           AND NOT EXISTS (
               SELECT 1 FROM payment_bill_line bl
                 JOIN payment_cycle c
                   ON c.clinic_id = bl.clinic_id
                  AND c.payment_cycle_id = bl.payment_cycle_id
                WHERE bl.clinic_id = p.clinic_id AND bl.source_type = 'phu_thu'
                  AND bl.source_id = p.id::text
                  AND c.status IN ('PENDING_VERIFICATION', 'PAID'))
        """,
        clinic_id,
        order_id,
        tu,
        sang,
    )


__all__ = [
    "ACTION",
    "QUYEN_CHI_DINH",
    "ChiDinhService",
    "LuotKhamConflictError",
    "chon_mang_sang",
]
