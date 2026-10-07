"""Thực hiện dịch vụ — Bắt đầu, Xong, Không làm được, Gián đoạn, Chuẩn bị làm lại.

Contract: `docs/ai/lifecycle-v1/ClinicAI-EXECUTION-v1.md` (đóng băng 22/09/2026).

NĂM CÂU HỎI mà module này trả lời, và chỉ nó được trả lời:

    đã thực sự bắt đầu chưa · lần làm nào đang chạy · đã xong thật chưa ·
    chưa bắt đầu mà không làm được · đã bắt đầu mà phải dừng giữa chừng

Nó KHÔNG chọn dịch vụ, KHÔNG thu tiền, KHÔNG xếp phòng, KHÔNG quyết kết quả.

MỘT CHỈ ĐỊNH, NHIỀU LẦN LÀM. Máy siêu âm hỏng lúc 10:05 thì lần làm #1 dừng, lần
#2 ở phòng khác bắt đầu lúc 10:18. Luật cũ "mỗi chỉ định chỉ được bắt đầu một
lần" sai với đời thật; luật đúng là **mỗi LẦN LÀM chỉ được bắt đầu một lần**.

`attempt_id` BẮT BUỘC khi bấm Xong hoặc Gián đoạn. Đây không phải thủ tục thừa:
một request mạng cũ của lần làm #1 tới muộn không được phép đóng lần làm #2 đang
chạy — hệ thống nhìn `attempt_id` và từ chối.

BỐN THỨ KHÔNG BAO GIỜ TỰ ĐỘNG khi dừng giữa chừng hay không làm được: không tự
hoàn tiền, không tự đánh dấu đã xong, không tự mở lần làm mới, không tự chọn
phòng khác. Mỗi cái là một quyết định của người, và có lệnh riêng.

"CHỜ LÀM" KHÔNG PHẢI MỘT GIÁ TRỊ ĐƯỢC LƯU. Lược đồ chỉ nhận PENDING ·
IN_PROGRESS · COMPLETED · CANCELLED · NOT_PERFORMED · INTERRUPTED. "Chờ làm"
(`WAITING`) là kết luận TÍNH RA: đang PENDING + khách đã chọn + tiền đã đủ + đã
xếp phòng + không có lần làm nào đang chạy. Lưu nó thành một giá trị riêng nghĩa
là Thu tiền và Xếp phòng cũng phải nhớ ghi execution_status — và ngày nào một
trong hai quên thì hàng chờ sai mà không ai biết.

KHÔNG SUY "AI LÀM CHUYÊN MÔN" TỪ AI BẤM NÚT. Bảng lần làm ghi `started_by`,
`completed_by`, `interrupted_by` — đó là ai thao tác trên hệ thống. Ai chịu
trách nhiệm chuyên môn là dữ liệu khác, ở phiếu kết quả (`thuc_hien_boi`).
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError, ValidationError
from clinicai.events.catalogue import (
    DaXepPhong,
    DichVuDaBatDau,
    DichVuDaHuyBatDau,
    DichVuDaXong,
    DichVuGianDoan,
    DichVuKhongLam,
    DichVuSanSangLamLai,
    KhachDaChuyenPhong,
    XepPhongDaHuy,
)
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can_o_phong_nao_do, doi_quyen
from clinicai.permissions.catalogue import tra_quyen
from clinicai.permissions.doc_bang import doi_mot_quyen
from clinicai.permissions.lich import doi_lich_phong
from clinicai.permissions.y_khoa import QUYEN_Y_KHOA
from clinicai.phieu_kham.mau_goi_y import mau_cho_dich_vu
from clinicai.services import finance_gate
from clinicai.services.day_noi import doc_day, giai_gia_tri
from clinicai.services.finance_gate import can_start
from clinicai.services.hang_cho import (
    cap_nhat_vi_tri,
    mo_cho_bi_chan,
    ve_lai_hang_phong,
)
from clinicai.services.lenh_kham_core import (
    LuotKhamConflictError,
    LuotKhamValidationError,
    bien_nhan_doc,
    bien_nhan_ghi,
    khoa_luot,
    luot_cua,
)

QUYEN_BAT_DAU = "service.execute.start"
QUYEN_XONG = "service.execute.complete"
QUYEN_KHONG_LAM = "service.execute.not_performed"
QUYEN_GIAN_DOAN = "service.execute.interrupt"
QUYEN_LAM_LAI = "service.execute.retry"

#: Vì sao KHÔNG bắt đầu được. Sau khi đã bắt đầu thì dùng lý do gián đoạn.
LY_DO_KHONG_LAM = frozenset(
    {
        "PATIENT_DECLINED_AT_ROOM",
        "CLINICAL_CONTRAINDICATION_BEFORE_START",
        "EQUIPMENT_UNAVAILABLE_BEFORE_START",
        "STAFF_UNAVAILABLE",
        "OTHER",
    }
)

#: Lời cho người đọc cột cũ `not_performed_reason` (Bàn khám in thẳng ra).
_TEN_LY_DO_KHONG_LAM = {
    "PATIENT_DECLINED_AT_ROOM": "Khách từ chối tại phòng",
    "CLINICAL_CONTRAINDICATION_BEFORE_START": "Chống chỉ định trước khi làm",
    "EQUIPMENT_UNAVAILABLE_BEFORE_START": "Máy/thiết bị không dùng được",
    "STAFF_UNAVAILABLE": "Không có người làm",
    "OTHER": "Lý do khác",
}

#: Vì sao đang làm mà phải dừng.
LY_DO_GIAN_DOAN = frozenset(
    {
        "EQUIPMENT_FAILURE",
        "PATIENT_REQUEST",
        "CLINICAL_SAFETY",
        "TECHNICAL_FAILURE",
        "STAFF_UNAVAILABLE",
        "OTHER",
    }
)


#: Lý do HỆ THỐNG ghi khi đóng một lần làm (V4, 30/09/2026) — không nằm trong
#: danh sách người chọn khi bấm Dừng:
#:   PATIENT_MOVED    — phòng khác bấm Bắt đầu và chọn "chuyển khách sang đây";
#:   STARTED_IN_ERROR — "Huỷ bắt đầu nhầm" khi chưa điền gì.
LY_DO_CHUYEN_KHACH = "PATIENT_MOVED"
LY_DO_BAT_DAU_NHAM = "STARTED_IN_ERROR"
#: "Hoàn tác" dịch vụ đã đóng TẠI QUẦY (làm thêm tại quầy, 01/10/2026): lần làm
#: đóng bằng lý do này khi người đứng quầy sửa lại / hoàn tác kết quả.
LY_DO_HOAN_TAC_XONG = "RESULT_UNDONE"
#: Ghi chú lần làm do QUẦY đóng (Hoàn tất phiếu kết quả ở Đo sinh hiệu / Tiếp
#: đón). Là DẤU để lệnh hoàn tác chỉ mở lại những lần làm do quầy đóng — dịch vụ
#: do phòng làm xong thì hoàn tác ở phòng.
GHI_CHU_TAI_QUAY = "Làm tại quầy — hoàn tất phiếu kết quả"
#: LÀM TẠI BÀN KHÁM (Tuyền chốt 07/10/2026): bác sĩ làm chỉ định điều trị ngay
#: tại bàn khám — lần làm mang `noi_lam = BAN_KHAM` (cột của bảng lần làm), phòng
#: chụp là phòng bác sĩ. Quyền = khối y khoa ở bàn khám + trưởng ca (như đổi
#: dịch vụ trong hồ sơ), không phải lego làm dịch vụ ở phòng của chỉ định.
NOI_BAN_KHAM = "BAN_KHAM"
QUYEN_LAM_TAI_BAN_KHAM: tuple[str, ...] = (*QUYEN_Y_KHOA, "dispatch.manage")
CAU_KHONG_QUYEN_BAN_KHAM = "Bạn không có quyền làm dịch vụ tại bàn khám."
CAU_KHACH_KHONG_CHON = (
    "Khách đã chọn KHÔNG làm dịch vụ này ở quầy — muốn làm thì quầy chọn lại."
)
#: Lượt đã check-out / đã đóng: lệnh làm tại bàn khám bị từ chối (Tuyền 07/10/2026
#: — staging: 15:37 vẫn bấm làm tại bàn khám cho khách check-out lúc 15:32). Kiểm
#: TRONG giao dịch sau khi khoá lượt: check-out chen giữa không lọt.
CAU_LUOT_DA_DONG = "Lượt đã check-out — muốn làm tiếp thì Mở lại lượt trước."
#: Phòng KHÔNG Xong / Gián đoạn / Huỷ bắt đầu hộ lần làm của bàn khám.
CAU_DANG_LAM_BAN_KHAM = (
    "Dịch vụ đang làm ở bàn khám — bàn khám bấm Xong / hoàn tác ở hồ sơ khám."
)
#: Gỡ phòng bàn khám đã xếp lúc [Làm tại bàn khám] (hoàn tác) — lý do của
#: `service.routing_invalidated`; không mở việc "xếp lại phòng" cho trưởng ca.
LY_DO_HUY_LAM_BAN_KHAM = "HUY_LAM_TAI_BAN_KHAM"
#: Nguồn của `service.routed` khi [Làm tại bàn khám] xếp chỉ định vào phòng bác
#: sĩ (cột `routing_nguon` vẫn 'khac' như trước — chỉ sự kiện nói rõ nơi bấm).
NGUON_BAN_KHAM = "ban_kham"
CAU_CHUA_BIET_PHONG_BAN_KHAM = (
    "Chưa biết bàn khám ở phòng nào (bác sĩ chưa có lịch ở phòng nào hôm nay) —"
    " xếp phòng cho dịch vụ ở quầy / trưởng ca rồi làm."
)
#: Phòng của bàn khám: chỗ chờ hàng BÁC SĨ có phòng; không thì phòng theo lịch
#: trực HÔM NAY của bác sĩ phiên khám (rồi của người bấm) — cùng cách con trỏ
#: "khách đang ở đâu" (`hang_cho.cap_nhat_vi_tri`) suy phòng bàn khám.
_PHONG_BAN_KHAM_SQL = """
SELECT coalesce(
    (SELECT q.room_id FROM queue_entry q
      WHERE q.clinic_id = $1::uuid AND q.visit_id = $2::uuid
        AND q.lane = 'DOCTOR' AND q.room_id IS NOT NULL
      ORDER BY (q.status = 'serving') DESC, q.updated_at DESC LIMIT 1),
    (SELECT vt.room_id
       FROM work_roster w
       JOIN vi_tri_lam_viec vt ON vt.clinic_id = w.clinic_id AND vt.code = w.station
      WHERE w.clinic_id = $1::uuid AND w.status <> 'REJECTED'
        AND vt.room_id IS NOT NULL
        AND w.work_date = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
        AND w.staff_id IN (bs.id, $3::uuid)
      ORDER BY (w.staff_id = bs.id) DESC, vt.sort LIMIT 1)
)::text
  FROM (SELECT coalesce(
               (SELECT c.doctor_staff_id FROM consultation c
                 WHERE c.clinic_id = $1::uuid AND c.visit_id = $2::uuid
                   AND c.kind = 'PRIMARY' AND c.status <> 'cancelled'
                 ORDER BY c.round_no DESC LIMIT 1),
               (SELECT v.attending_doctor_id FROM visit v
                 WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid)) AS id) bs
"""


def phieu_da_dien(trang_thai: str | None, revision: int | None) -> bool:
    """Phiếu kết quả đã có người điền (V4, 30/09/2026).

    Mở khách ở phòng là màn tự MỞ phiếu (tạo nháp mang giá trị mặc định của
    mẫu, revision 0) — nháp ấy chưa ai gõ gì, không tính. Đã lưu ít nhất một
    lần (revision > 0) hay đã Hoàn tất (READY) mới là "đã điền": không được
    chuyển khách đi / huỷ bắt đầu, vì như thế là bỏ dở công người vừa gõ.
    Cùng luật với `_PHIEU_DA_DIEN_SQL` bên dưới.
    """
    return trang_thai == "READY" or int(revision or 0) > 0


_PHIEU_DA_DIEN_SQL = (
    "SELECT EXISTS (SELECT 1 FROM form_instance"
    " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
    "   AND (trang_thai = 'READY' OR revision > 0))"
)


def huy_bat_dau_duoc(
    execution_status: str | None,
    co_lan_dang_chay: bool,
    phieu: list[tuple[str | None, int | None]],
) -> bool:
    """Màn phòng hiện nút "Huỷ bắt đầu nhầm" khi nào — MÁY CHỦ quyết (V4).

    Đang làm (IN_PROGRESS, có lần làm chạy) và chưa phiếu nào được điền.
    Lệnh `huy_bat_dau` tự kiểm lại đúng luật này khi bấm.
    """
    if execution_status != "IN_PROGRESS" or not co_lan_dang_chay:
        return False
    return not any(phieu_da_dien(t, r) for t, r in phieu)


def phieu_chua_hoan_tat(
    execution_status: str | None, trang_thai_phieu: list[str | None]
) -> bool:
    """Dịch vụ ĐÃ LÀM XONG nhưng phiếu kết quả mới là nháp (27/09/2026, đợt 3).

    Đúng khi: dịch vụ COMPLETED, có ít nhất một phiếu, và không phiếu nào
    READY. Không phiếu nào (dịch vụ không dùng phiếu, chỉ tải ảnh) → False: đó
    không phải chuyện "quên Hoàn tất". Giá trị lạ → False (không báo động giả).
    """
    if execution_status != "COMPLETED" or not trang_thai_phieu:
        return False
    return all(t != "READY" for t in trang_thai_phieu)


async def _doi_quyen_lam(
    conn: asyncpg.Connection, identity: StaffIdentity, quyen: str
) -> None:
    """Cổng sớm: có quyền làm dịch vụ ở phòng NÀO ĐÓ (28/09/2026).

    Quyền làm dịch vụ thường theo PHÒNG (xếp lịch vào phòng = quyền ở đúng
    phòng ấy), nên đúng phòng phải kiểm SAU khi đọc chỉ định. Cổng này chặn
    người không có lego trước khi đọc — họ nhận 403, không biết chỉ định có
    tồn tại hay không.
    """
    if not await can_o_phong_nao_do(conn, identity, quyen):
        raise SafetyGateError(f"Bạn không có quyền “{tra_quyen(quyen).ten}”.")


def cua_tien_ban_kham(
    tien: finance_gate.FinanceDecision | None,
    *,
    selection_status: str | None,
    duoc_chua_thu: bool,
) -> tuple[bool, str | None, bool]:
    """Cửa tiền của [Làm tại bàn khám] — hàm THUẦN, MỘT luật cho nút trên màn và
    cho lệnh. Trả (làm được, câu chặn, phải chốt lựa chọn của khách trước).

    CÙNG FinanceGate với phòng (`FinanceDecision.duoc_lam` — dây
    ``thu_truoc_khi_lam`` + tick "Làm trước – thu sau"). Khách chưa chốt
    (NOT_APPLICABLE): đã chọn KHÔNG làm ở quầy → chặn; chưa quyết mà lượt được
    làm khi chưa thu → làm được, chốt như lúc tick; còn lại → chặn câu "chưa
    thu" gợi ý tick (ô tick có ở Bàn khám).
    """
    if tien is not None and tien.finance_state == finance_gate.NOT_APPLICABLE:
        if selection_status == "NOT_SELECTED":
            return False, CAU_KHACH_KHONG_CHON, False
        if duoc_chua_thu:
            return True, None, True
        return False, finance_gate.CAU_CHUA_THU, False
    if tien is None or not tien.duoc_lam:
        return False, finance_gate.cau_chan_lam(tien), False
    return True, None, False


async def duoc_lam_khi_chua_thu(
    conn: asyncpg.Connection, clinic_id: str, visit_ids: list[str]
) -> dict[str, bool]:
    """Lượt nào được làm khi CHƯA thu: dây thu trước tắt, hoặc lượt đã tick
    "Làm trước – thu sau" (đúng `finance_gate.cua_lam` với một khoản DUE)."""
    rows = await conn.fetch(
        "SELECT v.visit_id::text AS vid, v.lam_truoc_thu_sau_luc IS NOT NULL AS tick,"
        "       (SELECT dn.gia_tri FROM day_nghiep_vu dn"
        "         WHERE dn.clinic_id = v.clinic_id AND dn.ma = $3) AS day"
        "  FROM visit v"
        " WHERE v.clinic_id = $1::uuid AND v.visit_id = ANY($2::uuid[])",
        clinic_id,
        visit_ids,
        finance_gate.DAY_THU_TRUOC,
    )
    return {
        r["vid"]: finance_gate.cua_lam(
            finance_gate.DUE,
            thu_truoc_khi_lam=bool(giai_gia_tri(finance_gate.DAY_THU_TRUOC, r["day"])),
            lam_truoc_thu_sau=bool(r["tick"]),
        )
        for r in rows
    }


class ServiceExecutionService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        # Dùng nhờ hai thứ của kernel cũ: biên nhận lệnh và con trỏ "khách đang
        # ở đâu". Cả hai là CƠ CHẾ DÙNG CHUNG, chép lại là tạo bản thứ hai sẽ
        # lệch.

    # ------------------------------------------------------------------
    async def bat_dau(
        self,
        *,
        order_id: str,
        expected_execution_revision: int,
        expected_routing_revision: int,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
        giai_phong: bool = False,
        xong_truoc: bool = False,
    ) -> dict[str, Any]:
        """`StartService` — mở một lần làm mới cho chỉ định này.

        `giai_phong` (V4, Tuyền 30/09/2026 — làm không theo thứ tự): khách đang
        làm dịch vụ khác ở phòng khác thì lần gọi thường trả 409 PATIENT_BUSY
        kèm tên phòng; màn hỏi "chuyển sang đây?" rồi gửi lại với
        `giai_phong=True` — CÙNG giao dịch dừng lần làm ở phòng kia rồi mới
        bắt đầu ở đây (`_giai_phong_khach`).

        `xong_truoc` (07/10/2026): dịch vụ đang làm ở CHÍNH phòng này → 409
        CUNG_PHONG_DANG_LAM; người bấm [Xong <DV1> & bắt đầu <DV2>] gửi lại với
        cờ này — cùng giao dịch Xong DV1 rồi Bắt đầu DV2 (`_xong_cung_phong`).
        """
        cid = identity.clinic_id
        payload = {
            "order_id": order_id,
            "exec_rev": expected_execution_revision,
            "routing_rev": expected_routing_revision,
            "giai_phong": bool(giai_phong),
            "xong_truoc": bool(xong_truoc),
        }
        async with self._pool.acquire() as conn, conn.transaction():
            await _doi_quyen_lam(conn, identity, QUYEN_BAT_DAU)
            don, vid = await self._khoa_don(conn, cid, order_id)
            await doi_quyen(conn, identity, QUYEN_BAT_DAU, phong_id=don["room_id"])

            cached = await bien_nhan_doc(
                conn, identity, "service.start", idempotency_key, payload
            )
            if cached is not None:
                return cached
            # Quyền theo lịch: phải đang có ca ở phòng của chỉ định (dây nối).
            await doi_lich_phong(
                conn,
                self._pool,
                identity,
                don["room_id"],
                ngay_cu=bool(don["la_ngay_cu"]),
            )

            self._doi_revision(don, expected_execution_revision, "execution_revision")
            self._doi_revision(don, expected_routing_revision, "routing_revision")

            if don["selection_status"] != "SELECTED":
                raise LuotKhamConflictError(
                    "SELECTION_NOT_CONFIRMED", "Khách chưa xác nhận làm dịch vụ này."
                )
            if don["routing_status"] != "ASSIGNED":
                raise LuotKhamConflictError(
                    "ROUTING_NOT_ASSIGNED", "Chỉ định chưa được xếp phòng."
                )
            # "Chờ làm" tính ra chứ không lưu: đủ điều kiện dưới đây mới là chờ.
            if don["execution_status"] not in (None, "PENDING"):
                raise LuotKhamConflictError(
                    "EXECUTION_STATE_INVALID",
                    f"Chỉ định đang ở trạng thái {don['execution_status']}.",
                )
            dang_chay = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM service_execution_attempt"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                "   AND status = 'IN_PROGRESS')",
                cid,
                order_id,
            )
            if dang_chay:
                raise LuotKhamConflictError(
                    "EXECUTION_ALREADY_RUNNING", "Đang có một lần làm chạy dở."
                )

            # Cửa làm của FinanceGate: dây ``thu_truoc_khi_lam`` BẬT (mặc định,
            # 30/09/2026 tối) → chưa thu chỉ làm khi lượt tick "Làm trước – thu
            # sau"; dây TẮT → V10 (chưa thu vẫn làm, cuối buổi quầy thu). Luôn
            # chặn tiền đang hoàn / đã hoàn / sổ lệch.
            tien = await can_start(conn, cid, order_id)
            if tien is None or not tien.duoc_lam:
                raise LuotKhamConflictError(
                    "FINANCE_NOT_READY", finance_gate.cau_chan_lam(tien)
                )

            lan_truoc = await conn.fetchval(
                "SELECT COALESCE(max(attempt_no), 0) FROM service_execution_attempt"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid",
                cid,
                order_id,
            )
            lan = await conn.fetchrow(
                """
                INSERT INTO service_execution_attempt
                    (clinic_id, service_order_id, attempt_no, room_id_snapshot,
                     routing_revision_snapshot, status, started_by, started_at)
                VALUES ($1::uuid, $2::uuid, $3, $4::uuid, $5, 'IN_PROGRESS',
                        $6::uuid, now())
                RETURNING id::text, attempt_no, started_at
                """,
                cid,
                order_id,
                int(lan_truoc) + 1,
                don["room_id"],
                don["routing_revision"],
                identity.staff_id,
            )

            # Khách đang làm ở phòng khác: hỏi trước, chuyển khi người bấm đồng
            # ý (V4 — bỏ khoá PATIENT_BUSY cứng, 30/09/2026).
            await self._giai_phong_khach(
                conn,
                cid,
                vid,
                order_id,
                don,
                identity,
                giai_phong=giai_phong,
                xong_truoc=xong_truoc,
            )
            moi = await self._doi_trang_thai(conn, cid, order_id, "IN_PROGRESS")
            # KHÁCH RỜI CHỖ CŨ SANG PHÒNG NÀY. Luồng chuẩn (Tuyền 23/09/2026):
            # "chỉ định đi chỗ khác = ĐỢI QUAY LẠI, không phải khám xong" — bác
            # sĩ chính còn mở phiên trong lúc khách đi siêu âm. Chỗ đang phục vụ
            # ở bàn bác sĩ (và mọi chỗ đang chờ khác) chuyển "đợi quay lại"
            # (blocked); phiên khám KHÔNG đổi. Làm xong ở phòng thì mở lại
            # (`_dong_hang_cho`). Trước bản này phòng không Bắt đầu được khi
            # phiên bác sĩ còn mở: Postgres chỉ cho MỘT chỗ 'serving' mỗi lượt.
            await conn.execute(
                "UPDATE queue_entry SET status = 'blocked',"
                "       version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                "   AND status IN ('waiting', 'called', 'serving')"
                "   AND NOT (reason = 'SERVICE' AND ref_id = $3::uuid)",
                cid,
                vid,
                order_id,
            )
            # Khách đang ở trong phòng này: hàng chờ của phòng chuyển sang
            # "đang làm". Chỉ MỘT chỗ chờ được 'serving' trong một lượt — chính
            # Postgres giữ luật ấy, không phải Python. Chỗ chờ còn "đợi" (khách
            # vừa ở bàn bác sĩ, chưa có giờ vào hàng) lấy giờ vào hàng = bây giờ.
            await conn.execute(
                "UPDATE queue_entry SET status = 'serving', serving_at = now(),"
                "       eligible_at = coalesce(eligible_at, now()),"
                "       version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND ref_id = $2::uuid"
                "   AND reason = 'SERVICE'"
                "   AND status NOT IN ('done', 'left', 'cancelled')",
                cid,
                order_id,
            )
            # CON TRỎ "KHÁCH ĐANG Ở ĐÂU" — việc mà nút [Gọi vào] từng làm.
            #
            # Bỏ [Gọi vào] mà không bù chỗ này là dựng lại đúng sự cố 17/09/2026
            # ghi trong `_cap_nhat_vi_tri`: khám xong cả vòng rồi mà trưởng ca
            # vẫn thấy khách "đang ở Đo chỉ số", và quầy không đóng được lượt.
            # Bảng điều phối, TV phòng chờ và bước đóng lượt đều đọc con trỏ này.
            #
            # Trong CÙNG giao dịch với việc mở lần làm: hai thứ ấy hoặc cùng
            # đúng, hoặc cùng không xảy ra.
            await cap_nhat_vi_tri(conn, cid, vid)

            await emit_event(
                conn,
                ten="service.started",
                clinic_id=cid,
                aggregate_id=order_id,
                so_ke_tiep=True,  # một dãy số cho cả chỉ định (emit.py)
                payload=DichVuDaBatDau(
                    visit_id=vid,
                    service_order_id=order_id,
                    attempt_id=lan["id"],
                    attempt_no=lan["attempt_no"],
                    room_id=str(don["room_id"]) if don["room_id"] else None,
                    execution_revision=moi,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )

            ket_qua = {
                "ok": True,
                "order_id": order_id,
                "attempt_id": lan["id"],
                "attempt_no": lan["attempt_no"],
                "execution_status": "IN_PROGRESS",
                "execution_revision": moi,
                "started_at": lan["started_at"].isoformat(),
            }
            await bien_nhan_ghi(
                conn, identity, "service.start", idempotency_key, payload, vid, ket_qua
            )
        return ket_qua

    # ------------------------------------------------------------------
    async def xong(
        self,
        *,
        order_id: str,
        attempt_id: str,
        expected_execution_revision: int,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
        ghi_chu: str | None = None,
    ) -> dict[str, Any]:
        """`CompleteService` — lần làm này đã xong.

        `ghi_chu` (tuỳ chọn, 24/09/2026): điều dưỡng lấy mẫu / phòng bấm Xong ghi
        lại gì đó ("khách khó lấy ven, lấy lần 2") — lưu vào CHÍNH lần làm.

        KHÔNG nhận nội dung kết quả: `service.completed` ≠ `result.ready`. Kết
        quả là việc của biểu mẫu (`form_instance`), một vòng đời riêng.
        """
        cid = identity.clinic_id
        payload = {"order_id": order_id, "attempt_id": attempt_id}
        ghi = (ghi_chu or "").strip() or None
        if ghi is not None and len(ghi) > 2000:
            raise LuotKhamValidationError(
                "NOTE_TOO_LONG", "Ghi chú quá dài (tối đa 2.000 ký tự)."
            )
        async with self._pool.acquire() as conn, conn.transaction():
            await _doi_quyen_lam(conn, identity, QUYEN_XONG)
            don, vid = await self._khoa_don(conn, cid, order_id)
            await doi_quyen(conn, identity, QUYEN_XONG, phong_id=don["room_id"])
            cached = await bien_nhan_doc(
                conn, identity, "service.complete", idempotency_key, payload
            )
            if cached is not None:
                return cached
            # Quyền theo lịch: phải đang có ca ở phòng của chỉ định (dây nối).
            await doi_lich_phong(
                conn,
                self._pool,
                identity,
                don["room_id"],
                ngay_cu=bool(don["la_ngay_cu"]),
            )

            self._doi_revision(don, expected_execution_revision, "execution_revision")
            if don["execution_status"] != "IN_PROGRESS":
                raise LuotKhamConflictError(
                    "EXECUTION_STATE_INVALID", "Chỉ định không đang được làm."
                )
            lan = await self._lan_dang_chay(conn, cid, order_id, attempt_id)
            moi = await self._ghi_xong(conn, cid, vid, order_id, lan, identity, ghi)
            ket_qua = {
                "ok": True,
                "order_id": order_id,
                "attempt_id": lan["id"],
                "execution_status": "COMPLETED",
                "execution_revision": moi,
            }
            await bien_nhan_ghi(
                conn,
                identity,
                "service.complete",
                idempotency_key,
                payload,
                vid,
                ket_qua,
            )
        return ket_qua

    # ------------------------------------------------------------------
    async def khong_lam(
        self,
        *,
        order_id: str,
        expected_execution_revision: int,
        ly_do: str,
        ghi_chu: str | None,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """`MarkServiceNotPerformed` — đã tới lượt mà cuối cùng không làm.

        Không sinh "lần làm giả": chưa ai bắt đầu thì không có lần làm nào.
        Tiền đã thu KHÔNG tự hoàn — hoàn tiền là quyết định của người, đi đường
        tài chính riêng.
        """
        if ly_do not in LY_DO_KHONG_LAM:
            raise ValidationError(f"Lý do không hợp lệ: {ly_do}.")
        if ly_do == "OTHER" and not (ghi_chu or "").strip():
            raise ValidationError("Chọn lý do Khác thì phải ghi rõ.")

        cid = identity.clinic_id
        payload = {"order_id": order_id, "ly_do": ly_do}
        async with self._pool.acquire() as conn, conn.transaction():
            await _doi_quyen_lam(conn, identity, QUYEN_KHONG_LAM)
            don, vid = await self._khoa_don(conn, cid, order_id)
            await doi_quyen(conn, identity, QUYEN_KHONG_LAM, phong_id=don["room_id"])
            cached = await bien_nhan_doc(
                conn, identity, "service.not_performed", idempotency_key, payload
            )
            if cached is not None:
                return cached
            # Quyền theo lịch: phải đang có ca ở phòng của chỉ định (dây nối).
            await doi_lich_phong(
                conn,
                self._pool,
                identity,
                don["room_id"],
                ngay_cu=bool(don["la_ngay_cu"]),
            )

            self._doi_revision(don, expected_execution_revision, "execution_revision")
            if don["execution_status"] not in (None, "PENDING"):
                raise LuotKhamConflictError(
                    "EXECUTION_STATE_INVALID",
                    "Đã bắt đầu làm thì dùng Gián đoạn, không phải Không làm.",
                )
            da_tung_bat_dau = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM service_execution_attempt"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid)",
                cid,
                order_id,
            )
            if da_tung_bat_dau:
                raise LuotKhamConflictError(
                    "EXECUTION_ALREADY_STARTED",
                    "Chỉ định này đã từng bắt đầu — dùng đường gián đoạn.",
                )

            moi = await self._doi_trang_thai(
                conn,
                cid,
                order_id,
                "NOT_PERFORMED",
                ly_do=" — ".join(
                    x
                    for x in (
                        _TEN_LY_DO_KHONG_LAM.get(ly_do, ly_do),
                        (ghi_chu or "").strip(),
                    )
                    if x
                ),
            )
            await self._dong_hang_cho(conn, cid, order_id)

            tien = await can_start(conn, cid, order_id)
            await emit_event(
                conn,
                ten="service.not_performed",
                clinic_id=cid,
                aggregate_id=order_id,
                so_ke_tiep=True,  # một dãy số cho cả chỉ định (emit.py)
                payload=DichVuKhongLam(
                    visit_id=vid,
                    service_order_id=order_id,
                    ly_do=ly_do,
                    execution_revision=moi,
                    # Đã thu tiền mà không làm: có người phải xử lý, nên nói rõ
                    # ngay trong sự kiện thay vì để bên nghe tự suy.
                    da_thu_tien=bool(tien and tien.finance_state == "PAID"),
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            ket_qua = {
                "ok": True,
                "order_id": order_id,
                "execution_status": "NOT_PERFORMED",
                "execution_revision": moi,
                "can_doi_soat_tien": bool(tien and tien.finance_state == "PAID"),
            }
            await bien_nhan_ghi(
                conn,
                identity,
                "service.not_performed",
                idempotency_key,
                payload,
                vid,
                ket_qua,
            )
        return ket_qua

    # ------------------------------------------------------------------
    async def gian_doan(
        self,
        *,
        order_id: str,
        attempt_id: str,
        expected_execution_revision: int,
        ly_do: str,
        ghi_chu: str | None,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """`InterruptService` — đã bắt đầu nhưng không hoàn thành được."""
        if ly_do not in LY_DO_GIAN_DOAN:
            raise ValidationError(f"Lý do không hợp lệ: {ly_do}.")
        if ly_do == "OTHER" and not (ghi_chu or "").strip():
            raise ValidationError("Chọn lý do Khác thì phải ghi rõ.")

        cid = identity.clinic_id
        payload = {"order_id": order_id, "attempt_id": attempt_id, "ly_do": ly_do}
        async with self._pool.acquire() as conn, conn.transaction():
            await _doi_quyen_lam(conn, identity, QUYEN_GIAN_DOAN)
            don, vid = await self._khoa_don(conn, cid, order_id)
            await doi_quyen(conn, identity, QUYEN_GIAN_DOAN, phong_id=don["room_id"])
            cached = await bien_nhan_doc(
                conn, identity, "service.interrupt", idempotency_key, payload
            )
            if cached is not None:
                return cached
            # Quyền theo lịch: phải đang có ca ở phòng của chỉ định (dây nối).
            await doi_lich_phong(
                conn,
                self._pool,
                identity,
                don["room_id"],
                ngay_cu=bool(don["la_ngay_cu"]),
            )

            self._doi_revision(don, expected_execution_revision, "execution_revision")
            if don["execution_status"] != "IN_PROGRESS":
                raise LuotKhamConflictError(
                    "EXECUTION_STATE_INVALID", "Chỉ định không đang được làm."
                )
            lan = await self._lan_dang_chay(conn, cid, order_id, attempt_id)

            await conn.execute(
                "UPDATE service_execution_attempt"
                "   SET status = 'INTERRUPTED', interrupted_by = $3::uuid,"
                "       interrupted_at = now(), interruption_reason_code = $4,"
                "       interruption_reason_note = $5, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                lan["id"],
                identity.staff_id,
                ly_do,
                ghi_chu,
            )
            moi = await self._doi_trang_thai(conn, cid, order_id, "INTERRUPTED")
            await self._dong_hang_cho(conn, cid, order_id)

            await emit_event(
                conn,
                ten="service.interrupted",
                clinic_id=cid,
                aggregate_id=order_id,
                so_ke_tiep=True,  # một dãy số cho cả chỉ định (emit.py)
                payload=DichVuGianDoan(
                    visit_id=vid,
                    service_order_id=order_id,
                    attempt_id=lan["id"],
                    attempt_no=lan["attempt_no"],
                    ly_do=ly_do,
                    execution_revision=moi,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            ket_qua = {
                "ok": True,
                "order_id": order_id,
                "attempt_id": lan["id"],
                "execution_status": "INTERRUPTED",
                "execution_revision": moi,
            }
            await bien_nhan_ghi(
                conn,
                identity,
                "service.interrupt",
                idempotency_key,
                payload,
                vid,
                ket_qua,
            )
        return ket_qua

    # ------------------------------------------------------------------
    async def chuan_bi_lam_lai(
        self,
        *,
        order_id: str,
        interrupted_attempt_id: str,
        expected_execution_revision: int,
        ghi_chu: str | None,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """`PrepareServiceRetry` — người quyết định sẽ làm lại.

        Cố ý là một lệnh RIÊNG. Để `StartService` tự hiểu "gián đoạn thì bắt đầu
        lại luôn" là bỏ qua đúng những thứ phải có người quyết: bác sĩ đồng ý
        chưa, đổi phòng chưa, máy sửa chưa, khách còn muốn làm không.
        """
        cid = identity.clinic_id
        payload = {"order_id": order_id, "attempt_id": interrupted_attempt_id}
        async with self._pool.acquire() as conn, conn.transaction():
            await _doi_quyen_lam(conn, identity, QUYEN_LAM_LAI)
            don, vid = await self._khoa_don(conn, cid, order_id)
            await doi_quyen(conn, identity, QUYEN_LAM_LAI, phong_id=don["room_id"])
            cached = await bien_nhan_doc(
                conn, identity, "service.retry", idempotency_key, payload
            )
            if cached is not None:
                return cached
            # Quyền theo lịch: phải đang có ca ở phòng của chỉ định (dây nối).
            await doi_lich_phong(
                conn,
                self._pool,
                identity,
                don["room_id"],
                ngay_cu=bool(don["la_ngay_cu"]),
            )

            self._doi_revision(don, expected_execution_revision, "execution_revision")
            if don["execution_status"] != "INTERRUPTED":
                raise LuotKhamConflictError(
                    "EXECUTION_STATE_INVALID", "Chỉ định không đang ở trạng thái dừng."
                )
            lan_cuoi = await conn.fetchrow(
                "SELECT id::text, attempt_no, status FROM service_execution_attempt"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                " ORDER BY attempt_no DESC LIMIT 1",
                cid,
                order_id,
            )
            if lan_cuoi is None or lan_cuoi["id"] != interrupted_attempt_id:
                raise LuotKhamConflictError(
                    "EXECUTION_ATTEMPT_NOT_ACTIVE",
                    "Lần làm này không phải lần bị dừng gần nhất.",
                )

            # Về PENDING chứ không phải "WAITING": chờ làm là thứ tính ra, và
            # lúc này chỉ định lại đủ điều kiện để ai đó bấm Bắt đầu.
            moi = await self._doi_trang_thai(conn, cid, order_id, "PENDING")
            # Khách hiện lại ở hàng chờ của phòng (V4 — kiểm 30/09/2026): Dừng
            # đã đóng chỗ chờ ('done'), trước bản này Làm lại để nguyên nên
            # màn phòng xếp khách vào nhóm "đã xong".
            await ve_lai_hang_phong(conn, cid, vid, order_id, don["room_id"])
            await cap_nhat_vi_tri(conn, cid, vid)
            await emit_event(
                conn,
                ten="service.retry_prepared",
                clinic_id=cid,
                aggregate_id=order_id,
                so_ke_tiep=True,  # một dãy số cho cả chỉ định (emit.py)
                payload=DichVuSanSangLamLai(
                    visit_id=vid,
                    service_order_id=order_id,
                    attempt_id=interrupted_attempt_id,
                    execution_revision=moi,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            ket_qua = {
                "ok": True,
                "order_id": order_id,
                "execution_status": "PENDING",
                "cho_lam": True,
                "execution_revision": moi,
                "ghi_chu": ghi_chu,
            }
            await bien_nhan_ghi(
                conn, identity, "service.retry", idempotency_key, payload, vid, ket_qua
            )
        return ket_qua

    # ------------------------------------------------------------------
    async def huy_bat_dau(
        self,
        *,
        order_id: str,
        attempt_id: str,
        expected_execution_revision: int,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """`CancelMistakenStart` — bấm Bắt đầu nhầm khách / nhầm dịch vụ (V4).

        Chỉ khi lần làm đang chạy và CHƯA điền phiếu kết quả. Một giao dịch:
        lần làm → INTERRUPTED lý do STARTED_IN_ERROR (không xoá: vẫn đọc được là
        đã có lần bấm), chỉ định → PENDING, khách về lại hàng chờ của phòng,
        các chỗ "đợi quay lại" của lượt mở ra, con trỏ "khách đang ở đâu" dời.

        Ai có lego Bắt đầu ở phòng này thì huỷ được ("mở hết", Tuyền 30/09):
        người bấm nhầm tự sửa ngay, không phải đi tìm trưởng ca.
        """
        cid = identity.clinic_id
        payload = {"order_id": order_id, "attempt_id": attempt_id}
        async with self._pool.acquire() as conn, conn.transaction():
            await _doi_quyen_lam(conn, identity, QUYEN_BAT_DAU)
            don, vid = await self._khoa_don(conn, cid, order_id)
            await doi_quyen(conn, identity, QUYEN_BAT_DAU, phong_id=don["room_id"])
            cached = await bien_nhan_doc(
                conn, identity, "service.start_cancel", idempotency_key, payload
            )
            if cached is not None:
                return cached
            # Quyền theo lịch: phải đang có ca ở phòng của chỉ định (dây nối).
            await doi_lich_phong(
                conn,
                self._pool,
                identity,
                don["room_id"],
                ngay_cu=bool(don["la_ngay_cu"]),
            )

            self._doi_revision(don, expected_execution_revision, "execution_revision")
            if don["execution_status"] != "IN_PROGRESS":
                raise LuotKhamConflictError(
                    "EXECUTION_STATE_INVALID", "Chỉ định không đang được làm."
                )
            lan = await self._lan_dang_chay(conn, cid, order_id, attempt_id)
            if await conn.fetchval(_PHIEU_DA_DIEN_SQL, cid, order_id):
                raise LuotKhamConflictError(
                    "RESULT_FORM_STARTED",
                    "Đã điền phiếu kết quả — không huỷ bắt đầu được nữa."
                    " Làm tiếp rồi Hoàn tất, hoặc nhờ trưởng ca chuyển phòng.",
                )

            await conn.execute(
                "UPDATE service_execution_attempt"
                "   SET status = 'INTERRUPTED', interrupted_by = $3::uuid,"
                "       interrupted_at = now(), interruption_reason_code = $4,"
                "       updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                lan["id"],
                identity.staff_id,
                LY_DO_BAT_DAU_NHAM,
            )
            moi = await self._doi_trang_thai(conn, cid, order_id, "PENDING")
            await ve_lai_hang_phong(conn, cid, vid, order_id, don["room_id"])
            await mo_cho_bi_chan(conn, cid, vid)
            await cap_nhat_vi_tri(conn, cid, vid)

            await emit_event(
                conn,
                ten="service.start_cancelled",
                clinic_id=cid,
                aggregate_id=order_id,
                so_ke_tiep=True,  # một dãy số cho cả chỉ định (emit.py)
                payload=DichVuDaHuyBatDau(
                    visit_id=vid,
                    service_order_id=order_id,
                    attempt_id=lan["id"],
                    attempt_no=lan["attempt_no"],
                    room_id=str(don["room_id"]) if don["room_id"] else None,
                    execution_revision=moi,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            ket_qua = {
                "ok": True,
                "order_id": order_id,
                "attempt_id": lan["id"],
                "execution_status": "PENDING",
                "cho_lam": True,
                "execution_revision": moi,
            }
            await bien_nhan_ghi(
                conn,
                identity,
                "service.start_cancel",
                idempotency_key,
                payload,
                vid,
                ket_qua,
            )
        return ket_qua

    # ------------------------------------------------------------------
    async def hoan_tac_xong_tai_quay(
        self,
        *,
        order_id: str,
        expected_execution_revision: int,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
        nguon: str = "hoan_tac",
    ) -> dict[str, Any]:
        """`ReopenDeskCompletedService` — hoàn tác dịch vụ QUẦY đã đóng (01/10/2026).

        Làm thêm tại quầy: Hoàn tất phiếu kết quả ở Đo sinh hiệu / Tiếp đón =
        dịch vụ xong (`xong` kèm dấu `GHI_CHU_TAI_QUAY`). Sửa lại / Hoàn tác kết
        quả thì dịch vụ trở về ĐÚNG trạng thái trước đó: chờ làm, khách hiện lại
        ở hàng chờ của phòng. Một giao dịch: lần làm → INTERRUPTED lý do
        RESULT_UNDONE (không xoá), chỉ định → PENDING, hàng chờ phòng dựng lại,
        con trỏ "khách ở đâu" dời, phát `service.retry_prepared`.

        CHỈ lần làm do quầy đóng; dịch vụ phòng làm xong thì lệnh này từ chối.
        `nguon` ("hoan_tac" | "sua_lai") ghi vào lần làm để [Huỷ sửa] biết có phải
        chính lần Sửa lại đã mở dịch vụ không (hoàn tác tường minh thì [Huỷ sửa]
        KHÔNG đóng lại).
        """
        cid = identity.clinic_id
        payload = {"order_id": order_id}
        async with self._pool.acquire() as conn, conn.transaction():
            await _doi_quyen_lam(conn, identity, QUYEN_XONG)
            don, vid = await self._khoa_don(conn, cid, order_id)
            await doi_quyen(conn, identity, QUYEN_XONG, phong_id=don["room_id"])
            cached = await bien_nhan_doc(
                conn, identity, "service.desk_reopen", idempotency_key, payload
            )
            if cached is not None:
                return cached
            await doi_lich_phong(
                conn,
                self._pool,
                identity,
                don["room_id"],
                ngay_cu=bool(don["la_ngay_cu"]),
            )
            self._doi_revision(don, expected_execution_revision, "execution_revision")
            if don["execution_status"] != "COMPLETED":
                raise LuotKhamConflictError(
                    "EXECUTION_STATE_INVALID", "Dịch vụ chưa được đóng."
                )
            lan = await conn.fetchrow(
                "SELECT id::text, attempt_no, ghi_chu FROM service_execution_attempt"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                " ORDER BY attempt_no DESC LIMIT 1 FOR UPDATE",
                cid,
                order_id,
            )
            if lan is None or lan["ghi_chu"] != GHI_CHU_TAI_QUAY:
                raise LuotKhamConflictError(
                    "NOT_DESK_COMPLETED",
                    "Dịch vụ này do phòng làm xong — hoàn tác ở phòng.",
                )
            await conn.execute(
                "UPDATE service_execution_attempt"
                "   SET status = 'INTERRUPTED', completed_by = NULL,"
                "       completed_at = NULL, interrupted_by = $3::uuid,"
                "       interrupted_at = now(), interruption_reason_code = $4,"
                "       interruption_reason_note = $5, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                lan["id"],
                identity.staff_id,
                LY_DO_HOAN_TAC_XONG,
                nguon,
            )
            moi = await self._doi_trang_thai(conn, cid, order_id, "PENDING")
            await ve_lai_hang_phong(conn, cid, vid, order_id, don["room_id"])
            await cap_nhat_vi_tri(conn, cid, vid)
            await emit_event(
                conn,
                ten="service.retry_prepared",
                clinic_id=cid,
                aggregate_id=order_id,
                so_ke_tiep=True,
                payload=DichVuSanSangLamLai(
                    visit_id=vid,
                    service_order_id=order_id,
                    attempt_id=lan["id"],
                    execution_revision=moi,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            ket_qua = {
                "ok": True,
                "order_id": order_id,
                "execution_status": "PENDING",
                "cho_lam": True,
                "execution_revision": moi,
            }
            await bien_nhan_ghi(
                conn,
                identity,
                "service.desk_reopen",
                idempotency_key,
                payload,
                vid,
                ket_qua,
            )
        return ket_qua

    # ------------------------------------------------------------------
    # LÀM TẠI BÀN KHÁM (Tuyền chốt 07/10/2026) — bốn lệnh song song với lệnh
    # của phòng, KHÔNG đổi hành vi đường phòng / quầy.
    # ------------------------------------------------------------------
    async def bat_dau_tai_ban_kham(
        self,
        *,
        order_id: str,
        expected_execution_revision: int,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """`StartServiceAtDesk` — bác sĩ làm chỉ định NGAY tại bàn khám.

        Khác `bat_dau` (phòng): quyền khối y khoa ở bàn khám (không phải lego +
        ca ở phòng của chỉ định); không đòi đã xếp phòng; KHÔNG đụng chỗ chờ
        'serving' của phiên bác sĩ — khách vẫn ngồi ở bàn khám, và Postgres chỉ
        cho MỘT chỗ 'serving' mỗi lượt (`uq_queue_entry_one_serving`). Chỗ chờ ở
        phòng (nếu đã xếp) → 'blocked' (khách đang ở chỗ khác); Xong đóng nó.

        GIỐNG `bat_dau` ở cửa tiền: CÙNG FinanceGate (`can_start` / `cua_lam`,
        dây ``thu_truoc_khi_lam``). Chỉ định khách chưa chốt mà lượt được làm khi
        chưa thu (tick "Làm trước – thu sau", hoặc dây tắt) → chốt như lúc tick
        (`lam_truoc_thu_sau._chot_cho_quyet` — bác sĩ làm = khách đồng ý).
        """
        cid = identity.clinic_id
        payload = {"order_id": order_id, "exec_rev": expected_execution_revision}
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_mot_quyen(
                conn, identity, QUYEN_LAM_TAI_BAN_KHAM, cau=CAU_KHONG_QUYEN_BAN_KHAM
            )
            don, vid = await self._khoa_don_ban_kham(conn, cid, order_id)
            cached = await bien_nhan_doc(
                conn, identity, "service.start_desk", idempotency_key, payload
            )
            if cached is not None:
                return cached
            self._doi_revision(don, expected_execution_revision, "execution_revision")
            if don["execution_status"] not in (None, "PENDING"):
                raise LuotKhamConflictError(
                    "EXECUTION_STATE_INVALID",
                    f"Chỉ định đang ở trạng thái {don['execution_status']}.",
                )
            if await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM service_execution_attempt"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                "   AND status = 'IN_PROGRESS')",
                cid,
                order_id,
            ):
                raise LuotKhamConflictError(
                    "EXECUTION_ALREADY_RUNNING", "Đang có một lần làm chạy dở."
                )
            chot = await self._cua_tien_ban_kham(conn, identity, vid, order_id)

            lan_truoc = await conn.fetchval(
                "SELECT COALESCE(max(attempt_no), 0) FROM service_execution_attempt"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid",
                cid,
                order_id,
            )
            phong = await conn.fetchval(
                _PHONG_BAN_KHAM_SQL, cid, vid, identity.staff_id
            )
            # Chỉ định CHƯA có phòng → xếp vào phòng bàn khám (nơi làm thật).
            # Cột cũ `exec_status` in_progress/performed BẮT BUỘC có phòng (CHECK
            # service_order_room_when_assigned), và công nợ check-out / vòng đọc /
            # theo dõi thủ thuật còn đọc cột cũ: không có phòng thì dịch vụ đã
            # làm vẫn bị coi là "chưa làm" — khách về không bị nhắc nợ.
            gan_phong = don["room_id"] is None
            if gan_phong:
                if phong is None:
                    raise LuotKhamConflictError(
                        "DESK_ROOM_UNKNOWN", CAU_CHUA_BIET_PHONG_BAN_KHAM
                    )
                rev_xep = await conn.fetchval(
                    "UPDATE service_order"
                    "   SET room_id = $3::uuid, routing_status = 'ASSIGNED',"
                    "       routing_nguon = 'khac', assigned_by = $4::uuid,"
                    "       assigned_at = now(),"
                    "       routing_revision = routing_revision + 1,"
                    "       updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid"
                    " RETURNING routing_revision",
                    cid,
                    order_id,
                    phong,
                    identity.staff_id,
                )
                # Đổi cột xếp phòng = một mốc thật trong sổ (không cái gì sau
                # đè cái trước): `v_moc_hanh_trinh` đọc thành XEP_PHONG.
                await emit_event(
                    conn,
                    ten="service.routed",
                    clinic_id=cid,
                    aggregate_id=order_id,
                    so_ke_tiep=True,
                    payload=DaXepPhong(
                        visit_id=vid,
                        service_order_id=order_id,
                        room_id=str(phong),
                        routing_revision=int(rev_xep),
                        ly_do="INITIAL_ASSIGNMENT",
                        nguon=NGUON_BAN_KHAM,
                    ),
                    boi=nguoi(identity),
                    correlation_id=vid,
                )
            lan = await conn.fetchrow(
                """
                INSERT INTO service_execution_attempt
                    (clinic_id, service_order_id, attempt_no, room_id_snapshot,
                     routing_revision_snapshot, status, started_by, started_at,
                     noi_lam, gan_phong_ban_kham, chot_lua_chon_tu,
                     chot_lua_chon_rev)
                VALUES ($1::uuid, $2::uuid, $3, $4::uuid, $5, 'IN_PROGRESS',
                        $6::uuid, now(), $7, $8, $9, $10)
                RETURNING id::text, attempt_no, started_at
                """,
                cid,
                order_id,
                int(lan_truoc) + 1,
                phong,
                int(don["routing_revision"] or 0),
                identity.staff_id,
                NOI_BAN_KHAM,
                gan_phong,
                chot[0] if chot else None,
                chot[1] if chot else None,
            )
            moi = await self._doi_trang_thai(conn, cid, order_id, "IN_PROGRESS")
            await conn.execute(
                "UPDATE queue_entry SET status = 'blocked',"
                "       version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND ref_id = $2::uuid"
                "   AND reason = 'SERVICE' AND status IN ('waiting', 'called')",
                cid,
                order_id,
            )
            await cap_nhat_vi_tri(conn, cid, vid)
            await emit_event(
                conn,
                ten="service.started",
                clinic_id=cid,
                aggregate_id=order_id,
                so_ke_tiep=True,
                payload=DichVuDaBatDau(
                    visit_id=vid,
                    service_order_id=order_id,
                    attempt_id=lan["id"],
                    attempt_no=lan["attempt_no"],
                    room_id=phong,
                    execution_revision=moi,
                    noi_lam=NOI_BAN_KHAM,
                    chot_lua_chon=chot is not None,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            ket_qua = {
                "ok": True,
                "order_id": order_id,
                "attempt_id": lan["id"],
                "attempt_no": lan["attempt_no"],
                "execution_status": "IN_PROGRESS",
                "execution_revision": moi,
                "noi_lam": NOI_BAN_KHAM,
                "started_at": lan["started_at"].isoformat(),
            }
            await bien_nhan_ghi(
                conn,
                identity,
                "service.start_desk",
                idempotency_key,
                payload,
                vid,
                ket_qua,
            )
        return ket_qua

    async def xong_tai_ban_kham(
        self,
        *,
        order_id: str,
        attempt_id: str,
        expected_execution_revision: int,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """`CompleteServiceAtDesk` — lần làm tại bàn khám xong. Chỉ đóng lần làm
        do bàn khám mở (lần làm ở phòng thì bấm Xong ở phòng)."""
        cid = identity.clinic_id
        payload = {"order_id": order_id, "attempt_id": attempt_id}
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_mot_quyen(
                conn, identity, QUYEN_LAM_TAI_BAN_KHAM, cau=CAU_KHONG_QUYEN_BAN_KHAM
            )
            don, vid = await self._khoa_don_ban_kham(conn, cid, order_id)
            cached = await bien_nhan_doc(
                conn, identity, "service.complete_desk", idempotency_key, payload
            )
            if cached is not None:
                return cached
            self._doi_revision(don, expected_execution_revision, "execution_revision")
            if don["execution_status"] != "IN_PROGRESS":
                raise LuotKhamConflictError(
                    "EXECUTION_STATE_INVALID", "Chỉ định không đang được làm."
                )
            lan = await self._lan_ban_kham(conn, cid, order_id, attempt_id)
            await conn.execute(
                "UPDATE service_execution_attempt"
                "   SET status = 'COMPLETED', completed_by = $3::uuid,"
                "       completed_at = now(), updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                lan["id"],
                identity.staff_id,
            )
            moi = await self._doi_trang_thai(
                conn, cid, order_id, "COMPLETED", nguoi_lam=identity.staff_id
            )
            await self._dong_hang_cho(conn, cid, order_id)
            await cap_nhat_vi_tri(conn, cid, vid)
            await emit_event(
                conn,
                ten="service.completed",
                clinic_id=cid,
                aggregate_id=order_id,
                so_ke_tiep=True,
                payload=DichVuDaXong(
                    visit_id=vid,
                    service_order_id=order_id,
                    attempt_id=lan["id"],
                    attempt_no=lan["attempt_no"],
                    execution_revision=moi,
                    noi_lam=NOI_BAN_KHAM,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            ket_qua = {
                "ok": True,
                "order_id": order_id,
                "attempt_id": lan["id"],
                "execution_status": "COMPLETED",
                "execution_revision": moi,
            }
            await bien_nhan_ghi(
                conn,
                identity,
                "service.complete_desk",
                idempotency_key,
                payload,
                vid,
                ket_qua,
            )
        return ket_qua

    async def huy_bat_dau_tai_ban_kham(
        self,
        *,
        order_id: str,
        attempt_id: str,
        expected_execution_revision: int,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """Hoàn tác [Làm tại bàn khám] — cùng nghĩa `huy_bat_dau` (lần làm →
        INTERRUPTED lý do STARTED_IN_ERROR, không xoá; chỉ định → chờ làm; chỗ
        chờ ở phòng mở lại). KHÁC: phiếu đã ghi KHÔNG chặn — ở bàn khám phiếu ghi
        được trước cả khi làm, và hoàn tác không đụng phiếu. Không đụng tiền."""
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_mot_quyen(
                conn, identity, QUYEN_LAM_TAI_BAN_KHAM, cau=CAU_KHONG_QUYEN_BAN_KHAM
            )
            don, vid = await self._khoa_don_ban_kham(conn, cid, order_id)
            if don["execution_status"] in (None, "PENDING"):
                return {"ok": True, "order_id": order_id, "already": True}
            self._doi_revision(don, expected_execution_revision, "execution_revision")
            if don["execution_status"] != "IN_PROGRESS":
                raise LuotKhamConflictError(
                    "EXECUTION_STATE_INVALID", "Chỉ định không đang được làm."
                )
            lan = await self._lan_ban_kham(conn, cid, order_id, attempt_id)
            await conn.execute(
                "UPDATE service_execution_attempt"
                "   SET status = 'INTERRUPTED', interrupted_by = $3::uuid,"
                "       interrupted_at = now(), interruption_reason_code = $4,"
                "       updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                lan["id"],
                identity.staff_id,
                LY_DO_BAT_DAU_NHAM,
            )
            moi = await self._doi_trang_thai(conn, cid, order_id, "PENDING")
            if lan["gan_phong_ban_kham"]:
                # Gỡ đúng phòng bàn khám đã xếp lúc Bắt đầu: chỉ định về "chưa
                # xếp" để quầy / tự xếp đưa vào phòng làm thật (cột cũ về
                # authorized cùng câu — CHECK đòi phòng cho 'assigned').
                rev_go = await conn.fetchval(
                    "UPDATE service_order"
                    "   SET room_id = NULL, routing_status = 'UNASSIGNED',"
                    "       exec_status = 'authorized', routing_nguon = NULL,"
                    "       assigned_by = NULL, assigned_at = NULL,"
                    "       routing_revision = routing_revision + 1,"
                    "       updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid"
                    " RETURNING routing_revision",
                    cid,
                    order_id,
                )
                # Mốc gỡ phòng (XEP_PHONG của lần Bắt đầu → bị hoàn tác). Lý do
                # riêng: bên Trách nhiệm không mở việc "xếp lại phòng".
                await emit_event(
                    conn,
                    ten="service.routing_invalidated",
                    clinic_id=cid,
                    aggregate_id=order_id,
                    so_ke_tiep=True,
                    payload=XepPhongDaHuy(
                        visit_id=vid,
                        service_order_id=order_id,
                        from_room_id=lan["room_id"],
                        routing_revision=int(rev_go),
                        ly_do=LY_DO_HUY_LAM_BAN_KHAM,
                    ),
                    boi=nguoi(identity),
                    correlation_id=vid,
                )
            elif don["room_id"] is not None:
                await ve_lai_hang_phong(conn, cid, vid, order_id, str(don["room_id"]))
            # Lần làm đã chốt hộ lựa chọn của khách → trả về đúng như trước
            # (khi chưa ai chốt lại lượt sau đó — không đè người sau).
            tra_ve: str | None = None
            if lan["chot_lua_chon_tu"] is not None:
                from clinicai.services.lam_truoc_thu_sau import tra_lua_chon_chot_ho

                if await tra_lua_chon_chot_ho(
                    conn,
                    identity,
                    vid,
                    order_id,
                    ve=str(lan["chot_lua_chon_tu"]),
                    rev_sau_chot=int(lan["chot_lua_chon_rev"] or 0),
                ):
                    tra_ve = str(lan["chot_lua_chon_tu"])
            await cap_nhat_vi_tri(conn, cid, vid)
            await emit_event(
                conn,
                ten="service.start_cancelled",
                clinic_id=cid,
                aggregate_id=order_id,
                so_ke_tiep=True,
                payload=DichVuDaHuyBatDau(
                    visit_id=vid,
                    service_order_id=order_id,
                    attempt_id=lan["id"],
                    attempt_no=lan["attempt_no"],
                    room_id=lan["room_id"],
                    execution_revision=moi,
                    noi_lam=NOI_BAN_KHAM,
                    tra_lua_chon_ve=tra_ve,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
        return {
            "ok": True,
            "order_id": order_id,
            "execution_status": "PENDING",
            "execution_revision": moi,
        }

    async def hoan_tac_xong_tai_ban_kham(
        self,
        *,
        order_id: str,
        expected_execution_revision: int,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """Hoàn tác [Xong] của lần làm tại bàn khám — cùng nghĩa
        `UndoServiceCompletion` (lần làm về đang làm, mốc "khám xong hẳn" mở lại
        nếu chính lần Xong ấy khép lượt). Khách vẫn ở bàn khám: không dựng lại
        chỗ chờ phòng thành 'đang làm'. Không đụng tiền, không đụng phiếu."""
        from clinicai.events.catalogue import DichVuHoanTacXong
        from clinicai.services.hoan_tac_service import mo_lai_moc_kham_xong
        from clinicai.services.luot_kham_service import LuotKhamService

        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_mot_quyen(
                conn, identity, QUYEN_LAM_TAI_BAN_KHAM, cau=CAU_KHONG_QUYEN_BAN_KHAM
            )
            don, vid = await self._khoa_don_ban_kham(conn, cid, order_id)
            if don["execution_status"] == "IN_PROGRESS":
                return {"ok": True, "order_id": order_id, "already": True}
            self._doi_revision(don, expected_execution_revision, "execution_revision")
            if don["execution_status"] != "COMPLETED":
                raise LuotKhamConflictError(
                    "EXECUTION_NOT_COMPLETED",
                    "Dịch vụ này chưa ở trạng thái “Đã xong”.",
                )
            lan = await conn.fetchrow(
                "SELECT id::text, attempt_no, noi_lam FROM service_execution_attempt"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                "   AND status = 'COMPLETED'"
                " ORDER BY attempt_no DESC LIMIT 1 FOR UPDATE",
                cid,
                order_id,
            )
            if lan is None or lan["noi_lam"] != NOI_BAN_KHAM:
                raise LuotKhamConflictError(
                    "NOT_DESK_EXAM_COMPLETED",
                    "Dịch vụ này do phòng làm xong — hoàn tác ở phòng.",
                )
            await conn.execute(
                "UPDATE service_execution_attempt"
                "   SET status = 'IN_PROGRESS', completed_by = NULL,"
                "       completed_at = NULL, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                lan["id"],
            )
            moi = await self._doi_trang_thai(conn, cid, order_id, "IN_PROGRESS")
            # Chỗ chờ ở phòng (nếu có) về lại "đợi" — khách đang ở bàn khám.
            await conn.execute(
                "UPDATE queue_entry SET status = 'blocked', done_at = NULL,"
                "       version = version + 1, updated_at = now()"
                " WHERE id = (SELECT q.id FROM queue_entry q"
                "              WHERE q.clinic_id = $1::uuid AND q.ref_id = $2::uuid"
                "                AND q.reason = 'SERVICE' AND q.status = 'done'"
                "              ORDER BY q.updated_at DESC LIMIT 1)"
                "   AND NOT EXISTS (SELECT 1 FROM queue_entry s"
                "                WHERE s.clinic_id = $1::uuid"
                "                  AND s.ref_id = $2::uuid AND s.reason = 'SERVICE'"
                "                  AND s.status NOT IN ('done', 'left', 'cancelled'))",
                cid,
                order_id,
            )
            luot = LuotKhamService(pool=None)
            await luot._evaluate_rounds(conn, identity, vid)
            mo_moc = await mo_lai_moc_kham_xong(conn, cid, vid)
            if mo_moc and await luot._ket_thuc_neu_xong(conn, identity, vid):
                mo_moc = False
            await cap_nhat_vi_tri(conn, cid, vid)
            await emit_event(
                conn,
                ten="service.completion_undone",
                clinic_id=cid,
                aggregate_id=order_id,
                so_ke_tiep=True,
                payload=DichVuHoanTacXong(
                    visit_id=vid,
                    service_order_id=order_id,
                    attempt_id=lan["id"],
                    attempt_no=int(lan["attempt_no"]),
                    execution_revision=moi,
                    mo_lai_kham_xong=mo_moc,
                    noi_lam=NOI_BAN_KHAM,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
        return {
            "ok": True,
            "order_id": order_id,
            "attempt_id": lan["id"],
            "execution_status": "IN_PROGRESS",
            "execution_revision": moi,
        }

    @staticmethod
    async def _lan_ban_kham(
        conn: asyncpg.Connection, clinic_id: str, order_id: str, attempt_id: str
    ) -> asyncpg.Record:
        """Lần làm đang chạy, đúng lần người bấm thấy, và do BÀN KHÁM mở."""
        lan = await conn.fetchrow(
            "SELECT id::text, attempt_no, noi_lam, gan_phong_ban_kham,"
            "       chot_lua_chon_tu, chot_lua_chon_rev,"
            "       room_id_snapshot::text AS room_id"
            "  FROM service_execution_attempt"
            " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
            "   AND id = $3::uuid AND status = 'IN_PROGRESS' FOR UPDATE",
            clinic_id,
            order_id,
            attempt_id,
        )
        if lan is None:
            raise LuotKhamConflictError(
                "EXECUTION_ATTEMPT_NOT_ACTIVE",
                "Lần làm này không còn đang chạy — tải lại màn hình.",
            )
        if lan["noi_lam"] != NOI_BAN_KHAM:
            raise LuotKhamConflictError(
                "NOT_DESK_EXAM_ATTEMPT",
                "Dịch vụ đang làm ở phòng — bấm Xong / huỷ ở phòng.",
            )
        return lan

    @staticmethod
    async def _cua_tien_ban_kham(
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        visit_id: str,
        order_id: str,
    ) -> tuple[str, int] | None:
        """Cửa tiền của [Làm tại bàn khám] (luật: `cua_tien_ban_kham`). Phải chốt
        lựa chọn trước → chốt "khách làm" cho ĐÚNG chỉ định này (bác sĩ làm =
        khách đồng ý chỉ định ấy; chỉ định khác chờ khách quyết KHÔNG bị chốt
        theo) rồi hỏi lại. Trả (lựa chọn trước, revision sau chốt) nếu đã chốt
        hộ — lần làm ghi lại để hoàn tác trả về."""
        cid = identity.clinic_id
        tien = await can_start(conn, cid, order_id)
        sel = await conn.fetchval(
            "SELECT selection_status FROM service_order"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid",
            cid,
            order_id,
        )
        chua_thu = (await duoc_lam_khi_chua_thu(conn, cid, [visit_id])).get(
            visit_id, False
        )
        duoc, cau, chot = cua_tien_ban_kham(
            tien, selection_status=sel, duoc_chua_thu=chua_thu
        )
        da_chot: tuple[str, int] | None = None
        if chot:
            from clinicai.services.lam_truoc_thu_sau import chot_mot_chi_dinh

            da_chot = await chot_mot_chi_dinh(conn, identity, visit_id, order_id)
            tien = await can_start(conn, cid, order_id)
            if tien is not None and tien.finance_state == finance_gate.NOT_APPLICABLE:
                raise LuotKhamConflictError(
                    "FINANCE_NOT_READY",
                    "Chưa chốt được dịch vụ cho khách — chốt ở quầy thu rồi làm.",
                )
            duoc, cau, _ = cua_tien_ban_kham(
                tien, selection_status="SELECTED", duoc_chua_thu=chua_thu
            )
        if not duoc:
            raise LuotKhamConflictError(
                "FINANCE_NOT_READY", cau or finance_gate.CAU_CHUA_THU
            )
        return da_chot

    # ------------------------------------------------------------------
    # Nhìn (chỉ đọc)
    # ------------------------------------------------------------------
    async def xem(self, *, order_id: str, identity: StaffIdentity) -> dict[str, Any]:
        """Màn phòng cần gì để bấm được 5 lệnh — trả đúng ngần ấy, không hơn.

        Không kiểm quyền ghi ở đây: đọc trạng thái một chỉ định trong phòng
        mình đang trực không phải hành động nguy hiểm, và **ẩn nút không phải
        bảo mật** — từng lệnh vẫn tự hỏi capability của nó khi bấm.

        Hai `revision` là thứ khiến màn này không phải đoán: bấm kèm số nào
        đang thấy, máy chủ so lại, lệch thì từ chối thay vì ghi đè người khác.
        """
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            don = await conn.fetchrow(
                # KHÔNG có `billing_status`: tiền là thứ SUY RA từ sổ thanh
                # toán (FinanceGate), không phải một cột trên chỉ định. Hỏi cột
                # ấy là hỏi một sự thật thứ hai về tiền — và hai sự thật về
                # tiền thì sớm muộn lệch nhau.
                "SELECT so.id::text AS order_id, so.service_code, so.service_name,"
                "       so.selection_status, so.routing_status,"
                "       so.execution_status, so.execution_revision,"
                "       so.routing_revision, so.room_id::text AS room_id,"
                "       so.visit_id::text AS visit_id,"
                # Đầu dịch vụ ở phòng (27/09/2026 — bản mẫu): mã phòng khám
                # (mã SP KiotViet) · giá bảng giá. Giá chỉ để NHÌN — tiền
                # thật vẫn đọc ở sổ thanh toán.
                "       sp.ma_kiotviet, sp.unit_price AS gia"
                "  FROM service_order so"
                "  LEFT JOIN LATERAL ("
                "       SELECT s.ma_kiotviet, s.unit_price FROM service_price s"
                "        WHERE s.clinic_id = so.clinic_id"
                "          AND s.service_code = so.service_code"
                "        ORDER BY s.active DESC LIMIT 1) sp ON true"
                " WHERE so.clinic_id = $1::uuid AND so.id = $2::uuid",
                cid,
                order_id,
            )
            if don is None:
                raise ValidationError("Không tìm thấy chỉ định này.")

            lan = await conn.fetch(
                "SELECT a.id::text, a.attempt_no, a.status,"
                "       a.started_at, a.completed_at, a.interrupted_at,"
                "       a.interruption_reason_code, a.noi_lam,"
                "       nb.full_name AS bat_dau_boi, nx.full_name AS xong_boi"
                "  FROM service_execution_attempt a"
                "  LEFT JOIN staff nb ON nb.id = a.started_by"
                "  LEFT JOIN staff nx ON nx.id = a.completed_by"
                " WHERE a.clinic_id = $1::uuid AND a.service_order_id = $2::uuid"
                " ORDER BY a.attempt_no",
                cid,
                order_id,
            )
            from clinicai.services.nhan_tai_phong import ban_kham_dang_lam

            ban_kham = (await ban_kham_dang_lam(conn, cid, [order_id])).get(order_id)
            # Mẫu đã gắn → dùng; chưa gắn → mẫu gợi ý của phiếu v5 chọn sẵn +
            # 18 mẫu dự phòng (23/09 khuya: phòng siêu âm mở ra là điền được).
            mau, mau_goi_y = await mau_cho_dich_vu(
                conn, clinic_id=cid, service_code=don["service_code"]
            )
            # READY TRƯỚC (27/09/2026, đợt 3 — B11): màn phòng mở lại khách lấy
            # `phieu[0]` làm mẫu chọn sẵn. Xếp theo giờ tạo thì phiếu nháp cũ
            # (mẫu chọn sẵn lúc mới mở khách) đứng đầu → mở lại ra phiếu nháp
            # thay vì phiếu đã Hoàn tất. Cùng thứ tự với khối 2
            # (`ket_qua_chi_dinh`): hoàn tất mới nhất trước, rồi mới tạo trước.
            phieu = await conn.fetch(
                "SELECT id::text, form_id, trang_thai, revision, hoan_tat_luc"
                "  FROM form_instance"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                " ORDER BY (trang_thai = 'READY') DESC,"
                "          hoan_tat_luc DESC NULLS LAST, tao_luc DESC",
                cid,
                order_id,
            )

        dang_chay = next((d for d in lan if d["status"] == "IN_PROGRESS"), None)
        # Lần làm do BÀN KHÁM mở (07/10/2026): không phải việc của phòng — màn
        # phòng không có Xong / Gián đoạn / Huỷ (lệnh phòng cũng từ chối), chỉ
        # nói "đang làm ở bàn khám BS …".
        if dang_chay is not None and dang_chay["noi_lam"] == NOI_BAN_KHAM:
            dang_chay = None
        cuoi = lan[-1] if lan else None
        return {
            **{k: don[k] for k in don.keys()},
            "gia": int(don["gia"]) if don["gia"] is not None else None,
            "lan_dang_chay": dict(dang_chay) if dang_chay is not None else None,
            "lam_o_ban_kham": ban_kham,
            # Làm lại phải chỉ đúng lần đã dừng — màn không được tự đoán.
            "lan_da_dung": (
                dict(cuoi)
                if cuoi is not None and cuoi["status"] == "INTERRUPTED"
                else None
            ),
            "cac_lan": [dict(d) for d in lan],
            "mau_ket_qua": mau,
            "mau_goi_y": mau_goi_y,
            "phieu": [dict(d) for d in phieu],
            # Dịch vụ đã đóng mà phiếu kết quả chưa ai Hoàn tất (chỉ có nháp):
            # màn phòng hiện chip nhắc — bản in lúc này vẫn ghi BẢN NHÁP.
            "phieu_chua_hoan_tat": phieu_chua_hoan_tat(
                don["execution_status"], [d["trang_thai"] for d in phieu]
            ),
            # Nút "Huỷ bắt đầu nhầm" (V4, 30/09/2026) — máy chủ quyết.
            "huy_bat_dau_duoc": huy_bat_dau_duoc(
                don["execution_status"],
                dang_chay is not None,
                [(d["trang_thai"], d["revision"]) for d in phieu],
            ),
            "ly_do_khong_lam": sorted(LY_DO_KHONG_LAM),
            "ly_do_gian_doan": sorted(LY_DO_GIAN_DOAN),
        }

    # ------------------------------------------------------------------
    # Dùng chung
    # ------------------------------------------------------------------
    @staticmethod
    async def _khoa_don(
        conn: asyncpg.Connection, clinic_id: str, order_id: str
    ) -> tuple[asyncpg.Record, str]:
        """Khoá lượt rồi khoá chỉ định — luôn cùng thứ tự, để không kẹt nhau."""
        vid = await luot_cua(conn, "service_order", clinic_id, order_id)
        # Khách về giữa chừng (INCOMPLETE) vẫn làm / sửa được (Tuyền 29/09/2026:
        # "ngày cũ sửa được hết") — mỗi lệnh ghi sự kiện `service.*` của nó.
        await khoa_luot(conn, clinic_id, vid, cho_phep_ve_giua_chung=True)
        # `la_ngay_cu`: lượt check-in trước hôm nay → không đòi đang có ca ở
        # phòng (quyền theo lịch chỉ áp cho HÔM NAY — `doi_lich_phong`).
        don = await conn.fetchrow(
            "SELECT o.id::text, o.selection_status, o.routing_status,"
            "       o.execution_status, o.execution_revision, o.routing_revision,"
            "       o.room_id,"
            "       coalesce((v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
            "                < (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date,"
            "                false) AS la_ngay_cu"
            "  FROM service_order o"
            "  JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id"
            " WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid FOR UPDATE OF o",
            clinic_id,
            order_id,
        )
        if don is None:
            raise ValidationError("Không tìm thấy chỉ định này.")
        return don, vid

    @classmethod
    async def _khoa_don_ban_kham(
        cls, conn: asyncpg.Connection, clinic_id: str, order_id: str
    ) -> tuple[asyncpg.Record, str]:
        """`_khoa_don` + lượt còn mở (chưa check-out) — kiểm SAU khi khoá lượt,
        trong giao dịch: check-out chen giữa lần kiểm ngoài và lệnh không lọt."""
        don, vid = await cls._khoa_don(conn, clinic_id, order_id)
        luot = await conn.fetchrow(
            "SELECT status, closed_at FROM visit"
            " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
            clinic_id,
            vid,
        )
        if (
            luot is None
            or luot["closed_at"] is not None
            or luot["status"] not in ("OPEN", "IN_PROGRESS")
        ):
            raise LuotKhamConflictError("VISIT_CHECKED_OUT", CAU_LUOT_DA_DONG)
        return don, vid

    async def _ghi_xong(
        self,
        conn: asyncpg.Connection,
        cid: str,
        vid: str,
        order_id: str,
        lan: asyncpg.Record,
        identity: StaffIdentity,
        ghi: str | None,
    ) -> int:
        """Lần làm ``lan`` xong: đóng lần làm, chỉ định COMPLETED, đóng chỗ chờ,
        phát `service.completed`. Người gọi đã khoá + kiểm quyền. Trả revision."""
        await conn.execute(
            "UPDATE service_execution_attempt"
            "   SET status = 'COMPLETED', completed_by = $3::uuid,"
            "       completed_at = now(), updated_at = now(),"
            "       ghi_chu = coalesce($4, ghi_chu)"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid",
            cid,
            lan["id"],
            identity.staff_id,
            ghi,
        )
        moi = await self._doi_trang_thai(
            conn, cid, order_id, "COMPLETED", nguoi_lam=identity.staff_id
        )
        await self._dong_hang_cho(conn, cid, order_id)
        await emit_event(
            conn,
            ten="service.completed",
            clinic_id=cid,
            aggregate_id=order_id,
            so_ke_tiep=True,  # một dãy số cho cả chỉ định (emit.py)
            payload=DichVuDaXong(
                visit_id=vid,
                service_order_id=order_id,
                attempt_id=lan["id"],
                attempt_no=lan["attempt_no"],
                execution_revision=moi,
            ),
            boi=nguoi(identity),
            correlation_id=vid,
        )
        return moi

    async def _xong_cung_phong(
        self,
        conn: asyncpg.Connection,
        clinic_id: str,
        visit_id: str,
        order_id: str,
        giu: asyncpg.Record,
        don: asyncpg.Record,
        identity: StaffIdentity,
        *,
        xong_truoc: bool,
    ) -> None:
        """Khách đang làm DV1 ở CHÍNH phòng này lúc bấm Bắt đầu DV2 (07/10/2026).

        Không phải "khách ở phòng khác" — không nhận chéo, không đóng hàng, không
        nhãn đỏ. Chưa bấm nút → 409 CUNG_PHONG_DANG_LAM kèm tên DV1 để màn hỏi
        tại chỗ. Bấm [Xong DV1 & bắt đầu DV2] (`xong_truoc`) → cùng giao dịch Xong
        DV1 (sự kiện `service.completed` thật, người bấm) rồi Bắt đầu DV2. Không
        bao giờ tự Xong khi người dùng chưa bấm."""
        dv1 = giu["service_name"] or "Dịch vụ đang làm"
        oid = giu["order_id"]
        if not xong_truoc:
            dv2 = await conn.fetchval(
                "SELECT service_name FROM service_order"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                clinic_id,
                order_id,
            )
            raise LuotKhamConflictError(
                "CUNG_PHONG_DANG_LAM",
                f"{dv1} đang làm — Xong {dv1} rồi bắt đầu {dv2 or 'dịch vụ này'}?",
                {
                    "ma": "CUNG_PHONG_DANG_LAM",
                    "dich_vu": dv1,
                    "dich_vu_moi": dv2,
                    "order_id": oid,
                },
            )
        await doi_quyen(conn, identity, QUYEN_XONG, phong_id=don["room_id"])
        o = await conn.fetchrow(
            "SELECT execution_status FROM service_order"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
            clinic_id,
            oid,
        )
        lan = await conn.fetchrow(
            "SELECT id::text, attempt_no FROM service_execution_attempt"
            " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
            "   AND status = 'IN_PROGRESS' FOR UPDATE",
            clinic_id,
            oid,
        )
        if o is None or o["execution_status"] != "IN_PROGRESS" or lan is None:
            raise LuotKhamConflictError(
                "VERSION_CONFLICT", f"{dv1} không còn đang làm — tải lại rồi bấm."
            )
        await self._ghi_xong(conn, clinic_id, visit_id, oid, lan, identity, None)

    async def _giai_phong_khach(
        self,
        conn: asyncpg.Connection,
        clinic_id: str,
        visit_id: str,
        order_id: str,
        don: asyncpg.Record,
        identity: StaffIdentity,
        *,
        giai_phong: bool,
        xong_truoc: bool = False,
    ) -> None:
        """Khách đang làm dịch vụ KHÁC ở phòng khác lúc bấm Bắt đầu (V4).

        Trước 30/09/2026: 409 PATIENT_BUSY cứng — phòng kia phải bấm Xong hay
        Dừng trước (prod 29/09: 23 lần/ngày, khách đứng ở cửa phòng chờ người
        phòng bên cạnh quay lại màn hình). Nay:

          * chưa đồng ý (`giai_phong=False`) → vẫn 409 PATIENT_BUSY, nhưng kèm
            `chi_tiet` = tên phòng đang giữ khách + `chuyen_duoc` để màn hỏi
            "Khách đang ở phòng X — chuyển sang đây?";
          * đồng ý → trong CÙNG giao dịch với lần Bắt đầu này: lần làm ở phòng
            kia → INTERRUPTED lý do PATIENT_MOVED, chỉ định kia → PENDING, chỗ
            chờ của nó về hàng phòng kia (lần Bắt đầu ngay sau đặt nó "đợi quay
            lại" như mọi chỗ chờ khác của lượt), sự kiện `service.patient_moved`.

        CHẶN chuyển khi phòng kia đã điền phiếu kết quả (`phieu_da_dien`):
        chuyển đi là bỏ dở công người vừa gõ. Phòng kia Hoàn tất / Xong trước.
        Không đòi thêm quyền ở phòng kia — "mở hết" (Tuyền 30/09/2026): ai có
        lego Bắt đầu ở phòng này thì nhận khách được.
        """
        giu = await conn.fetchrow(
            "SELECT q.ref_id::text AS order_id, q.room_id::text AS room_id,"
            "       r.name AS ten_phong, o.service_name"
            "  FROM queue_entry q"
            "  LEFT JOIN clinic_room r"
            "    ON r.id = q.room_id AND r.clinic_id = q.clinic_id"
            "  LEFT JOIN service_order o"
            "    ON o.id = q.ref_id AND o.clinic_id = q.clinic_id"
            " WHERE q.clinic_id = $1::uuid AND q.visit_id = $2::uuid"
            "   AND q.status = 'serving' AND q.reason = 'SERVICE'"
            "   AND q.ref_id <> $3::uuid",
            clinic_id,
            visit_id,
            order_id,
        )
        if giu is None:
            return
        if don["room_id"] is not None and giu["room_id"] == str(don["room_id"]):
            await self._xong_cung_phong(
                conn,
                clinic_id,
                visit_id,
                order_id,
                giu,
                don,
                identity,
                xong_truoc=xong_truoc,
            )
            return
        ten = giu["ten_phong"] or "khác"
        # Dây Nhận tại phòng BẬT (07/10/2026): phòng kia KHÔNG bị dừng hộ — đóng
        # hàng chờ phòng kia, lần làm của nó giữ mở (phòng ấy tự Xong / Gián
        # đoạn), nên không có công ai bị bỏ dở và không chặn vì phiếu đã điền.
        tai_phong = bool(await doc_day(conn, clinic_id, "nhan_tai_phong"))
        da_dien = not tai_phong and bool(
            await conn.fetchval(_PHIEU_DA_DIEN_SQL, clinic_id, giu["order_id"])
        )
        chi_tiet = {
            "ma": "PATIENT_BUSY",
            "phong": ten,
            "dich_vu": giu["service_name"],
            "chuyen_duoc": not da_dien,
        }
        if da_dien:
            raise LuotKhamConflictError(
                "PATIENT_BUSY",
                f"Khách đang làm dịch vụ ở phòng {ten} và phòng đó đã điền phiếu"
                " kết quả — phòng đó Hoàn tất / bấm Xong trước rồi mới chuyển"
                " khách sang đây được.",
                chi_tiet,
            )
        if not giai_phong:
            raise LuotKhamConflictError(
                "PATIENT_BUSY",
                f"Khách đang làm dịch vụ ở phòng {ten}.",
                chi_tiet,
            )

        if tai_phong:
            from clinicai.services.nhan_tai_phong import NHA_NHAN_CHEO, roi_phong

            cho = await conn.fetch(
                "SELECT id::text AS id, ref_id::text AS ref_id, room_id::text"
                " AS room_id, status FROM queue_entry WHERE clinic_id = $1::uuid"
                " AND visit_id = $2::uuid AND reason = 'SERVICE' AND status = 'serving'"
                " AND ref_id <> $3::uuid",
                clinic_id,
                visit_id,
                order_id,
            )
            await roi_phong(
                conn,
                identity,
                vid=visit_id,
                cho=cho,
                ly_do=NHA_NHAN_CHEO,
                sang_room_id=str(don["room_id"]) if don["room_id"] else None,
            )
            return
        oid = giu["order_id"]
        o = await conn.fetchrow(
            "SELECT execution_status, execution_revision FROM service_order"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
            clinic_id,
            oid,
        )
        phong_nay = await conn.fetchval(
            "SELECT name FROM clinic_room WHERE clinic_id = $1::uuid AND id = $2::uuid",
            clinic_id,
            don["room_id"],
        )
        lan = await conn.fetchrow(
            "SELECT id::text, attempt_no FROM service_execution_attempt"
            " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
            "   AND status = 'IN_PROGRESS' FOR UPDATE",
            clinic_id,
            oid,
        )
        if lan is not None:
            await conn.execute(
                "UPDATE service_execution_attempt"
                "   SET status = 'INTERRUPTED', interrupted_by = $3::uuid,"
                "       interrupted_at = now(), interruption_reason_code = $4,"
                "       interruption_reason_note = $5, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                clinic_id,
                lan["id"],
                identity.staff_id,
                LY_DO_CHUYEN_KHACH,
                f"Khách chuyển sang phòng {phong_nay or 'khác'}",
            )
        rev = int((o["execution_revision"] if o is not None else 0) or 0)
        if o is not None and o["execution_status"] == "IN_PROGRESS":
            rev = await self._doi_trang_thai(conn, clinic_id, oid, "PENDING")
        await ve_lai_hang_phong(conn, clinic_id, visit_id, oid, giu["room_id"])
        await emit_event(
            conn,
            ten="service.patient_moved",
            clinic_id=clinic_id,
            aggregate_id=oid,
            so_ke_tiep=True,  # một dãy số cho cả chỉ định (emit.py)
            payload=KhachDaChuyenPhong(
                visit_id=visit_id,
                service_order_id=oid,
                attempt_id=lan["id"] if lan is not None else None,
                attempt_no=int(lan["attempt_no"]) if lan is not None else None,
                from_room_id=giu["room_id"],
                to_room_id=str(don["room_id"]) if don["room_id"] else None,
                to_service_order_id=order_id,
                execution_revision=rev,
            ),
            boi=nguoi(identity),
            correlation_id=visit_id,
        )

    @staticmethod
    def _doi_revision(don: asyncpg.Record, mong_doi: int, cot: str) -> None:
        """Màn đang mở có còn khớp hiện trạng không."""
        hien = int(don[cot] or 0)
        if hien != mong_doi:
            raise LuotKhamConflictError(
                "VERSION_CONFLICT",
                f"Màn hình đã cũ ({cot} {mong_doi} ≠ {hien}) — tải lại rồi bấm.",
            )

    @staticmethod
    async def _lan_dang_chay(
        conn: asyncpg.Connection, clinic_id: str, order_id: str, attempt_id: str
    ) -> asyncpg.Record:
        """Lần làm đang chạy, và phải đúng lần mà người bấm đang nhìn.

        Request cũ của lần làm trước tới muộn thì dừng ở đây, không đóng nhầm
        lần làm mới.
        """
        lan = await conn.fetchrow(
            "SELECT id::text, attempt_no, noi_lam FROM service_execution_attempt"
            " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
            "   AND id = $3::uuid AND status = 'IN_PROGRESS' FOR UPDATE",
            clinic_id,
            order_id,
            attempt_id,
        )
        if lan is None:
            raise LuotKhamConflictError(
                "EXECUTION_ATTEMPT_NOT_ACTIVE",
                "Lần làm này không còn đang chạy — tải lại màn hình.",
            )
        # Lần làm do BÀN KHÁM mở (07/10/2026): phòng của chỉ định không Xong /
        # Gián đoạn / Huỷ hộ — bàn khám đóng nó ở hồ sơ khám.
        if lan["noi_lam"] == NOI_BAN_KHAM:
            raise LuotKhamConflictError("DANG_LAM_BAN_KHAM", CAU_DANG_LAM_BAN_KHAM)
        return lan

    @staticmethod
    async def _doi_trang_thai(
        conn: asyncpg.Connection,
        clinic_id: str,
        order_id: str,
        trang_thai: str,
        *,
        ly_do: str | None = None,
        nguoi_lam: str | None = None,
    ) -> int:
        """Đổi `execution_status`; cột cũ `exec_status` + giờ bắt đầu/xong do
        trigger `service_order_dong_bo_trang_thai` (migration 20260924000011)
        suy ra — mọi lối ghi (kể cả đối tác lấy mẫu) khớp ở một chỗ.

        Bấm thật 23/09 22:00: phòng bấm Xong mà Bàn khám vẫn "Chờ ở phòng" vì
        nhiều màn/view còn đọc cột cũ — lý do phải có bản chiếu này.
        """
        moi = await conn.fetchval(
            "UPDATE service_order"
            "   SET execution_status = $3, execution_revision = execution_revision + 1,"
            "       not_performed_reason = CASE WHEN $3 = 'NOT_PERFORMED'"
            "         THEN coalesce(nullif(btrim(coalesce($4, '')), ''),"
            "                       not_performed_reason)"
            "         ELSE not_performed_reason END,"
            "       performed_by = CASE WHEN $3 = 'COMPLETED'"
            "         THEN coalesce($5::uuid, performed_by) ELSE performed_by END,"
            "       updated_at = now()"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid"
            " RETURNING execution_revision",
            clinic_id,
            order_id,
            trang_thai,
            ly_do,
            nguoi_lam,
        )
        return int(moi)

    @staticmethod
    async def _dong_hang_cho(
        conn: asyncpg.Connection, clinic_id: str, order_id: str
    ) -> None:
        """Đóng chỗ chờ của chỉ định này; các chỗ chờ khác của lượt mở lại.

        Khách rời phòng → quay lại hàng bác sĩ chính (và các phòng khác đang
        đợi), tính giờ từ lúc quay lại — "đợi quay lại" của `bat_dau` kết thúc
        ở đây (Tuyền 23/09/2026).
        """
        vid = await conn.fetchval(
            "SELECT visit_id::text FROM service_order"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid",
            clinic_id,
            order_id,
        )
        dong = await conn.execute(
            "UPDATE queue_entry SET status = 'done', done_at = now(),"
            "       version = version + 1, updated_at = now()"
            " WHERE clinic_id = $1::uuid AND ref_id = $2::uuid AND reason = 'SERVICE'"
            "   AND status NOT IN ('done', 'left', 'cancelled')",
            clinic_id,
            order_id,
        )
        if dong == "UPDATE 0":
            # Nhận chéo (07/10/2026): khách đã sang phòng khác, chỗ chờ ở phòng
            # này đã đóng lúc khách rời ('cancelled', mốc ở sự kiện
            # `service.room_released`) mà lần làm còn mở. Phòng bấm Xong muộn
            # → chỗ ấy thành "đã xong" với giờ bấm — mốc rời phòng vẫn riêng.
            await conn.execute(
                """
                UPDATE queue_entry q SET status = 'done', done_at = now(),
                       version = q.version + 1, updated_at = now()
                  FROM service_order o
                 WHERE q.clinic_id = $1::uuid AND q.ref_id = $2::uuid
                   AND q.reason = 'SERVICE' AND q.status = 'cancelled'
                   AND o.clinic_id = q.clinic_id AND o.id = q.ref_id
                   AND o.room_id = q.room_id
                   AND q.id = (SELECT q2.id FROM queue_entry q2
                                WHERE q2.clinic_id = q.clinic_id
                                  AND q2.reason = 'SERVICE' AND q2.ref_id = q.ref_id
                                ORDER BY q2.updated_at DESC LIMIT 1)
                """,
                clinic_id,
                order_id,
            )
        if vid is not None:
            await mo_cho_bi_chan(conn, clinic_id, vid)


__all__ = [
    "LY_DO_GIAN_DOAN",
    "LY_DO_KHONG_LAM",
    "QUYEN_BAT_DAU",
    "QUYEN_GIAN_DOAN",
    "QUYEN_KHONG_LAM",
    "QUYEN_LAM_LAI",
    "QUYEN_XONG",
    "ServiceExecutionService",
]
