-- LỊCH HẸN CỦA LƯỢT ĐÃ VỀ KHÔNG CÒN "ĐÃ CHECK-IN" (Tuyền 30/09/2026: "đã
-- checkout rồi nhưng ở mấy trang chủ hay trang lịch hẹn khám vẫn ghi là đang
-- khám. Dữ liệu cũng chưa được đồng bộ cho tất cả các lịch cũ.")
--
-- GỐC: `appointment.status` chỉ sang COMPLETED ở MỘT chỗ — lúc bác sĩ khép
-- lượt (`luot_kham_service._khep_luot`, đòi mọi phiên khám xong + hết chỉ định
-- dở). Lượt check-out khi còn việc dở, khách về giữa chừng, hay lượt thủ thuật
-- đi thẳng phòng (không có phiên khám nào) thì lịch nằm lại CHECKED_IN mãi:
-- lưới lịch tuần ghi "Đã check-in"/"Đang chờ khám", ô "Đã check-in hôm nay"
-- đếm cả người đã về, và `v_viec_cskh` giữ một việc DA_CHECKIN không bao giờ
-- đóng. Đo trên prod 30/09: 49 lịch CHECKED_IN có lượt đã check-out (25 đóng
-- bình thường + 24 về giữa chừng) và 4 lịch có lượt bác sĩ đã ký (FINALIZED)
-- mà lịch vẫn CHECKED_IN.
--
-- Từ bản này lệnh check-out (`checkout_service.close`) tự đưa lịch về
-- COMPLETED trong cùng giao dịch. Migration này sửa dữ liệu cũ theo ĐÚNG luật
-- ấy: lịch CHECKED_IN mà lượt của nó đã đóng (`closed_at`) hoặc đã ký
-- (FINALIZED / AMENDED) → COMPLETED. Nhãn hiển thị ("Đã về", "Về giữa chừng",
-- "Khám xong") do máy chủ suy từ lượt (`core/trang_thai_lich.trang_thai_hien_thi`).
--
-- An toàn với trigger của `appointment`: CHECKED_IN → COMPLETED cùng khung,
-- cùng bác sĩ, cùng kênh = "đã giữ ghế" (enforce_slot_capacity trả về ngay);
-- cấp số quầy / số thứ tự chỉ chạy khi vào CHECKED_IN; đóng nhắc tái khám chỉ
-- chạy cho trạng thái còn sống. Không xoá gì.
--
-- Chạy lại được: lần hai không còn dòng lệch → 0 dòng. In số dòng đã sửa.

DO $$
DECLARE
    so_dong integer;
BEGIN
    WITH sua AS (
        UPDATE public.appointment a
           SET status = 'COMPLETED', updated_at = now()
          FROM public.visit v
         WHERE v.appointment_id = a.id
           AND v.clinic_id = a.clinic_id
           AND a.status = 'CHECKED_IN'
           AND (v.closed_at IS NOT NULL OR v.status IN ('FINALIZED', 'AMENDED'))
        RETURNING a.id
    )
    SELECT count(*) INTO so_dong FROM sua;
    RAISE NOTICE 'Lịch của lượt đã về / đã ký còn CHECKED_IN → COMPLETED: % dòng',
        so_dong;
END
$$;
