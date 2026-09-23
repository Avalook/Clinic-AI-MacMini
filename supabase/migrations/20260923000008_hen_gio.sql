-- Hẹn giờ: viên gạch cho mọi luật có chữ "sau bao lâu" (23/09/2026).
--
-- VÌ SAO. Rất nhiều luật của phòng khám có chữ "quá … phút": khách chờ quá 20
-- phút thì báo trưởng ca; việc đối soát tiền để quá một ngày thì nhắc lại; khách
-- hẹn tái khám mà chưa tới thì gọi. Hôm nay hệ thống **không có chỗ nào để hẹn
-- một việc trong tương lai**, nên mọi luật loại ấy đều phải có người nhớ hộ.
--
-- MỘT BẢNG, KHÔNG THÊM MÁY CHỦ. Temporal và Camunda giải đúng bài này, nhưng
-- mỗi cái là một máy chủ + một database + một đội worker nữa để trông. Ở quy mô
-- một phòng khám, một bảng Postgres và một vòng lặp là đủ, và không ai phải học
-- thêm một hệ thống.
--
-- HAI LUẬT KHÔNG ĐƯỢC QUÊN
--   1. **Hẹn giờ ghi CÙNG giao dịch với việc sinh ra nó.** Mở việc xong mới hẹn
--      ở giao dịch khác là có ngày việc mở mà lời nhắc không bao giờ tới.
--   2. **Tới giờ phải KIỂM LẠI hiện trạng trước khi làm.** Lời nhắc đặt lúc
--      10:00 cho 10:20 không biết chuyện 10:05 người ta đã xử lý xong. Bắn một
--      lời nhắc sai là cách nhanh nhất để người trực học cách bỏ qua lời nhắc.
--
-- Chạy lại được: IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS public.hen_gio (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id     uuid NOT NULL,

    -- Loại hẹn — quyết định code nào xử lý khi tới giờ.
    loai          text NOT NULL,
    -- Hẹn về cái gì (việc nào, lượt nào, chỉ định nào).
    ve_cai_gi     uuid,
    -- Cả chuỗi việc, thường là mã lượt khám.
    correlation_id uuid,
    chi_tiet      jsonb NOT NULL DEFAULT '{}'::jsonb,

    den_gio       timestamptz NOT NULL,
    trang_thai    text NOT NULL DEFAULT 'CHO',
    so_lan_thu    integer NOT NULL DEFAULT 0,
    -- Nhận việc có hạn: worker chết thì lời nhắc quay lại hàng, không kẹt.
    thue_den      timestamptz,
    lam_luc       timestamptz,
    ket_qua       text,
    loi_gan_nhat  text,

    tao_luc       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT hen_gio_trang_thai
        CHECK (trang_thai IN ('CHO', 'DANG_LAM', 'XONG', 'BO_QUA', 'CHET')),
    CONSTRAINT hen_gio_so_lan_thu CHECK (so_lan_thu >= 0),
    CONSTRAINT hen_gio_xong_co_gio
        CHECK ((trang_thai IN ('XONG', 'BO_QUA')) = (lam_luc IS NOT NULL))
);

-- Hàng đợi theo giờ: chỉ quét cái đã tới hạn.
CREATE INDEX IF NOT EXISTS ix_hen_gio_den_han
    ON public.hen_gio (den_gio)
    WHERE trang_thai = 'CHO';
CREATE INDEX IF NOT EXISTS ix_hen_gio_dang_lam
    ON public.hen_gio (thue_den)
    WHERE trang_thai = 'DANG_LAM';

-- Một loại hẹn cho một đối tượng chỉ có MỘT cái đang chờ. Sự kiện tới hai lần
-- hay hai người cùng bấm đều không được sinh hai lời nhắc cho cùng một chuyện.
CREATE UNIQUE INDEX IF NOT EXISTS uq_hen_gio_mot_cai_dang_cho
    ON public.hen_gio (clinic_id, loai, ve_cai_gi)
    WHERE ve_cai_gi IS NOT NULL AND trang_thai IN ('CHO', 'DANG_LAM');

ALTER TABLE public.hen_gio ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS hen_gio_select_own_clinic ON public.hen_gio;
CREATE POLICY hen_gio_select_own_clinic ON public.hen_gio
    FOR SELECT TO service_role
    USING (clinic_id IN (SELECT current_clinic_ids()));
GRANT SELECT, INSERT, UPDATE ON public.hen_gio TO service_role;

COMMENT ON TABLE public.hen_gio IS
    'Việc hẹn trong tương lai. Ghi cùng giao dịch với việc sinh ra nó; tới giờ phải kiểm lại hiện trạng trước khi làm.';
