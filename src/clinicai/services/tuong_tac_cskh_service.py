"""Sổ tương tác CSKH — ghi lại từng lần chạm tới khách, và đọc lại nó.

VÌ SAO CÓ FILE NÀY. Nút "📞 Gọi nhắc hẹn" trên màn Quản lý khách hàng là một
thẻ `<a href="tel:…">`: nó quay số rồi thôi. Gọi xong không ai biết đã gọi, gọi
lần hai không ai biết là lần hai, và ba cột "Tương tác gần nhất / Bước tiếp
theo / Hạn xử lý" hiện "—" cho mọi khách.

Sổ này CHỈ THÊM. Không có hàm sửa, không có hàm xoá: một cuộc gọi đã xảy ra thì
đã xảy ra, và bản ghi sai được sửa bằng cách ghi thêm một dòng nói rõ, không
phải bằng cách viết lại quá khứ.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, cast

import asyncpg
import structlog

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import CLINIC_TZ as GIO_VN

logger = structlog.get_logger()


class _BorrowedConnection:
    """Expose one acquired connection without releasing it on nested services."""

    def __init__(self, connection: asyncpg.Connection) -> None:
        self._connection = connection

    async def __aenter__(self) -> asyncpg.Connection:
        return self._connection

    async def __aexit__(self, *_args: object) -> None:
        return None


class _ConnectionBoundPool:
    """Pool-shaped view that keeps collaborating services in one transaction.

    BookingService and CheckoutService normally acquire their own connections
    and therefore commit independently. During CSKH checkout both must borrow
    the already-acquired connection so their nested transactions are savepoints
    under one outer transaction.
    """

    def __init__(self, connection: asyncpg.Connection) -> None:
        self._connection = connection

    def acquire(self) -> _BorrowedConnection:
        return _BorrowedConnection(self._connection)

    async def fetchval(self, query: str, *args: Any) -> Any:
        return await self._connection.fetchval(query, *args)


#: Mốc tại quầy (20260809000007) — việc XẢY RA, không phải cuộc gọi. Hai mốc
#: đầu còn đổi trạng thái lịch hẹn thật: check-in mở lượt khám, check-out đóng.
MOC_QUAY = frozenset({"CHECK_IN", "CHECK_OUT", "THANH_TOAN", "MUA_THUOC"})

#: Loại việc — khớp CHECK trong 20260809000003 + 20260809000007.
LOAI_HOP_LE = (
    frozenset(
        {
            "XAC_NHAN_LICH",
            "NHAC_HEN",
            "CHECK_XN",
            "TRA_KQ",
            "HOI_LY_DO_HUY",
            "HOI_THAM",
            "KHAC",
        }
    )
    | MOC_QUAY
)
#: Loại việc luôn nói về MỘT lịch hẹn cụ thể. Check-in/check-out có mặt vì
#: chúng đổi trạng thái của chính lịch đó.
CAN_LICH_HEN = frozenset(
    {"XAC_NHAN_LICH", "NHAC_HEN", "HOI_LY_DO_HUY", "CHECK_IN", "CHECK_OUT"}
)
KENH_HOP_LE = frozenset({"GOI", "ZALO", "SMS", "TRUC_TIEP", "KHONG_LIEN_HE"})
#: KNM = CHUA_NGHE_MAY, KLLD = KHONG_LIEN_LAC_DUOC, Hẹn GLS = HEN_GOI_LAI
#: (Quang giải nghĩa 08/08/2026). Cả ba sinh ra việc "cần gọi lại".
KET_QUA_HOP_LE = frozenset(
    {
        "DA_LIEN_HE",
        "CHUA_NGHE_MAY",
        "KHONG_LIEN_LAC_DUOC",
        "HEN_GOI_LAI",
        "CAN_BAC_SI",
        "TU_CHOI",
        "BO_QUA",
        # Mốc quầy chỉ có "đã xảy ra" — cho nó mượn DA_LIEN_HE là bịa ra một
        # cuộc gọi chưa từng có.
        "GHI_NHAN",
    }
)


class TuongTacCskhService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def ghi(
        self,
        *,
        identity: StaffIdentity,
        clinic_patient_id: str,
        loai: str,
        kenh: str,
        ket_qua: str,
        appointment_id: str | None = None,
        khach_xac_nhan: bool | None = None,
        noi_dung: str | None = None,
        trang_thai_ma: str | None = None,
    ) -> dict[str, Any]:
        """Ghi một lần chạm tới khách. Trả về id dòng vừa ghi."""
        if loai not in LOAI_HOP_LE:
            raise ValidationError(f"Loại tương tác không hợp lệ: {loai!r}.")
        if kenh not in KENH_HOP_LE:
            raise ValidationError(f"Kênh không hợp lệ: {kenh!r}.")
        if ket_qua not in KET_QUA_HOP_LE:
            raise ValidationError(f"Kết quả không hợp lệ: {ket_qua!r}.")
        if loai == "TRA_KQ" and ket_qua != "DA_LIEN_HE":
            # View hiện coi MỌI dòng TRA_KQ là đóng KQ_CHUA_GUI, không xét kết
            # quả cuộc gọi. Cho một lần gọi hụt mang loại ấy sẽ làm việc biến
            # mất. Gọi hụt vẫn có thể ghi vào sổ bằng loại KHAC; TRA_KQ được
            # dành riêng cho bằng chứng đã trả thành công.
            raise ValidationError(
                "Chỉ ghi 'trả kết quả' khi đã liên hệ và gửi thành công. "
                "Lần gọi chưa thành công hãy ghi là tương tác khác."
            )
        # Nói ra ở đây bằng tiếng Việt thay vì để CHECK của Postgres nổ thành
        # một lỗi 500 mà người dùng không đọc được.
        if (ket_qua == "BO_QUA") != (kenh == "KHONG_LIEN_HE"):
            raise ValidationError(
                "'Bỏ qua' phải đi cùng 'không liên hệ' — và ngược lại."
            )
        if (loai in MOC_QUAY) != (ket_qua == "GHI_NHAN"):
            raise ValidationError(
                "Mốc tại quầy ghi kết quả 'ghi nhận' — và chỉ mốc quầy mới dùng nó."
            )
        if loai in MOC_QUAY and kenh != "TRUC_TIEP":
            raise ValidationError("Mốc tại quầy luôn là kênh trực tiếp.")
        if khach_xac_nhan is not None and loai not in ("XAC_NHAN_LICH", "NHAC_HEN"):
            raise ValidationError(
                "Chỉ việc xác nhận lịch / nhắc hẹn mới ghi được 'khách xác nhận'."
            )
        if loai in CAN_LICH_HEN and not appointment_id:
            raise ValidationError("Việc này phải gắn với một lịch hẹn cụ thể.")

        # Mọi kiểm tra ownership phải xong TRƯỚC side effect. Đặc biệt CHECK_IN,
        # CHECK_OUT và Zalo có thể đổi lịch/gửi tin ra ngoài; kiểm sau đó thì
        # request 422 vẫn có thể đã làm hỏng lịch của một khách khác.
        ok = await self._pool.fetchval(
            "SELECT 1 FROM public.patient "
            " WHERE clinic_patient_id = $1::uuid AND clinic_id = $2::uuid",
            clinic_patient_id,
            identity.clinic_id,
        )
        if not ok:
            raise NotFoundError("Không tìm thấy khách hàng này.")
        if appointment_id:
            thuoc_ve = await self._pool.fetchval(
                "SELECT 1 FROM public.appointment "
                " WHERE id = $1::uuid AND clinic_id = $2::uuid "
                "   AND clinic_patient_id = $3::uuid",
                appointment_id,
                identity.clinic_id,
                clinic_patient_id,
            )
            if not thuoc_ve:
                raise ValidationError("Lịch hẹn không phải của khách này.")

        # CHECK-IN VÀ CHECK-OUT LÀ HÀNH ĐỘNG THẬT TRÊN LỊCH HẸN, không chỉ là
        # dòng sổ. Đi qua đúng máy trạng thái (BookingService.apply_action):
        # check-in mở lượt khám và đưa khách vào hàng đợi tiếp nhận — y như lễ
        # tân bấm; check-out đóng trạng thái khám, thứ mà "đã khám" và nhắc tái
        # khám đọc vào.
        #
        # CHẠY TRƯỚC khi ghi sổ: hành động lịch thất bại (khách chưa check-in mà
        # bấm check-out) thì KHÔNG được để lại dòng sổ nói việc đã xảy ra. Chiều
        # ngược lại — hành động xong mà ghi sổ hỏng — chấp nhận được: trạng thái
        # lịch vẫn đúng và chuỗi bước vẫn tích qua trạng thái.
        if loai in ("CHECK_IN", "CHECK_OUT") and appointment_id:
            da_doi = await self._doi_trang_thai_lich(
                identity=identity, appointment_id=appointment_id, loai=loai
            )
            if not da_doi:
                # Mốc đã được vai khác thực hiện. Không tạo một dòng no-op có
                # nút Hoàn tác, vì nó có thể đảo transition thật của người đó.
                return {"ok": True, "already_applied": True, "id": None}

        # ĐÁNH DẤU "ĐÃ TRẢ KẾT QUẢ" KHÔNG CÒN ĐÒI BẰNG CHỨNG TỆP ĐÃ GỬI.
        #
        # Tuyền chốt 14/08/2026: *"mình đang chỉ cần CSKH và quản lý hệ thống
        # dùng thôi nên là tick là được… mình cần lưu lại lịch sử mà, có lịch sử
        # là coi như làm rồi"*.
        #
        # Bản trước chặn hai bước "Đã có kết quả, chưa gửi" và "Đã gọi trả kết
        # quả xét nghiệm" cho tới khi có một dòng `tep_ket_qua` với `gui_luc`
        # muộn hơn kết quả xét nghiệm mới nhất. Luật ấy được viết cho một thế
        # giới đã có luồng tải ảnh/video lên rồi gửi cho khách — mà chính màn
        # hình đang nói "video đang xây dựng". Nên chốt đòi một điều kiện KHÔNG
        # CÁCH NÀO đạt được: cùng họ với "phải ghi lý do ngoại lệ" ở màn không
        # có ô nhập lý do, và cùng họ với ba nút Kết thúc lượt khám vừa vá.
        #
        # SỔ CHĂM SÓC CHÍNH LÀ BẰNG CHỨNG, ở quy mô hiện tại. Mỗi lần bấm ghi
        # một dòng có người, có giờ, có nội dung, và hoàn tác được — đủ để truy
        # lại ai đã nói gì với khách. Đó là thứ phòng khám cần lúc này.
        #
        # KHI NÀO DỰNG LẠI CHỐT NÀY: lúc luồng tải tệp chạy thật và CSKH gửi
        # ảnh/phiếu qua hệ thống thay vì qua Zalo cá nhân. Toàn bộ hạ tầng còn
        # nguyên — bảng `tep_ket_qua`, `TepKetQuaService`, và khoá theo bệnh
        # nhân `ket_qua_patient_lock_key` — nên khôi phục là chép lại đúng khối
        # truy vấn đã gỡ ở commit này, không phải viết lại từ đầu.
        #
        # Luật CÒN GIỮ: `TRA_KQ` vẫn bắt buộc `ket_qua = "DA_LIEN_HE"` (kiểm ở
        # đầu hàm). Một cuộc gọi hụt vẫn không được mang nhãn đã trả kết quả —
        # đó là chuyện khác, và nó không đòi hỏi gì người dùng không làm được.
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row_id = await conn.fetchval(
                    """
                    INSERT INTO public.tuong_tac_cskh
                        (clinic_id, clinic_patient_id, appointment_id, loai, kenh,
                         ket_qua, khach_xac_nhan, noi_dung, nhan_vien_staff_id,
                         trang_thai_ma)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8,
                            $9::uuid, $10)
                    RETURNING id::text
                    """,
                    identity.clinic_id,
                    clinic_patient_id,
                    appointment_id,
                    loai,
                    kenh,
                    ket_qua,
                    khach_xac_nhan,
                    (noi_dung or "").strip() or None,
                    identity.staff_id,
                    (trang_thai_ma or "").strip() or None,
                )
                await conn.execute(
                    """
                    INSERT INTO public.event_log
                        (clinic_id, event_type, aggregate_type, aggregate_id,
                         payload, source, occurred_at)
                    VALUES ($1::uuid, 'cskh.tuong_tac', 'patient', $2::uuid,
                            jsonb_build_object('loai', $3::text, 'kenh', $4::text,
                                               'ket_qua', $5::text,
                                               'by_staff_id', $6::text),
                            'cskh.customers', now())
                    """,
                    identity.clinic_id,
                    clinic_patient_id,
                    loai,
                    kenh,
                    ket_qua,
                    identity.staff_id,
                )

        logger.info(
            "cskh_tuong_tac_ghi",
            loai=loai,
            kenh=kenh,
            ket_qua=ket_qua,
            by_staff_id=identity.staff_id,
        )
        return {"ok": True, "id": row_id}

    async def ghi_ly_do_hoan_tac(
        self, *, identity: StaffIdentity, tuong_tac_id: str, ly_do: str
    ) -> dict[str, Any]:
        """Ghi lý do làm lại — SAU hoàn tác, tuỳ chọn (Đặng Dương 17/08/2026).

        Hoàn tác giữ nguyên một-cú-bấm (Quang 10/08: không hộp xác nhận);
        đây là chỗ cho người cần báo cáo. Chỉ nhận vào dòng ĐÃ hoàn tác —
        "lý do làm lại" trên một dòng còn hiệu lực là câu vô nghĩa."""
        chu = ly_do.strip()
        if not chu:
            raise ValidationError("Lý do trống thì không có gì để ghi.")
        if len(chu) > 500:
            raise ValidationError("Lý do dài quá 500 ký tự.")
        da_ghi = await self._pool.fetchval(
            """
            UPDATE public.tuong_tac_cskh
               SET ly_do_hoan_tac = $3
             WHERE id = $1::uuid AND clinic_id = $2::uuid
               AND huy_luc IS NOT NULL
            RETURNING id
            """,
            tuong_tac_id,
            identity.clinic_id,
            chu,
        )
        if da_ghi is None:
            raise NotFoundError("Không tìm thấy thao tác đã hoàn tác nào để ghi lý do.")
        return {"ok": True}

    async def hoan_tac(
        self, *, identity: StaffIdentity, tuong_tac_id: str
    ) -> dict[str, Any]:
        """Rút lại một lần chạm bấm nhầm — KHÔNG xoá dòng sổ.

        Quang 10/08/2026: *"hoàn tác lại tác vụ đó… tất nhiên là log không được
        xoá"*. Dòng ở lại, chỉ thôi được tính (`huy_luc`), và view bỏ qua nó —
        xem migration 20260810000009.

        HOÀN TÁC KHÔNG CHỈ LÀ MỘT LÁ CỜ. Hai mốc quầy còn ĐỔI TRẠNG THÁI LỊCH
        HẸN thật, nên rút lại dòng sổ mà để lịch nguyên trạng là nói dối theo
        chiều ngược lại: sổ bảo chưa check-in, lịch hẹn vẫn CHECKED_IN.

            CHECK_IN   đảo được — `undo_checkin` đưa CHECKED_IN về CONFIRMED,
                       và nó huỷ luôn các bước còn mở của lượt khám
                       (`_WORKFLOW_CANCELLING`).
            CHECK_OUT  KHÔNG đảo được. Máy trạng thái không có đường nào ra khỏi
                       COMPLETED (`booking_service.TRANSITIONS`), và đó là chủ ý:
                       "đã khám xong" là mốc nhiều thứ khác đọc vào (nhắc tái
                       khám, thu tiền, hồ sơ). Từ chối ở đây kèm câu chỉ đường,
                       thay vì âm thầm gỡ cờ và để lịch hẹn nói một đằng sổ nói
                       một nẻo.
        """
        row = await self._pool.fetchrow(
            "SELECT id::text, loai, appointment_id::text AS appt, huy_luc, "
            "       clinic_patient_id::text AS bn "
            "  FROM public.tuong_tac_cskh "
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            tuong_tac_id,
            identity.clinic_id,
        )
        if row is None:
            raise NotFoundError("Không tìm thấy thao tác này.")
        if row["huy_luc"] is not None:
            # Hai người cùng bấm, hoặc bấm lại sau khi mạng lag. Không phải lỗi.
            return {"ok": True, "da_hoan_tac_truoc_do": True}

        if row["loai"] == "CHECK_OUT":
            raise ValidationError(
                "Không hoàn tác được lần đóng lượt khám. Lượt đã COMPLETED và "
                "máy trạng thái không có đường quay lại — nhờ Quản lý mở lại "
                "lượt, hoặc đặt một lịch mới cho khách."
            )

        if row["loai"] == "CHECK_IN" and row["appt"]:
            from clinicai.services.booking_service import BookingService

            trang_thai = await self._pool.fetchval(
                "SELECT status FROM public.appointment "
                " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                row["appt"],
                identity.clinic_id,
            )
            if trang_thai == "COMPLETED":
                raise ValidationError(
                    "Khách đã khám xong rồi, không rút lại check-in được nữa."
                )
            if trang_thai != "CHECKED_IN":
                raise ValidationError(
                    "Lịch không còn ở trạng thái CHECKED_IN nên không thể "
                    "hoàn tác mốc check-in này."
                )
            da_tien = await self._pool.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                      FROM public.visit v
                      JOIN public.work_item w
                        ON w.visit_id = v.visit_id AND w.clinic_id = v.clinic_id
                     WHERE v.appointment_id = $1::uuid
                       AND v.clinic_id = $2::uuid
                       AND w.node_code <> 'LUOTKHAM-01'
                       -- Trạm đầu được tự mở IN_PROGRESS ngay lúc check-in;
                       -- đó chưa phải tiến triển của người dùng. Chỉ một bước
                       -- phía sau đã COMPLETED mới làm undo trở nên nguy hiểm.
                       AND w.status = 'COMPLETED'
                )
                """,
                row["appt"],
                identity.clinic_id,
            )
            if da_tien:
                raise ValidationError(
                    "Khách đã tiếp tục quy trình sau check-in; không thể hoàn tác "
                    "từ màn CSKH. Nhờ Quản lý xử lý lượt khám."
                )
            await BookingService(self._pool).apply_action(
                appointment_id=row["appt"],
                action="undo_checkin",
                identity=identity,
            )

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE public.tuong_tac_cskh "
                    "   SET huy_luc = now(), huy_boi_staff_id = $2::uuid "
                    " WHERE id = $1::uuid AND huy_luc IS NULL",
                    tuong_tac_id,
                    identity.staff_id,
                )
                # Hoàn tác cũng là một sự kiện. Sổ nói "đã bấm rồi rút lại", và
                # `event_log` nói ai rút — hai thứ khác nhau, cần cả hai.
                await conn.execute(
                    """
                    INSERT INTO public.event_log
                        (clinic_id, event_type, aggregate_type, aggregate_id,
                         payload, source, occurred_at)
                    VALUES ($1::uuid, 'cskh.tuong_tac_hoan_tac', 'patient',
                            $5::uuid, jsonb_build_object(
                                'tuong_tac_id', $2::text,
                                'loai', $3::text,
                                'by_staff_id', $4::text),
                            'cskh.customers', now())
                    """,
                    identity.clinic_id,
                    tuong_tac_id,
                    row["loai"],
                    identity.staff_id,
                    # `aggregate_id` là NOT NULL — tôi để NULL ở bản đầu và mọi
                    # cú hoàn tác trả 500 với "null value in column
                    # aggregate_id". Câu `ghi()` ngay bên trên đã dùng đúng
                    # `clinic_patient_id` cho cột này; chép sai một tham số là
                    # đủ. Sự kiện hoàn tác thuộc về CHÍNH bệnh nhân ấy, y như
                    # sự kiện ghi.
                    row["bn"],
                )

        logger.info(
            "cskh_tuong_tac_hoan_tac",
            tuong_tac_id=tuong_tac_id,
            loai=row["loai"],
            by_staff_id=identity.staff_id,
        )
        return {"ok": True}

    async def _doi_trang_thai_lich(
        self, *, identity: StaffIdentity, appointment_id: str, loai: str
    ) -> bool:
        """Chạy hành động lịch tương ứng với mốc quầy — nếu lịch đang ở chỗ cần nó.

        Đã CHECKED_IN mà bấm check-in lần nữa (lễ tân làm trước rồi) thì chỉ ghi
        sổ, không phải lỗi. Nhưng khách CHƯA đến mà bấm check-out thì là lỗi
        thật, và câu báo phải nói được điều đó.
        """
        from clinicai.services.booking_service import BookingService

        if loai == "CHECK_OUT":
            return await self._checkout_atomically(
                identity=identity, appointment_id=appointment_id
            )

        row = await self._pool.fetchrow(
            "SELECT status FROM public.appointment "
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            appointment_id,
            identity.clinic_id,
        )
        if row is None:
            raise NotFoundError("Không tìm thấy lịch hẹn này.")
        status = row["status"]

        if loai == "CHECK_IN":
            if status in ("CHECKED_IN", "COMPLETED"):
                return False
            if status not in ("SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"):
                raise ValidationError(
                    f"Lịch đang ở trạng thái {status}, không check-in được."
                )
            await BookingService(self._pool).apply_action(
                appointment_id=appointment_id, action="checkin", identity=identity
            )
            return True

        raise ValidationError(f"Mốc quầy không hợp lệ: {loai!r}.")

    async def _checkout_atomically(
        self, *, identity: StaffIdentity, appointment_id: str
    ) -> bool:
        """Close visit + complete appointment on one connection/transaction."""
        from clinicai.services.booking_service import BookingService

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT status FROM public.appointment "
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid FOR UPDATE",
                    appointment_id,
                    identity.clinic_id,
                )
                if row is None:
                    raise NotFoundError("Không tìm thấy lịch hẹn này.")
                status = row["status"]
                if status == "COMPLETED":
                    return False
                if status != "CHECKED_IN":
                    raise ValidationError(
                        "Khách chưa check-in — check-in trước rồi mới check-out được."
                    )

                bound_pool = cast(asyncpg.Pool, _ConnectionBoundPool(conn))
                await self._dong_luot_kham(
                    identity=identity,
                    appointment_id=appointment_id,
                    pool=bound_pool,
                )
                await BookingService(bound_pool).apply_action(
                    appointment_id=appointment_id,
                    action="complete",
                    identity=identity,
                )
        return True

    async def _dong_luot_kham(
        self,
        *,
        identity: StaffIdentity,
        appointment_id: str,
        pool: asyncpg.Pool | None = None,
    ) -> None:
        """Đóng luôn dòng ``visit`` của lượt vừa checkout.

        HAI MỐC "KẾT THÚC LƯỢT", VÀ CHÚNG KHÔNG NÓI CHUYỆN VỚI NHAU.

        ``apply_action("complete")`` chỉ đặt ``appointment.status = COMPLETED``.
        Dòng ``visit`` thì do quầy đóng, qua ``CheckoutService.close``. Nên nút
        Checkout ở màn CSKH xưa nay đóng ĐÚNG MỘT NỬA: lịch hẹn nói đã khám
        xong, còn lượt khám vẫn mở.

        Đo trên staging 10/08/2026: **12 trên 15** dòng ``visit`` chưa đóng có
        lịch hẹn đã COMPLETED. Hệ quả không nằm ở màn CSKH — nó nằm ở chỗ khác:
        ``work_item`` của lượt còn PENDING, ``current_node_code`` vẫn trỏ một
        phòng, nên bệnh nhân đã về nhà vẫn nằm trong hàng đợi của bảng điều phối.
        Chính ``checkout_service`` đã ghi lại bài học ấy (xem 20260807000003).

        VÌ SAO GỌI THẲNG ``CheckoutService`` chứ không tự UPDATE: nó là đường
        DUY NHẤT dọn đủ ba thứ — đóng bước LUOTKHAM-15, bỏ con trỏ phòng, và ghi
        ``closed_at``/``closed_by``. Tự viết một câu UPDATE ở đây là dựng bản thứ
        hai của một quy trình, và bản thứ hai sẽ quên đúng cái thứ ba.

        BA NÚT KẾT THÚC LƯỢT LUÔN BẤM ĐƯỢC (Tuyền chốt 14/08/2026, lần thứ hai).

        Bản trước gọi ``close()`` KHÔNG kèm lý do ngoại lệ, nên còn một việc dở
        là cả thao tác dừng với dòng đỏ *"Lượt khám còn N việc chưa xong. Muốn
        đóng thì phải ghi lý do ngoại lệ."* — mà màn CSKH KHÔNG có ô nào để gõ
        lý do ấy. Người trực đọc một yêu cầu mà màn hình không cho họ cách đáp
        ứng; đó không phải một chốt, đó là một ngõ cụt.

        Lập luận cũ ("CSKH không đủ thông tin để vượt chốt lab/thanh toán") đúng
        về chuyên môn nhưng bỏ qua thực tế: khách đã về rồi. Lượt không đóng thì
        bệnh nhân ấy nằm mãi trong hàng đợi bảng điều phối — đúng cái hỏng mà
        chính hàm này được viết ra để chữa.

        KHÔNG XOÁ CHỐT, MÀ GHI LẠI ĐÃ VƯỢT CÁI GÌ. ``override_reason`` là cột
        sinh ra để trả lời "vì sao lượt này đóng khi còn dở". Truyền một câu
        rỗng cho qua chuyện thì cột ấy vô dụng. Câu dựng ở đây liệt kê ĐÚNG
        những việc còn vướng tại thời điểm đóng, kèm chỗ đứng của người bấm —
        đọc lại sáu tháng sau vẫn hiểu.

        Hai thứ vẫn KHÔNG được vượt, cố ý: lượt khám dở (khách về giữa chừng)
        vẫn phải có lý do do người gõ, và mọi ràng buộc ở tầng database giữ
        nguyên. Đây chỉ là chốt "phải giải thích", không phải chốt an toàn.
        """
        from clinicai.services.checkout_service import CheckoutService

        target_pool = pool or self._pool
        visit_id = await target_pool.fetchval(
            "SELECT visit_id::text FROM public.visit "
            " WHERE appointment_id = $1::uuid AND clinic_id = $2::uuid "
            "   AND closed_at IS NULL "
            " ORDER BY checked_in_at DESC NULLS LAST LIMIT 1 FOR UPDATE",
            appointment_id,
            identity.clinic_id,
        )
        if visit_id is None:
            # Heal a split state left by the old two-transaction implementation:
            # visit close committed but appointment complete failed. The outer
            # transaction may safely continue to complete the appointment.
            closed_visit_id = await target_pool.fetchval(
                "SELECT visit_id::text FROM public.visit "
                " WHERE appointment_id = $1::uuid AND clinic_id = $2::uuid "
                "   AND closed_at IS NOT NULL "
                " ORDER BY checked_in_at DESC NULLS LAST LIMIT 1 FOR UPDATE",
                appointment_id,
                identity.clinic_id,
            )
            if closed_visit_id is not None:
                return
            raise ValidationError(
                "Không tìm thấy lượt khám — nhờ Lễ tân kiểm tra trước khi đóng."
            )
        # `ly_do_tu_dong` chứ không phải `override_reason`: `close()` đã đọc
        # blockers rồi, nên nó dựng câu đầy đủ từ CHÍNH lần đọc ấy. Đọc lại ở
        # đây là hai vòng mạng cho một thứ, và hai kết quả có thể lệch nhau —
        # khi đó cột lý do ghi một danh sách không khớp thứ thật sự bị vượt.
        #
        # Không vướng gì thì `close()` không dùng tới câu này, và cột lý do để
        # trống — đúng vậy: nó chỉ có nghĩa khi thật sự có lần vượt chốt.
        await CheckoutService(target_pool).close(
            identity=identity,
            visit_id=visit_id,
            ly_do_tu_dong=("CSKH đóng lượt từ màn Quản lý khách hàng (khách đã về)."),
        )

    async def lich_su(
        self, *, identity: StaffIdentity, clinic_patient_id: str, gioi_han: int = 50
    ) -> list[dict[str, Any]]:
        """Dòng thời gian của một khách, mới nhất trước.

        Gộp cả `nhac_tai_kham` đã gọi xong: hai bảng, một dòng thời gian. CSKH
        không cần biết cuộc gọi nào được lưu ở bảng nào — họ cần biết khách này
        đã được gọi mấy lần và lần cuối nói gì.
        """
        rows = await self._pool.fetch(
            """
            SELECT t.xay_ra_luc, t.loai, t.kenh, t.ket_qua, t.khach_xac_nhan,
                   t.noi_dung, t.trang_thai_ma,
                   s.full_name AS nhan_vien, 'tuong_tac' AS nguon
              FROM public.tuong_tac_cskh t
              LEFT JOIN public.staff s ON s.id = t.nhan_vien_staff_id
             WHERE t.clinic_id = $1::uuid AND t.clinic_patient_id = $2::uuid

            UNION ALL

            SELECT n.goi_luc AS xay_ra_luc,
                   CASE n.luot_goi WHEN 1 THEN 'MOI_TAI_KHAM'
                                   ELSE 'NHAC_DI_KHAM' END AS loai,
                   'GOI' AS kenh, n.ket_qua, NULL::boolean AS khach_xac_nhan,
                   n.ghi_chu AS noi_dung, NULL::text AS trang_thai_ma,
                   s2.full_name AS nhan_vien,
                   'nhac_tai_kham' AS nguon
              FROM public.nhac_tai_kham n
              LEFT JOIN public.staff s2 ON s2.id = n.nguoi_goi_staff_id
             WHERE n.clinic_id = $1::uuid AND n.clinic_patient_id = $2::uuid
               AND n.goi_luc IS NOT NULL

             ORDER BY xay_ra_luc DESC
             LIMIT $3
            """,
            identity.clinic_id,
            clinic_patient_id,
            gioi_han,
        )
        return [dict(r) for r in rows]


class HenGoiLaiService:
    """Việc CSKH tự hẹn cho mình: "gọi lại ngày…".

    Chỗ đựng những việc hệ thống CHƯA suy được — gọi hỏi thăm sau thủ thuật,
    chúc mừng đầy tháng sau sinh.

    VÌ SAO GÕ TAY. Đo trên bản thật: không cột nào chứa ngày sinh con thật
    (`edd_date` là ngày DỰ sinh, lệch hai tuần là gọi chúc mừng vào tuần thứ
    hai hoặc tuần thứ sáu), và "thủ thuật" chưa phải một khái niệm — các
    service_type thủ thuật đang is_active = false sau 20260807000007.

    Một nút để người gõ thì có việc THẬT. Một tab tự sinh từ ngày dự sinh thì
    có việc SAI, và không ai biết nó sai cho tới lúc gọi nhầm.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def tao(
        self,
        *,
        identity: StaffIdentity,
        clinic_patient_id: str,
        ngay_goi: date,
        ly_do: str,
        gio_goi: time | None = None,
    ) -> dict[str, Any]:
        ly_do = (ly_do or "").strip()
        if not ly_do:
            # Một việc không có lý do là một việc mà tuần sau không ai biết vì
            # sao nó ở đó, và người trực sẽ đóng nó cho gọn màn hình.
            raise ValidationError("Ghi rõ gọi lại để làm gì.")
        hom_nay = datetime.now(GIO_VN).date()
        if ngay_goi < hom_nay:
            raise ValidationError("Ngày gọi lại không thể ở quá khứ.")

        async with self._pool.acquire() as conn:
            ok = await conn.fetchval(
                "SELECT 1 FROM public.patient "
                " WHERE clinic_patient_id = $1::uuid AND clinic_id = $2::uuid",
                clinic_patient_id,
                identity.clinic_id,
            )
            if not ok:
                raise NotFoundError("Không tìm thấy khách hàng này.")
            row_id = await conn.fetchval(
                """
                INSERT INTO public.hen_goi_lai
                    (clinic_id, clinic_patient_id, ngay_goi, gio_goi, ly_do,
                     tao_boi_staff_id)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::uuid)
                RETURNING id::text
                """,
                identity.clinic_id,
                clinic_patient_id,
                ngay_goi,
                gio_goi,
                ly_do,
                identity.staff_id,
            )
            ten_khach = await conn.fetchval(
                "SELECT full_name FROM public.patient "
                " WHERE clinic_patient_id = $1::uuid AND clinic_id = $2::uuid",
                clinic_patient_id,
                identity.clinic_id,
            )

        await self._bao_hen_goi_lai(
            identity=identity,
            hen_id=row_id,
            clinic_patient_id=clinic_patient_id,
            ten_khach=ten_khach or "Khách",
            ngay_goi=ngay_goi,
            gio_goi=gio_goi,
            ly_do=ly_do,
        )
        logger.info(
            "cskh_hen_goi_lai",
            ngay=str(ngay_goi),
            gio=str(gio_goi) if gio_goi else None,
            by=identity.staff_id,
        )
        return {"ok": True, "id": row_id}

    async def _bao_hen_goi_lai(
        self,
        *,
        identity: StaffIdentity,
        hen_id: str,
        clinic_patient_id: str,
        ten_khach: str,
        ngay_goi: date,
        gio_goi: time | None,
        ly_do: str,
    ) -> None:
        """Dựng một thông báo đứng sẵn trong chuông cho vai CSKH.

        MỘT GIỚI HẠN PHẢI NÓI RA. Dự án CHƯA CÓ BỘ HẸN GIỜ NÀO — không có gì
        chạy nền để đúng 17:00 thì gõ vào vai CSKH. Nên thông báo này ra đời
        NGAY LÚC ĐẶT HẸN, mang theo mốc giờ trong tiêu đề, và nằm đó tới khi có
        người bấm "đã xử lý". Nó là một mẩu giấy dán màn hình, không phải đồng
        hồ báo thức — và nói thẳng như vậy còn hơn hứa một tiếng chuông sẽ không
        bao giờ kêu.

        Nuốt lỗi: lời hẹn ĐÃ ghi vào `hen_goi_lai` và đã hiện ở cột trạng thái
        (nhánh HEN_GOI_LAI của `v_trang_thai_cskh`). Ném lỗi ở đây là báo hỏng
        cho một việc đã xong.
        """
        from clinicai.services.thong_bao_service import ThongBaoService

        khi = f"{ngay_goi:%d/%m}"
        if gio_goi is not None:
            khi = f"{gio_goi:%H:%M} ngày {khi}"
        try:
            await ThongBaoService(self._pool).goi(
                identity=identity,
                vai_nhan=ClinicRole.CSKH.value,
                nguon="hen_goi_lai",
                nguon_id=hen_id,
                muc_do="THUONG",
                tieu_de=f"Hẹn gọi lại {khi} — {ten_khach}",
                noi_dung=ly_do,
                # TỚI ĐÚNG VIỆC, KHÔNG CHỈ ĐÚNG HỒ SƠ (Quang 10/08/2026).
                #
                # `?selected=` một mình mở đúng khách rồi buông tay: cột phải
                # vẫn chạy theo việc gấp nhất do view suy ra, và lời hẹn này
                # (ưu tiên 6) thường thua một việc khác. Người trực bấm "Bấm để
                # xử lý" rồi không thấy đâu là việc vừa được nhắc.
                #
                # `viec=HEN_GOI_LAI` mở đúng bộ nút gọi + ghi kết quả, và khối
                # "Đã hẹn gọi lại" ở cột giữa hiện ngày, giờ và lý do đã ghi.
                duong_dan=(f"/customers?selected={clinic_patient_id}&viec=HEN_GOI_LAI"),
            )
        except Exception:  # noqa: BLE001 — xem docstring
            logger.warning("bao_hen_goi_lai_that_bai", hen_id=hen_id, exc_info=True)

    async def dong(self, *, identity: StaffIdentity, hen_id: str) -> dict[str, Any]:
        """Đóng việc khi mốc ngày + giờ phòng khám đã tới."""
        hen = await self._pool.fetchrow(
            "SELECT id::text, ngay_goi, gio_goi, dong_luc "
            "  FROM public.hen_goi_lai "
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            hen_id,
            identity.clinic_id,
        )
        if hen is None or hen["dong_luc"] is not None:
            raise NotFoundError("Không tìm thấy việc này, hoặc nó đã đóng rồi.")

        bay_gio = datetime.now(GIO_VN)
        ngay_goi: date = hen["ngay_goi"]
        gio_goi: time | None = hen["gio_goi"]
        chua_toi_ngay = ngay_goi > bay_gio.date()
        chua_toi_gio = (
            ngay_goi == bay_gio.date()
            and gio_goi is not None
            and bay_gio.time().replace(tzinfo=None) < gio_goi
        )
        if chua_toi_ngay or chua_toi_gio:
            khi = f"{ngay_goi:%d/%m/%Y}"
            if gio_goi is not None:
                khi = f"{gio_goi:%H:%M} ngày {khi}"
            raise ValidationError(f"Chưa tới giờ gọi lại ({khi}).")

        row = await self._pool.fetchrow(
            "UPDATE public.hen_goi_lai "
            "   SET dong_luc = now(), dong_boi_staff_id = $1::uuid "
            " WHERE id = $2::uuid AND clinic_id = $3::uuid AND dong_luc IS NULL "
            "RETURNING id::text",
            identity.staff_id,
            hen_id,
            identity.clinic_id,
        )
        if row is None:
            raise NotFoundError("Không tìm thấy việc này, hoặc nó đã đóng rồi.")
        return {"ok": True}


class GuiZaloService:
    """Gửi tin ZNS cho khách, và chỉ ghi sổ khi Zalo THẬT SỰ nhận.

    ĐÂY LÀ CHỖ DỄ NÓI DỐI NHẤT trong cả màn. Một dòng "đã liên hệ" ghi trước
    khi biết kết quả sẽ khiến người trực ca sau tin rằng khách đã được báo — và
    không ai gọi nữa. Nên thứ tự là: gọi Zalo → đọc kết quả → CHỈ KHI thành
    công mới ghi sổ. Thất bại thì trả về lý do đọc được, không để lại dấu vết
    nào nói việc đã xảy ra.

    ZNS KHÔNG GỬI ĐƯỢC TỆP. Nó gửi template chữ đã duyệt. Nên "gửi kết quả qua
    Zalo" thật ra là "báo cho khách biết kết quả đã có" — tệp vẫn đi đường
    khác. Nhãn trên màn phải nói đúng như thế.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def gui(
        self,
        *,
        identity: StaffIdentity,
        clinic_patient_id: str,
        loai_tin: str,
        appointment_id: str | None = None,
    ) -> dict[str, Any]:
        from clinicai.services.providers import zalo

        if loai_tin not in ("NHAC_HEN", "TRA_KET_QUA"):
            raise ValidationError(f"Loại tin không hợp lệ: {loai_tin!r}.")

        row = await self._pool.fetchrow(
            "SELECT full_name, phone_primary FROM public.patient"
            " WHERE clinic_patient_id = $1::uuid AND clinic_id = $2::uuid",
            clinic_patient_id,
            identity.clinic_id,
        )
        if row is None:
            raise NotFoundError("Không tìm thấy khách hàng này.")
        if not (row["phone_primary"] or "").strip():
            raise ValidationError("Khách chưa có số điện thoại.")

        gio_hen = ""
        if appointment_id:
            ah = await self._pool.fetchrow(
                "SELECT slot_start, clinic_patient_id::text AS clinic_patient_id "
                "FROM public.appointment"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                appointment_id,
                identity.clinic_id,
            )
            if ah is None:
                raise NotFoundError("Không tìm thấy lịch hẹn này.")
            if ah["clinic_patient_id"] != clinic_patient_id:
                raise ValidationError("Lịch hẹn không phải của khách này.")
            if ah["slot_start"]:
                gio_hen = ah["slot_start"].astimezone(GIO_VN).strftime("%H:%M %d/%m")

        ket_qua = await zalo.gui_zns(
            sdt=row["phone_primary"],
            template_id=zalo.template_cho(loai_tin) or "",
            du_lieu={"ten": row["full_name"] or "", "gio_hen": gio_hen},
            ma_theo_doi=clinic_patient_id,
        )

        if not ket_qua.get("da_gui"):
            # KHÔNG ghi sổ. Một dòng "đã liên hệ" cho một tin chưa gửi là đúng
            # thứ tính năng này phải chống.
            logger.warning(
                "zalo_gui_that_bai",
                ly_do=ket_qua.get("ly_do"),
                by_staff_id=identity.staff_id,
            )
            return {"da_gui": False, **ket_qua}

        await TuongTacCskhService(self._pool).ghi(
            identity=identity,
            clinic_patient_id=clinic_patient_id,
            appointment_id=appointment_id,
            # ZNS chỉ báo "đã có kết quả", không mang tệp. Ghi TRA_KQ ở đây
            # sẽ làm KQ_CHUA_GUI biến mất dù chưa ai gửi ảnh/PDF/video.
            loai="NHAC_HEN" if loai_tin == "NHAC_HEN" else "KHAC",
            kenh="ZALO",
            ket_qua="DA_LIEN_HE",
            noi_dung="Đã gửi tin Zalo (ZNS).",
        )
        return {"da_gui": True, "ly_do": "OK"}
