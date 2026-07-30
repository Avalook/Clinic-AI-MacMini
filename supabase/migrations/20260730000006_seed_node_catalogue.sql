-- W4 — Seed the 37-node catalogue for Dr4Women (ADR-0011).
--
-- Source: Notion "12. Danh mục định nghĩa nút v1", transcribed into
-- docs/ClinicAI-Tong-Quan-He-Thong.md §13. The clinic owns this list; it is
-- seeded rather than hard-coded precisely so it can be edited without a deploy.
--
-- Idempotent: re-running updates the definition in place and never duplicates.
-- It writes only for the Dr4Women tenant, so a second clinic starts empty and
-- gets its own catalogue.
--
-- ROLE MAPPING: the catalogue names roles in prose ("BS / KTV siêu âm"). Those
-- are mapped onto the 11 department codes in src/dashboard/lib/roles.ts. Where
-- the clinic has no dedicated code — there is no pharmacist and no lab
-- technician role — the nearest real one is used and noted below. Worth a
-- second pair of eyes from the clinic before the flow goes live.
--
-- DEPENDENCIES: §13 gives the stations but not the arrows between them. The
-- chains seeded at the bottom follow the catalogue's own numbering, which is
-- the only ordering the source states. Parallel work (the five KHAM specialties,
-- the DICHVU services) is deliberately left unlinked — which service follows
-- which exam is a clinical decision, not something to infer from a table.

-- ---------------------------------------------------------------------------
-- 1. Definitions
-- ---------------------------------------------------------------------------

INSERT INTO public.node_definition
    (clinic_id, code, name, flow_group, workspace, actor_roles, priority, is_group)
VALUES
-- §13.1 Hoạch định nguồn lực — Khu lịch nhân sự
('a0000000-0000-4000-8000-000000000001', 'NGUONLUC-01', 'Khai báo lịch làm việc', 'nhan_su', 'khu_lich_nhan_su', ARRAY['DOCTOR','ULTRASOUND_DOCTOR','TKYK','MANAGEMENT'], 'P2', false),
('a0000000-0000-4000-8000-000000000001', 'NGUONLUC-02', 'Duyệt lịch làm việc', 'nhan_su', 'khu_lich_nhan_su', ARRAY['MANAGEMENT'], 'P2', false),
('a0000000-0000-4000-8000-000000000001', 'NGUONLUC-03', 'Công bố khung giờ', 'nhan_su', 'khu_lich_nhan_su', ARRAY['MANAGEMENT','CSKH'], 'P2', false),

-- §13.2 Đặt lịch — Khu đặt lịch
('a0000000-0000-4000-8000-000000000001', 'DATLICH-01', 'Tiếp nhận yêu cầu đặt lịch', 'dat_lich', 'khu_dat_lich', ARRAY['CSKH'], 'P1', false),
('a0000000-0000-4000-8000-000000000001', 'DATLICH-02', 'Đối chiếu hoặc tạo hồ sơ người bệnh', 'dat_lich', 'khu_dat_lich', ARRAY['CSKH','RECEPTION'], 'P1', false),
('a0000000-0000-4000-8000-000000000001', 'DATLICH-03', 'Chọn khung giờ', 'dat_lich', 'khu_dat_lich', ARRAY['CSKH'], 'P1', false),
('a0000000-0000-4000-8000-000000000001', 'DATLICH-04', 'Xác nhận lịch', 'dat_lich', 'khu_dat_lich', ARRAY['CSKH'], 'P1', false),
('a0000000-0000-4000-8000-000000000001', 'DATLICH-05', 'Đổi lịch', 'dat_lich', 'khu_dat_lich', ARRAY['CSKH'], 'P2', false),
('a0000000-0000-4000-8000-000000000001', 'DATLICH-06', 'Huỷ lịch (giải phóng slot)', 'dat_lich', 'khu_dat_lich', ARRAY['CSKH','MANAGEMENT'], 'P2', false),

-- §13.3 Lượt khám
('a0000000-0000-4000-8000-000000000001', 'LUOTKHAM-01', 'Tiếp nhận người bệnh (check-in)', 'tiep_nhan', 'bang_dieu_phoi', ARRAY['RECEPTION'], 'P0', false),
('a0000000-0000-4000-8000-000000000001', 'LUOTKHAM-02', 'Xác minh người bệnh & dịch vụ hôm nay', 'tiep_nhan', 'bang_dieu_phoi', ARRAY['RECEPTION','NURSE_ULTRASOUND'], 'P0', false),
('a0000000-0000-4000-8000-000000000001', 'LUOTKHAM-03', 'Sinh hiệu', 'sinh_hieu', 'khu_dieu_duong', ARRAY['NURSE_ULTRASOUND'], 'P0', false),
('a0000000-0000-4000-8000-000000000001', 'LUOTKHAM-05', 'Tạo chỉ định dịch vụ', 'kham', 'khu_bac_si', ARRAY['DOCTOR','ULTRASOUND_DOCTOR','TKYK'], 'P0', false),
('a0000000-0000-4000-8000-000000000001', 'LUOTKHAM-13', 'Đối soát chi phí', 'thu_ngan', 'thu_ngan_dong_luot', ARRAY['CASHIER','CASHIER_THUOC','CASHIER_DV'], 'P0', false),
('a0000000-0000-4000-8000-000000000001', 'LUOTKHAM-14', 'Thanh toán', 'thu_ngan', 'thu_ngan_dong_luot', ARRAY['CASHIER','CASHIER_THUOC','CASHIER_DV'], 'P0', false),
('a0000000-0000-4000-8000-000000000001', 'LUOTKHAM-15', 'Đóng lượt khám', 'thu_ngan', 'thu_ngan_dong_luot', ARRAY['RECEPTION','CASHIER','CASHIER_THUOC','CASHIER_DV'], 'P0', false),

-- §13.3 Node khám — 5 chuyên khoa
('a0000000-0000-4000-8000-000000000001', 'KHAM-PHUKHOA', 'Khám Phụ khoa', 'kham', 'khu_bac_si', ARRAY['DOCTOR'], 'P0', false),
('a0000000-0000-4000-8000-000000000001', 'KHAM-SANKHOA', 'Khám Sản khoa', 'kham', 'khu_bac_si', ARRAY['DOCTOR'], 'P0', false),
('a0000000-0000-4000-8000-000000000001', 'KHAM-NOITIET', 'Khám Nội tiết', 'kham', 'khu_bac_si', ARRAY['DOCTOR'], 'P0', false),
('a0000000-0000-4000-8000-000000000001', 'KHAM-HIEMMUON-VOSINH', 'Khám Hiếm muộn – Vô sinh', 'kham', 'khu_bac_si', ARRAY['DOCTOR'], 'P0', false),
('a0000000-0000-4000-8000-000000000001', 'KHAM-NAMKHOA', 'Khám Nam khoa', 'kham', 'khu_bac_si', ARRAY['DOCTOR'], 'P1', false),

-- §13.4 Dịch vụ & kết quả
('a0000000-0000-4000-8000-000000000001', 'DICHVU-SIEUAM', 'Thực hiện siêu âm (nhóm)', 'dich_vu', 'khu_sieu_am', ARRAY['ULTRASOUND_DOCTOR','NURSE_ULTRASOUND'], 'P0', true),
('a0000000-0000-4000-8000-000000000001', 'DICHVU-LAYMAU-MAU', 'Lấy mẫu máu', 'dich_vu', 'khu_dieu_duong', ARRAY['NURSE_ULTRASOUND'], 'P0', false),
('a0000000-0000-4000-8000-000000000001', 'DICHVU-LAYMAU-NUOCTIEU', 'Lấy mẫu nước tiểu', 'dich_vu', 'khu_dieu_duong', ARRAY['NURSE_ULTRASOUND'], 'P1', false),
('a0000000-0000-4000-8000-000000000001', 'DICHVU-LAYMAU-AMDAO', 'Lấy mẫu dịch âm đạo', 'dich_vu', 'khu_dieu_duong', ARRAY['DOCTOR','NURSE_ULTRASOUND'], 'P1', false),
('a0000000-0000-4000-8000-000000000001', 'DICHVU-SANGLOC-COTUCUNG', 'Phết tế bào CTC / HPV / ThinPrep', 'dich_vu', 'khu_dieu_duong', ARRAY['DOCTOR','NURSE_ULTRASOUND'], 'P1', false),
('a0000000-0000-4000-8000-000000000001', 'DICHVU-DXA', 'Đo mật độ xương DXA', 'dich_vu', 'khu_dieu_duong', ARRAY['NURSE_ULTRASOUND','DOCTOR'], 'P1', false),
('a0000000-0000-4000-8000-000000000001', 'DICHVU-THUTHUAT', 'Thực hiện thủ thuật (nhóm)', 'dich_vu', 'khu_dieu_duong', ARRAY['DOCTOR','NURSE_ULTRASOUND'], 'P1', true),
-- "Dược / thu ngân": the clinic has no pharmacist role code, and dispensing is
-- handled at the medicine till.
('a0000000-0000-4000-8000-000000000001', 'DICHVU-THUOC', 'Cấp thuốc', 'dich_vu', 'khu_dieu_duong', ARRAY['CASHIER_THUOC'], 'P1', false),
('a0000000-0000-4000-8000-000000000001', 'DICHVU-HINHANH-NGOAI', 'Chẩn đoán hình ảnh ngoài (nhóm)', 'dich_vu', 'khu_dieu_duong', ARRAY['CSKH','TRUONG_CA'], 'P1', true),
-- "KTV xét nghiệm": no lab-technician code exists; TKYK (medical secretary) is
-- who enters results today.
('a0000000-0000-4000-8000-000000000001', 'DICHVU-KETQUA-XETNGHIEM', 'Xử lý & nhập kết quả xét nghiệm', 'ket_qua', 'khu_xet_nghiem', ARRAY['TKYK'], 'P1', false),
('a0000000-0000-4000-8000-000000000001', 'DICHVU-TINHDICHDO', 'Tinh dịch đồ', 'ket_qua', 'khu_xet_nghiem', ARRAY['TKYK'], 'P1', false),
('a0000000-0000-4000-8000-000000000001', 'DICHVU-DUYET-KETQUA', 'Duyệt kết quả (release_now / sensitive_hold)', 'ket_qua', 'khu_bac_si', ARRAY['DOCTOR'], 'P0', false),

-- §13.5 Theo dõi sau khám
('a0000000-0000-4000-8000-000000000001', 'THEODOI-01', 'Tạo hồ sơ theo dõi', 'cham_soc_khach_hang', 'bang_theo_doi_sau_kham', ARRAY['CSKH','DOCTOR'], 'P1', false),
('a0000000-0000-4000-8000-000000000001', 'THEODOI-02', 'Duyệt nội dung/kết quả được phép trả', 'cham_soc_khach_hang', 'bang_theo_doi_sau_kham', ARRAY['DOCTOR'], 'P1', false),
('a0000000-0000-4000-8000-000000000001', 'THEODOI-03', 'Thông báo người bệnh', 'cham_soc_khach_hang', 'bang_theo_doi_sau_kham', ARRAY['CSKH'], 'P1', false),
('a0000000-0000-4000-8000-000000000001', 'THEODOI-04', 'Hoàn tất theo dõi / tạo tái hẹn', 'cham_soc_khach_hang', 'bang_theo_doi_sau_kham', ARRAY['CSKH','DOCTOR'], 'P1', false)

ON CONFLICT ON CONSTRAINT uq_node_definition_clinic_code DO UPDATE SET
    name        = EXCLUDED.name,
    flow_group  = EXCLUDED.flow_group,
    workspace   = EXCLUDED.workspace,
    actor_roles = EXCLUDED.actor_roles,
    priority    = EXCLUDED.priority,
    is_group    = EXCLUDED.is_group,
    updated_at  = now();

-- ---------------------------------------------------------------------------
-- 2. Freeze version 1 of every definition
-- ---------------------------------------------------------------------------

INSERT INTO public.node_definition_version (clinic_id, node_definition_id, version, snapshot)
SELECT n.clinic_id,
       n.id,
       n.current_version,
       jsonb_build_object(
           'code', n.code,
           'name', n.name,
           'flow_group', n.flow_group,
           'workspace', n.workspace,
           'actor_roles', to_jsonb(n.actor_roles),
           'priority', n.priority,
           'is_group', n.is_group,
           'config', n.config
       )
FROM public.node_definition n
ON CONFLICT ON CONSTRAINT uq_node_definition_version DO NOTHING;

-- ---------------------------------------------------------------------------
-- 3. The chains the catalogue's numbering states
-- ---------------------------------------------------------------------------
-- Finish-to-start throughout: each of these is a step the clinic does after the
-- previous one is done. LUOTKHAM skips 04 and 06–12 because the catalogue
-- reserves those numbers for exam/service nodes it has not settled yet, so the
-- chain jumps 03 → 05 → 13.

INSERT INTO public.node_dependency
    (clinic_id, predecessor_code, successor_code, dependency_type, is_blocking)
VALUES
('a0000000-0000-4000-8000-000000000001', 'NGUONLUC-01', 'NGUONLUC-02', 'FS', true),
('a0000000-0000-4000-8000-000000000001', 'NGUONLUC-02', 'NGUONLUC-03', 'FS', true),

('a0000000-0000-4000-8000-000000000001', 'DATLICH-01', 'DATLICH-02', 'FS', true),
('a0000000-0000-4000-8000-000000000001', 'DATLICH-02', 'DATLICH-03', 'FS', true),
('a0000000-0000-4000-8000-000000000001', 'DATLICH-03', 'DATLICH-04', 'FS', true),

('a0000000-0000-4000-8000-000000000001', 'LUOTKHAM-01', 'LUOTKHAM-02', 'FS', true),
('a0000000-0000-4000-8000-000000000001', 'LUOTKHAM-02', 'LUOTKHAM-03', 'FS', true),
('a0000000-0000-4000-8000-000000000001', 'LUOTKHAM-03', 'LUOTKHAM-05', 'FS', true),
('a0000000-0000-4000-8000-000000000001', 'LUOTKHAM-05', 'LUOTKHAM-13', 'FS', true),
('a0000000-0000-4000-8000-000000000001', 'LUOTKHAM-13', 'LUOTKHAM-14', 'FS', true),
('a0000000-0000-4000-8000-000000000001', 'LUOTKHAM-14', 'LUOTKHAM-15', 'FS', true),

-- A result may only be released by a doctor after it has been entered.
('a0000000-0000-4000-8000-000000000001', 'DICHVU-KETQUA-XETNGHIEM', 'DICHVU-DUYET-KETQUA', 'FS', true),

('a0000000-0000-4000-8000-000000000001', 'THEODOI-01', 'THEODOI-02', 'FS', true),
('a0000000-0000-4000-8000-000000000001', 'THEODOI-02', 'THEODOI-03', 'FS', true),
('a0000000-0000-4000-8000-000000000001', 'THEODOI-03', 'THEODOI-04', 'FS', true)

ON CONFLICT ON CONSTRAINT uq_node_dependency DO UPDATE SET
    dependency_type = EXCLUDED.dependency_type,
    is_blocking     = EXCLUDED.is_blocking;
