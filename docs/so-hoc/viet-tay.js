// SỔ HỌC — PHẦN VIẾT TAY. Sửa thoải mái (giữ đúng cú pháp JSON bên dưới), rồi chạy
// `python3 scripts/so-hoc-data.py` để sinh lại phần code và kiểm mọi tệp:dòng, route.
// khoi[]: khối nghiệp vụ (thứ tự = thứ tự trên hành trình), routes = màn của khối,
//   man[] = tên dễ hiểu/ai dùng/làm được gì/bảng chính, thao_tac[] = chuỗi bước,
//   dieu_phai_nho[] = 5 điều, the[] = thẻ tự kiểm. toc_do = đèn đã đo / theo báo cáo
//   (màn không có ở đây thì trang tự xếp đèn theo code). tu_dien[] = tên viết tay;
//   manh = nghĩa từng mảnh tên để ghép nghĩa tự động cho tên còn lại.
window.SO_HOC_VIET_TAY = {
 "khoi": [
  {
   "id": "dat-lich",
   "ten": "Đặt lịch",
   "nhom": "hanh-trinh",
   "mau": "k1",
   "ngan": "Khách gọi/nhắn → CSKH, lễ tân giữ chỗ và đặt lịch với bác sĩ.",
   "routes": [
    "/appointments",
    "/patients/new",
    "/appointments/cho-xep-bac-si",
    "/lich-do-ve",
    "/print/[appointmentId]"
   ]
  },
  {
   "id": "tiep-don",
   "ten": "Tiếp đón & check-in",
   "nhom": "hanh-trinh",
   "mau": "k2",
   "ngan": "Khách tới quầy: check-in, đo sinh hiệu, TV gọi tên, ai cũng xem được khách đang ở đâu.",
   "routes": [
    "/reception/queue",
    "/do-sinh-hieu",
    "/home",
    "/hanh-trinh",
    "/display",
    "/truong-ca/tv"
   ]
  },
  {
   "id": "kham",
   "ten": "Khám",
   "nhom": "hanh-trinh",
   "mau": "k3",
   "ngan": "Tư vấn, bác sĩ khám, ghi phiếu khám, chỉ định dịch vụ, kê đơn.",
   "routes": [
    "/ban-kham",
    "/ban-kham/[phong]",
    "/tu-van",
    "/patient-list",
    "/print/phieu-kham/[visitId]"
   ],
   "mo_ta": "Bác sĩ (kèm thư ký y khoa) và bác sĩ tư vấn nhận khách từ hàng chờ phòng, ghi phiếu khám v5 tự lưu, chỉ định dịch vụ, kê đơn rồi bấm Hoàn tất. Đây là chặng giữa hành trình: sau đo sinh hiệu, trước quầy thu và phòng dịch vụ.",
   "dieu_phai_nho": [
    {
     "chu": "Hoàn tất KHÔNG khoá hồ sơ — chỉ là mốc giờ, sửa phiếu tiếp thoải mái (kể cả ngày cũ).",
     "vi_sao": "Tuyền chốt bỏ nút Ký và không khoá; bấm nhầm thì có Hoàn tác (mo-lai-kham), mọi thao tác phải hoàn tác được.",
     "nguon": "src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:16"
    },
    {
     "chu": "Chỉ định là MỘT lệnh, chỉ định luôn — thư ký y khoa ngang quyền bác sĩ, không còn bước nháp chờ duyệt.",
     "vi_sao": "Đường cũ hai bước (draft-orders → authorize-orders, bảng service_order_draft) đã tắt trả 410; chỉ còn cửa duyệt cho bản nháp sót lại.",
     "nguon": "src/clinicai/services/chi_dinh_service.py:7"
    },
    {
     "chu": "Bấm “Đã khám xong” thì MÁY CHỦ tự chọn kết quả phiên: còn chỉ định chưa làm → khách đi làm dịch vụ rồi quay lại đọc kết quả; hết → khép lượt khám.",
     "vi_sao": "Bắt bác sĩ chọn giữa hai mã kỹ thuật là đẩy luật vận hành lên đầu người đang khám.",
     "nguon": "src/clinicai/services/luot_kham_service.py:1590"
    },
    {
     "chu": "Phiếu khám tự lưu sau 1,5 giây ngừng gõ và CHỈ gửi các ô vừa đổi — hai người sửa hai ô khác nhau đều được giữ.",
     "vi_sao": "Gửi cả gói thì người lưu sau đè người lưu trước; gộp từng ô dưới khoá dòng, lịch sử sửa (trigger) giữ đủ vết.",
     "nguon": "src/clinicai/services/phieu_kham_service.py:387"
    },
    {
     "chu": "Chỉ định mới KHÔNG tự vào hàng phòng: phải đợi khách chọn + trả tiền ở quầy thì khối Hành trình mới xếp phòng.",
     "vi_sao": "Bác sĩ chỉ định xong mà phòng dịch vụ chưa thấy khách là đúng thiết kế (dây H4), không phải lỗi.",
     "nguon": "src/clinicai/services/chi_dinh_service.py:256"
    }
   ],
   "man": [
    {
     "route": "/ban-kham",
     "ten": "Bàn khám (khách của tôi, mọi phòng)",
     "ai_dung": "Bác sĩ chính, thư ký y khoa (lego ban_kham)",
     "lam_duoc": [
      "Xem hàng chờ khám theo nhóm: đang khám · kết quả cần đọc · chờ khám · đang ở bước khác · đã khám xong",
      "Bấm [Bắt đầu khám] ngay ở dòng hàng chờ hoặc trong hồ sơ",
      "Ghi phiếu khám v5 tự lưu, chỉ định dịch vụ (mục C/F), kê đơn thuốc (mục E), xem kết quả tại chỗ",
      "Bấm [Hoàn tất] (kham-xong) và hoàn tác trong vài giây",
      "Chọn ngày cũ (?ngay=) để mở lại lượt cũ mà sửa"
     ],
     "bang_doc": [
      "queue_entry",
      "consultation",
      "service_order",
      "visit",
      "phieu_kham_luot",
      "prescription"
     ],
     "bang_ghi": [
      "consultation",
      "queue_entry",
      "service_order",
      "phieu_kham_luot",
      "prescription",
      "domain_event"
     ],
     "toc_do_ghi_chu": "Mở màn: 1 lượt phong-hom-nay (src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:268) rồi 2 lượt song song hang-cho + bang (src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:291) + 1 lượt chip liệu trình (src/dashboard/app/(dashboard)/_lam-viec/dung-chip-lieu-trinh.ts:26) = 4. Chọn một khách (phiếu v5): PhieuKhamLuot gọi thêm 5 lượt song song dau-phieu, tham-chieu, don-thuoc, phieu, ket-qua (src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx:235) + các khối con tự fetch (hành trình src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/HanhTrinhLuot.tsx:49, điều trị src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/KhoiDieuTri.tsx:108, ghi chú, lịch sử khám… — chưa đếm hết) → khoảng 11 lượt trở lên. Có tin: useNgheBang 8 bảng queue_entry, consultation, visit, encounter_flow, service_order, form_instance, tep_ket_qua, vital_measurement (src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:330) → 2 lượt hang-cho + bang; mà `bang` là bảng lượt khám CẢ NGÀY (src/clinicai/services/luot_kham_doc.py:75). Tin service_order/form_instance/tep_ket_qua còn làm PhieuKhamLuot nạp lại kết quả (src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx:268) và vài khối con nghe service_order. Nhịp lưới an toàn 60 giây (src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:322). Màn nằm trong MAN_TU_TAI nên RealtimeRefresher không dựng lại trang server (src/dashboard/lib/man-tu-tai.ts:23).",
     "ghi_chu": "Không nghe phieu_kham_luot: người kia gõ phiếu thì phiếu đang mở KHÔNG nạp lại (cố ý, để không đè chữ đang gõ). Còn một luật trong TSX: thư ký bấm Hoàn tất lượt không còn dịch vụ thì màn tự chặn “Chờ bác sĩ hoàn tất” (src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:1038) — trái luật “không luật nghiệp vụ trong TSX”."
    },
    {
     "route": "/ban-kham/[phong]",
     "ten": "Bàn khám của một phòng",
     "ai_dung": "Bác sĩ chính, thư ký y khoa (lego ban_kham)",
     "lam_duoc": [
      "Giống /ban-kham nhưng hàng chờ lọc theo một phòng khám (room_id; mã phòng cũ vẫn mở được)",
      "Đổi phòng bằng ô chọn — có chặn nếu còn chỉ định tick chưa gửi",
      "Mọi thao tác khám/chỉ định/Hoàn tất như /ban-kham"
     ],
     "bang_doc": [
      "queue_entry",
      "consultation",
      "service_order",
      "visit"
     ],
     "bang_ghi": [
      "consultation",
      "queue_entry",
      "service_order",
      "phieu_kham_luot",
      "prescription"
     ],
     "toc_do_ghi_chu": "Cùng component BanKham với phongMa (ban-kham/[phong]/page.tsx); hang-cho gửi thêm ?phong=<room_id> (src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:293). Số lượt gọi như /ban-kham.",
     "ghi_chu": ""
    },
    {
     "route": "/tu-van",
     "ten": "Bàn khám tư vấn",
     "ai_dung": "Bác sĩ tư vấn (lego tu_van, quyền clinical.intake.perform)",
     "lam_duoc": [
      "Hàng tư vấn CHUNG — bác sĩ tư vấn nào rảnh thì nhận",
      "[Bắt đầu tư vấn] nhận cả khách còn chờ đo sinh hiệu",
      "Ghi MỘT ô chữ tự do (consultation_note) mang sang phiếu bác sĩ chính",
      "[Xong tư vấn] → khối Hành trình chuyển khách sang bác sĩ chính",
      "Điền tiếp đơn thuốc cho khách bác sĩ chính đã khám xong, đánh dấu Xong kê đơn"
     ],
     "bang_doc": [
      "queue_entry",
      "consultation",
      "consultation_note",
      "prescription",
      "visit"
     ],
     "bang_ghi": [
      "consultation",
      "queue_entry",
      "consultation_note",
      "prescription",
      "domain_event"
     ],
     "toc_do_ghi_chu": "Cùng BanKham với cheDo=\"tu_van\" (tu-van/page.tsx); hang-cho gửi ?tu_van=true (src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:293). Số lượt gọi khi mở và khi có tin như /ban-kham.",
     "ghi_chu": "Xong tư vấn KHÔNG tự xếp khách sang bác sĩ chính: nó phát consultation.handed_over, consumer HANH_TRINH làm việc ấy (src/clinicai/services/luot_kham_service.py:2030)."
    },
    {
     "route": "/patient-list",
     "ten": "Danh sách bệnh nhân (tra cứu)",
     "ai_dung": "Mọi vai có lego ds_benh_nhan (mặc định CSKH, lễ tân); vai lâm sàng mở thêm hồ sơ lâm sàng",
     "lam_duoc": [
      "Tìm / lọc / xếp ~8.700 hồ sơ, phân trang ở máy chủ 50 dòng",
      "Xem đã khám mấy lần và những lần nào",
      "Mở phiếu khám lượt cũ ở panel phải (vai lâm sàng)",
      "Đi sang đặt lịch cho khách"
     ],
     "bang_doc": [
      "patient",
      "visit",
      "appointment",
      "service_type",
      "staff"
     ],
     "bang_ghi": [],
     "toc_do_ghi_chu": "Mỗi lần dựng trang 1 lượt server GET /api/v1/patients/danh-sach (src/dashboard/app/(dashboard)/patient-list/page.tsx:167) — 50 dòng + số đếm; tìm/tab/trang đi qua URL (src/dashboard/app/(dashboard)/patient-list/PatientListView.tsx:250).",
     "ghi_chu": "Trang còn hỏi vai trong TSX (import isDoctorRole, canEditPatient… ở patient-list/page.tsx) để quyết bật hồ sơ lâm sàng."
    },
    {
     "route": "/print/phieu-kham/[visitId]",
     "ten": "In phiếu khám một lượt (A4)",
     "ai_dung": "Ai có khối khám/kết quả, và quầy tiếp đón / thu tiền / nhà thuốc in cho khách (requireInPhieu)",
     "lam_duoc": [
      "In phiếu khám v5 + dịch vụ + kết quả + đơn thuốc + ghi chú của lượt",
      "?phan= in riêng một phần (hồ sơ khám / kết quả / đơn thuốc) để tải PDF trả khách"
     ],
     "bang_doc": [
      "phieu_kham_luot",
      "service_order",
      "form_instance",
      "prescription",
      "tep_ket_qua"
     ],
     "bang_ghi": [],
     "toc_do_ghi_chu": "6 lượt song song khi mở: phieu, dau-phieu, ket-qua, don-thuoc, tham-chieu, ghi-chu (src/dashboard/app/print/phieu-kham/[visitId]/InPhieuKham.tsx:375).",
     "ghi_chu": "Nằm ngoài nhóm (dashboard) → không thanh bên; đọc đúng nguồn Bàn khám đọc (/api/phieu-kham)."
    }
   ],
   "chuyen_huong": [
    {
     "route": "/doctor/board",
     "toi": "/ban-kham"
    },
    {
     "route": "/doctor/orders/[visitId]",
     "toi": "/ban-kham"
    },
    {
     "route": "/kham/[loai]",
     "toi": "/ban-kham"
    },
    {
     "route": "/luot-kham",
     "toi": "/ban-kham"
    },
    {
     "route": "/result-review",
     "toi": "/duyet-ket-qua"
    }
   ],
   "thao_tac": [
    {
     "man": "/ban-kham",
     "nut": "Bấm [Bắt đầu khám] (hoặc [Bắt đầu tư vấn] ở /tu-van)",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "BanKham.tsx batDauTuHang gọi guiThaoTac(\"nhan-kham\", ref_id) → POST /api/luot-kham",
       "nguon": "src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:462"
      },
      {
       "loai": "api",
       "chu": "Proxy danh sách trắng nhan-kham → POST /api/v1/luot-kham/consultations/{id}/start",
       "nguon": "src/clinicai/api/v1/routers/luot_kham.py:433"
      },
      {
       "loai": "ham",
       "chu": "LuotKhamService.start_consultation (nhận khách vào phiên khám: hỏi quyền theo loại phiên, kiểm đúng ca, gắn bác sĩ của phiên)",
       "nguon": "src/clinicai/services/luot_kham_service.py:1709"
      },
      {
       "loai": "bang",
       "chu": "consultation.status = in_progress; queue_entry.status = serving; chặn chỗ chờ khác của khách; cập nhật vị trí visit",
       "nguon": "src/clinicai/services/luot_kham_service.py:1873"
      },
      {
       "loai": "su_kien",
       "chu": "pg_notify bảng consultation, queue_entry (trigger notify_row_change) + sự kiện nghiệp vụ consultation.started (consumer dòng thời gian lượt)",
       "nguon": "src/clinicai/services/luot_kham_service.py:1931"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "/ban-kham và /tu-van (useNgheBang queue_entry, consultation), /truong-ca (LIVE_TABLES), /do-sinh-hieu (queue_entry)",
       "nguon": "src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:330"
      }
     ],
     "ghi_chu": "Khách đang ở bước khác → 409 PATIENT_BUSY. Thư ký bấm thì phiên vẫn ghi BÁC SĨ tìm được, không ghi thư ký (src/clinicai/services/luot_kham_service.py:1884). Bấm lại khi khách quay về sau dịch vụ = tiếp tục phiên, phát consultation.resumed."
    },
    {
     "man": "/ban-kham",
     "nut": "Tick dịch vụ ở mục C/F rồi bấm gửi chỉ định",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "BanKham.tsx datChiDinh gọi guiThaoTac(\"chi-dinh\", {service_codes, bat_buoc_codes, lan_moi?}) kèm Idempotency-Key",
       "nguon": "src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:982"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/luot-kham/consultations/{id}/service-orders (PlaceServiceOrders)",
       "nguon": "src/clinicai/api/v1/routers/luot_kham.py:676"
      },
      {
       "loai": "ham",
       "chu": "ChiDinhService.dat_chi_dinh (chốt chỉ định: quyền clinical.order.place, khoá lượt, biên nhận chống bấm trùng, gán “lần chỉ định”)",
       "nguon": "src/clinicai/services/chi_dinh_service.py:135"
      },
      {
       "loai": "bang",
       "chu": "INSERT service_order (exec_status authorized, selection_status PENDING, routing_status UNASSIGNED); trigger ghi sổ sửa chỉ định",
       "nguon": "src/clinicai/services/chi_dinh_service.py:213"
      },
      {
       "loai": "su_kien",
       "chu": "pg_notify service_order + mỗi dịch vụ một service_order.placed trong domain_event, CÙNG giao dịch",
       "nguon": "src/clinicai/services/chi_dinh_service.py:238"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "/thu-ngan/dich-vu (QuayThuNgan nghe service_order) hiện khoản cần thu; Bàn khám nạp lại; phòng dịch vụ CHƯA thấy cho tới khi thu tiền + xếp phòng",
       "nguon": "src/dashboard/app/(dashboard)/thu-ngan/QuayThuNgan.tsx:301"
      }
     ],
     "ghi_chu": "Màn hiện “Đã chỉ định N dịch vụ · Hoàn tác” — hoàn tác = huy-chi-dinh từng order_id vừa tạo (src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:993). Rời khách khi còn tick chưa gửi thì bị chặn hỏi lại (src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:429)."
    },
    {
     "man": "/ban-kham",
     "nut": "Gõ vào phiếu khám v5 (không có nút Lưu — tự lưu)",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "PhieuKham đợi 1,5 giây sau phím cuối (CHO_TU_LUU_MS) rồi PhieuKhamLuot.onLuu gửi PUT /api/phieu-kham {thao_tac: luu-phieu, thay_doi: chỉ ô vừa đổi}",
       "nguon": "src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx:276"
      },
      {
       "loai": "api",
       "chu": "PUT /api/v1/phieu-kham/luot/{visit_id}/phieu",
       "nguon": "src/clinicai/api/v1/routers/phieu_kham.py:177"
      },
      {
       "loai": "ham",
       "chu": "PhieuKhamService.luu_luot (tự lưu một lần: qua cổng kiem_luu, kiểm đúng ca, gộp ô)",
       "nguon": "src/clinicai/services/phieu_kham_service.py:374"
      },
      {
       "loai": "bang",
       "chu": "INSERT/UPDATE phieu_kham_luot (du_lieu || ô mới, revision+1); ô kinh cuối/dự sinh đổi → ghi pregnancy; ngày hẹn đổi → việc gọi CSKH",
       "nguon": "src/clinicai/services/phieu_kham_service.py:473"
      },
      {
       "loai": "su_kien",
       "chu": "pg_notify phieu_kham_luot (trigger trg_notify_phieu_kham_luot); KHÔNG phát sự kiện nghiệp vụ — mốc duy nhất là lúc Hoàn tất",
       "nguon": "supabase/migrations/20261010100001_lich_su_don_thuoc_notify.sql:16"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "Lịch sử đơn thuốc ở nhà thuốc (LichSuDonThuoc nghe phieu_kham_luot); Bàn khám đang mở KHÔNG nạp lại phiếu (để không đè chữ)",
       "nguon": "src/dashboard/app/(dashboard)/pharmacy/LichSuDonThuoc.tsx:320"
      }
     ],
     "ghi_chu": "Đơn thuốc mục E đi đường riêng PUT luu-don → PhieuKhamService.luu_don_thuoc → bảng prescription + sự kiện prescription.saved (src/clinicai/services/phieu_kham_service.py:822). Hoàn tất khi còn chữ chưa lưu thì màn lưu nốt rồi mới gửi (src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:1059)."
    },
    {
     "man": "/ban-kham",
     "nut": "Bấm [Hoàn tất] ở cuối hồ sơ",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "BanKham.tsx bam(\"kham-xong\") → gui() gọi guiThaoTac(\"kham-xong\", ref_id); xong thì hiện “Đã khám xong · Hoàn tác” (mo-lai-kham)",
       "nguon": "src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:1011"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/luot-kham/consultations/{id}/kham-xong",
       "nguon": "src/clinicai/api/v1/routers/luot_kham.py:377"
      },
      {
       "loai": "ham",
       "chu": "LuotKhamService.kham_xong (máy chủ tự chọn kết quả phiên) → complete_consultation (khép phiên, lập yêu cầu vòng đọc kết quả)",
       "nguon": "src/clinicai/services/luot_kham_service.py:2446"
      },
      {
       "loai": "bang",
       "chu": "UPDATE consultation status=completed, outcome; queue_entry → done; tạo review_round nếu còn dịch vụ",
       "nguon": "src/clinicai/services/luot_kham_service.py:2697"
      },
      {
       "loai": "su_kien",
       "chu": "pg_notify consultation, queue_entry + consultation.completed (mốc DUY NHẤT phát sự kiện của bệnh án) + followup.scheduled nếu có ngày tái khám",
       "nguon": "src/clinicai/services/luot_kham_service.py:2711"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "Bàn khám chuyển khách sang “Đã khám xong” nhưng vẫn ghim khách đang mở; /truong-ca, /hanh-trinh nạp lại",
       "nguon": "src/dashboard/app/(dashboard)/truong-ca/shared.tsx:118"
      }
     ],
     "ghi_chu": "Bàn tư vấn bấm [Xong tư vấn] thay vì kham-xong: POST .../xong-tu-van → LuotKhamService.xong_tu_van, phát consultation.handed_over (src/clinicai/services/luot_kham_service.py:2111)."
    }
   ],
   "the": [
    {
     "hoi": "Màn /ban-kham nghe những bảng nào để tự nạp lại hàng chờ?",
     "dap": "8 bảng: queue_entry, consultation, visit, encounter_flow, service_order, form_instance, tep_ket_qua, vital_measurement — mỗi tin gọi lại hang-cho + bang.",
     "nguon": "src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:330"
    },
    {
     "hoi": "/tu-van có phải một màn riêng không?",
     "dap": "Không. Cùng component BanKham với cheDo=\"tu_van\": đọc hàng tư vấn chung (hang-cho?tu_van=true), nút Bắt đầu tư vấn / Xong tư vấn.",
     "nguon": "src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:242"
    },
    {
     "hoi": "Thư ký y khoa nhập chỉ định thì có phải chờ bác sĩ duyệt không?",
     "dap": "Không. Một lệnh chi-dinh ghi thẳng service_order đã duyệt. Đường nháp service_order_draft / draft-orders đã nghỉ, trả 410.",
     "nguon": "src/clinicai/api/v1/routers/luot_kham.py:719"
    },
    {
     "hoi": "Phiếu khám v5 lưu vào bảng nào, và bao lâu thì tự lưu?",
     "dap": "Bảng phieu_kham_luot (một dòng mỗi lượt × phiếu), tự lưu 1,5 giây sau phím cuối, chỉ gửi các ô vừa đổi.",
     "nguon": "src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/PhieuKham.tsx:73"
    },
    {
     "hoi": "Đơn thuốc bác sĩ kê đi vào bảng nào, sự kiện gì?",
     "dap": "Bảng prescription qua luu_don_chua_ky; phát prescription.saved (consumer dòng thời gian + sổ nợ). Nhà thuốc nghe bảng prescription.",
     "nguon": "src/clinicai/services/phieu_kham_service.py:891"
    },
    {
     "hoi": "Bấm Hoàn tất xong có sửa phiếu được nữa không? Hoàn tác thế nào?",
     "dap": "Sửa được, Hoàn tất không khoá. Hoàn tác = lệnh mo-lai-kham (HoanTacService.mo_lai_kham) mở lại phiên.",
     "nguon": "src/clinicai/services/hoan_tac_service.py:418"
    }
   ]
  },
  {
   "id": "phong-dich-vu",
   "ten": "Chỉ định & phòng dịch vụ",
   "nhom": "hanh-trinh",
   "mau": "k4",
   "ngan": "Siêu âm, xét nghiệm, thủ thuật, đối tác; trưởng ca điều phối phòng.",
   "routes": [
    "/phong",
    "/phong/[ma]",
    "/truong-ca",
    "/truong-ca/lich-su",
    "/doi-tac",
    "/viec-can-xu-ly",
    "/print/ket-qua/[orderId]",
    "/duyet-ket-qua",
    "/xac-nhan-ket-qua",
    "/print/sono/[id]"
   ],
   "mo_ta": "Sau khi khách trả tiền, chỉ định được xếp vào hàng một phòng dịch vụ (siêu âm, thủ thuật, lấy mẫu, đối tác). Phòng bấm Bắt đầu → điền phiếu kết quả / tải tệp → Hoàn tất; trưởng ca điều phối phòng, bác sĩ duyệt kết quả, và việc rơi (không làm được mà đã thu tiền…) hiện ở Việc cần xử lý.",
   "dieu_phai_nho": [
    {
     "chu": "“Đã làm xong” (service.completed) và “đã có kết quả” (result.ready) là HAI sự thật khác nhau — kết quả đi qua phiếu (form_instance), không nằm trong lệnh Xong.",
     "vi_sao": "Lấy mẫu gửi ngoài thì làm xong hôm nay mà kết quả hai ngày sau mới về; gộp làm một là báo sai cho bác sĩ.",
     "nguon": "src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx:49"
    },
    {
     "chu": "Phòng chỉ có hai nút chính: [Bắt đầu] rồi [Hoàn tất]. Đã bỏ [Gọi vào]; ngoại lệ (Không làm được, Dừng giữa chừng, Làm lại) nằm ở hàng phụ.",
     "vi_sao": "Gọi vào → Bắt đầu là hai bước cho một việc; lệnh Bắt đầu đã tự dời con trỏ “khách đang ở đâu”.",
     "nguon": "src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx:31"
    },
    {
     "chu": "Không làm được mà khách ĐÃ trả tiền → hệ thống tự mở việc OPS-FINANCIAL-RESOLUTION ở /viec-can-xu-ly; không bao giờ tự hoàn tiền.",
     "vi_sao": "Trách nhiệm không được rơi; nhưng hoàn tiền là quyết định của người, có lệnh riêng của Tài chính.",
     "nguon": "src/clinicai/events/consumers/trach_nhiem.py:52"
    },
    {
     "chu": "Xếp / đổi phòng chỉ đi MỘT lệnh AssignServiceRoom; phòng đã gọi khách vào hoặc đang làm thì không kéo đi được (ROOM_ALREADY_CALLED).",
     "vi_sao": "Một cửa duy nhất giữ đúng revision, cổng tiền, quyền theo nguồn (quầy thu / trưởng ca); chuyển khi đang làm phải đi lệnh riêng có lý do.",
     "nguon": "src/clinicai/services/service_routing_service.py:1217"
    },
    {
     "chu": "Bẫy: trạng thái thật là service_order.execution_status; cột cũ exec_status chỉ là bản chiếu do trigger suy ra.",
     "vi_sao": "Bấm thật 23/09: phòng bấm Xong mà Bàn khám vẫn “Chờ ở phòng” vì màn đọc cột cũ — nên mới có trigger đồng bộ.",
     "nguon": "src/clinicai/services/service_execution_service.py:2327"
    }
   ],
   "man": [
    {
     "route": "/phong",
     "ten": "Danh sách phòng dịch vụ",
     "ai_dung": "BS siêu âm / thủ thuật, điều dưỡng (lego phong)",
     "lam_duoc": [
      "Thấy mọi phòng dịch vụ đang bật, phòng mình đứng hôm nay lên đầu",
      "Mỗi ô có 3 số: sắp đến · đang chờ · đang làm (máy chủ đếm)",
      "Bấm vào để mở /phong/<room_id>"
     ],
     "bang_doc": [
      "clinic_room",
      "queue_entry",
      "service_order",
      "work_roster"
     ],
     "bang_ghi": [],
     "toc_do_ghi_chu": "Server 1 lượt GET /api/v1/luot-kham/phong-hom-nay (phong/page.tsx); có LiveBoardSync nên VÀO màn dựng lại một lần và RealtimeRefresher dựng lại trang khi bảng của màn đổi (src/dashboard/app/(dashboard)/phong/page.tsx:63).",
     "ghi_chu": "Phòng KHÁM (bước KHAM-*) không nằm ở đây — dùng Bàn khám."
    },
    {
     "route": "/phong/[ma]",
     "ten": "Một phòng dịch vụ (siêu âm, thủ thuật, lấy mẫu)",
     "ai_dung": "BS siêu âm / thủ thuật, điều dưỡng (lego phong; lệnh hỏi quyền khối Thực hiện dịch vụ + ca ở phòng)",
     "lam_duoc": [
      "Hàng chờ phòng, danh sách Sắp đến / Chưa xếp phòng, nhận khách tại phòng (dây nhan_tai_phong)",
      "[Bắt đầu] → [Hoàn tất]; ngoại lệ Không làm được / Dừng giữa chừng / Làm lại / Huỷ bắt đầu",
      "Điền phiếu kết quả (form engine), tải ảnh/video/PDF vào ô tệp",
      "Việc đối tác: đã lấy mẫu, chờ tài liệu, trả kết quả",
      "Chọn ngày cũ để sửa kết quả (đi đường Sửa lại có lý do)"
     ],
     "bang_doc": [
      "queue_entry",
      "service_order",
      "service_execution_attempt",
      "form_instance",
      "tep_ket_qua",
      "visit"
     ],
     "bang_ghi": [
      "service_execution_attempt",
      "service_order",
      "queue_entry",
      "form_instance",
      "tep_ket_qua",
      "domain_event"
     ],
     "toc_do_ghi_chu": "Mở: phong-hom-nay (src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx:183) rồi hang-cho (src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx:205) + chip liệu trình (src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx:247) = 3; chọn khách thêm thuc-hien (src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx:572) + phiếu kết quả. Có tin 5 bảng queue_entry, service_order, visit, form_instance, tep_ket_qua → 1 lượt hang-cho (src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx:244); nhịp lưới 60 giây (src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx:236). Sau mỗi lệnh: đọc lại thuc-hien + nạp lại hàng chờ (src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx:622).",
     "ghi_chu": "Lệch tài liệu: GIAI-THICH-CODE mục service_order_service/work_item_service (docs/GIAI-THICH-CODE.md:5012) còn tả “chỉ định sinh việc ở phòng” qua work_item; code hiện tại phòng ghi service_execution_attempt + service_order.execution_status, work_item chỉ còn cho việc vận hành. Bảng service_log (gợi ý trong đề) là đường cũ của /sono, không còn màn nào ghi."
    },
    {
     "route": "/doi-tac",
     "ten": "Việc của đối tác (phòng xét nghiệm ngoài)",
     "ai_dung": "Tài khoản Đối tác (lego doi_tac), quản lý",
     "lam_duoc": [
      "Nhận việc phòng khám gửi sang theo ngày",
      "Ghi đã lấy mẫu / đã thu tiền / chờ tài liệu, huỷ các mốc ấy",
      "Điền phiếu kết quả và gửi tệp kết quả về"
     ],
     "bang_doc": [
      "service_order",
      "form_instance",
      "tep_ket_qua",
      "visit"
     ],
     "bang_ghi": [
      "service_order",
      "form_instance",
      "tep_ket_qua"
     ],
     "toc_do_ghi_chu": "Không dùng useNgheBang; tự hỏi lại mỗi 20 giây (src/dashboard/app/doi-tac/BangDoiTac.tsx:208), mỗi lần 1 lượt /api/doi-tac (src/dashboard/app/doi-tac/BangDoiTac.tsx:114).",
     "ghi_chu": "Trang nằm ngoài nhóm (dashboard) nên tự gác quyền; dữ liệu chỉ qua FastAPI (get_partner_identity), không PostgREST."
    },
    {
     "route": "/duyet-ket-qua",
     "ten": "Duyệt kết quả (bác sĩ phê duyệt cho gửi)",
     "ai_dung": "Bác sĩ (cửa API chỉ đòi đăng nhập; lệnh tự hỏi quyền)",
     "lam_duoc": [
      "Mỗi thẻ là một chỉ định đã có kết quả, xem tệp ngay trong thẻ",
      "Ghi đánh giá + [Phê duyệt cho gửi] → CSKH thấy “Đã có kết quả”",
      "Hoàn tác = thu hồi duyệt về chờ duyệt"
     ],
     "bang_doc": [
      "service_order",
      "form_instance",
      "tep_ket_qua"
     ],
     "bang_ghi": [
      "service_order",
      "tep_ket_qua"
     ],
     "toc_do_ghi_chu": "Mở 1 lượt ket-qua-cho-duyet (src/dashboard/app/(dashboard)/duyet-ket-qua/DuyetKetQua.tsx:44); không thấy useNgheBang — chưa rõ có tự hiện kết quả mới không (chỉ nạp lại sau thao tác).",
     "ghi_chu": "Thay cho /result-review cũ (duyệt theo tệp rời)."
    },
    {
     "route": "/xac-nhan-ket-qua",
     "ten": "Xác nhận tệp kết quả của đối tác",
     "ai_dung": "Nhân sự có quyền ket_qua.xac_nhan (vận hành kiểm trước khi bác sĩ duyệt)",
     "lam_duoc": [
      "Hàng tệp kết quả đối tác gửi về chờ xác nhận",
      "Xác nhận đúng khách/đúng chỉ định hoặc từ chối kèm lý do",
      "Xem nội dung tệp"
     ],
     "bang_doc": [
      "tep_ket_qua",
      "service_order"
     ],
     "bang_ghi": [
      "tep_ket_qua"
     ],
     "toc_do_ghi_chu": "Mở 1 lượt /api/cskh/ket-qua/cho-xac-nhan (src/dashboard/app/(dashboard)/xac-nhan-ket-qua/HangChoXacNhanKetQua.tsx:85); không useNgheBang.",
     "ghi_chu": "Comment trang ghi rõ: mới chạy thử với MỘT đối tác (single-partner pilot)."
    },
    {
     "route": "/truong-ca",
     "ten": "Điều phối ca (hàng đợi theo trạm)",
     "ai_dung": "Trưởng ca (lego dieu_phoi)",
     "lam_duoc": [
      "Mỗi phòng một thẻ, khách chờ quá ngưỡng tô đỏ, cảnh báo phòng quá tải",
      "Bấm khách → popup đổi phòng; kéo khách sang phòng cùng chức năng",
      "Đổi bác sĩ, áp tuyến, đặt ngưỡng chờ",
      "Mở TV phòng chờ từng phòng"
     ],
     "bang_doc": [
      "visit",
      "queue_entry",
      "service_order",
      "consultation",
      "encounter_flow",
      "work_item"
     ],
     "bang_ghi": [
      "service_order",
      "queue_entry",
      "visit"
     ],
     "toc_do_ghi_chu": "Server 2 lượt overview + alerts (src/dashboard/app/(dashboard)/truong-ca/load.ts:25), client thêm history (src/dashboard/app/(dashboard)/truong-ca/QueuesClient.tsx:46). Có tin 7 bảng LIVE_TABLES → pull 2 lượt overview + alerts (src/dashboard/app/(dashboard)/truong-ca/shared.tsx:84); trang còn gắn LiveBoardSync và không nằm trong MAN_TU_TAI nên RealtimeRefresher có thể dựng lại trang server (thêm 2 lượt) cho cùng tin (src/dashboard/app/(dashboard)/truong-ca/page.tsx:19).",
     "ghi_chu": "Lệch tài liệu: GIAI-THICH-CODE §6.4 ghi DispatchService.move ở dòng :221, code hiện tại ở src/clinicai/services/dispatch_service.py:462."
    },
    {
     "route": "/truong-ca/lich-su",
     "ten": "Lịch sử điều phối",
     "ai_dung": "Trưởng ca (lego dieu_phoi)",
     "lam_duoc": [
      "Xem ai chuyển ai, từ đâu sang đâu, vì sao (200 dòng gần nhất)"
     ],
     "bang_doc": [
      "event_log",
      "visit"
     ],
     "bang_ghi": [],
     "toc_do_ghi_chu": "Server 1 lượt /api/v1/dispatch/history?limit=200 (src/dashboard/app/(dashboard)/truong-ca/load.ts:49).",
     "ghi_chu": "Đọc view v_dispatch_history (theo GIAI-THICH-CODE §6.4); bảng gốc chính xác chưa kiểm."
    },
    {
     "route": "/viec-can-xu-ly",
     "ten": "Việc cần xử lý (trách nhiệm không được rơi)",
     "ai_dung": "Quản lý, trưởng ca (lego viec_can_xu_ly)",
     "lam_duoc": [
      "Thấy việc OPS-FINANCIAL-RESOLUTION (đã thu mà không làm), OPS-SERVICE-INTERRUPTED (dừng giữa chừng), OPS-ROUTING-REASSIGN (cần xếp lại phòng)",
      "Bấm [Đã xử lý] đóng việc",
      "Xem nhanh lượt khám của việc"
     ],
     "bang_doc": [
      "work_item",
      "work_item_event",
      "staff_task"
     ],
     "bang_ghi": [
      "work_item",
      "work_item_event"
     ],
     "toc_do_ghi_chu": "Mở 1 lượt /api/work-items?workspace=khu_van_hanh (src/dashboard/app/(dashboard)/viec-can-xu-ly/BangViecCanXuLy.tsx:55); có tin work_item/work_item_event/staff_task → nạp lại (src/dashboard/app/(dashboard)/viec-can-xu-ly/BangViecCanXuLy.tsx:101). [Đã xử lý] gửi 2 lệnh tuần tự start → complete rồi await nạp lại (src/dashboard/app/(dashboard)/viec-can-xu-ly/BangViecCanXuLy.tsx:128).",
     "ghi_chu": "Máy trạng thái chỉ cho complete từ IN_PROGRESS — việc mới luôn PENDING nên màn phải gửi start trước."
    },
    {
     "route": "/print/ket-qua/[orderId]",
     "ten": "In phiếu kết quả một chỉ định (A4)",
     "ai_dung": "Nhân sự phòng khám đã đăng nhập (requireClinicRole)",
     "lam_duoc": [
      "In kết quả form engine của một chỉ định kèm ảnh"
     ],
     "bang_doc": [
      "form_instance",
      "service_order",
      "tep_ket_qua"
     ],
     "bang_ghi": [],
     "toc_do_ghi_chu": "1 lượt /api/phieu?in=<orderId> (src/dashboard/app/print/ket-qua/[orderId]/InKetQua.tsx:329) + ảnh đọc qua /api/cskh/ket-qua/<id>/noi-dung.",
     "ghi_chu": "Đây là phiếu in kết quả hiện hành, thay /print/sono."
    },
    {
     "route": "/print/sono/[id]",
     "ten": "Phiếu in siêu âm kiểu cũ (ĐÃ TẮT)",
     "ai_dung": "Không ai — trang chỉ hiện câu báo đã tắt",
     "lam_duoc": [
      "Không làm gì; chỉ báo dùng /print/ket-qua/[orderId]"
     ],
     "bang_doc": [],
     "bang_ghi": [],
     "toc_do_ghi_chu": "",
     "ghi_chu": "Tắt 24/09/2026; bản cũ đọc thẳng service_log bằng Supabase (src/dashboard/app/print/sono/[id]/page.tsx:1). Không phải redirect nên vẫn liệt kê ở đây."
    }
   ],
   "chuyen_huong": [
    {
     "route": "/lab-queue",
     "toi": "/phong"
    },
    {
     "route": "/service-queue",
     "toi": "/phong"
    },
    {
     "route": "/sieu-am",
     "toi": "/phong"
    },
    {
     "route": "/sono",
     "toi": "/phong"
    },
    {
     "route": "/truong-ca/hang-doi",
     "toi": "/truong-ca"
    }
   ],
   "thao_tac": [
    {
     "man": "/phong/[ma]",
     "nut": "Bấm [Bắt đầu] cho một khách trong hàng chờ phòng",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "PhongDichVu.tsx batDau → lenh(\"bat-dau-v1\", {expected_execution_revision, expected_routing_revision, giai_phong})",
       "nguon": "src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx:628"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/luot-kham/orders/{id}/execution/bat-dau",
       "nguon": "src/clinicai/api/v1/routers/luot_kham.py:1112"
      },
      {
       "loai": "ham",
       "chu": "ServiceExecutionService.bat_dau (mở một LẦN LÀM: kiểm quyền + ca ở phòng, cổng tiền, revision; khách bận phòng khác thì hỏi chuyển)",
       "nguon": "src/clinicai/services/service_execution_service.py:372"
      },
      {
       "loai": "bang",
       "chu": "INSERT service_execution_attempt (IN_PROGRESS, giờ vào); service_order.execution_status = IN_PROGRESS; queue_entry → serving; dời vị trí visit",
       "nguon": "src/clinicai/services/service_execution_service.py:471"
      },
      {
       "loai": "su_kien",
       "chu": "pg_notify service_order, queue_entry + service.started (consumer dòng thời gian, sổ nợ)",
       "nguon": "src/clinicai/services/service_execution_service.py:546"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "Phòng tự nạp lại; Bàn khám thấy “Đang làm”; /truong-ca, /thu-ngan/dich-vu nạp lại",
       "nguon": "src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx:244"
      }
     ],
     "ghi_chu": "Bấm nhầm → huy-bat-dau-v1 (chỉ khi chưa điền phiếu). Cùng phòng đang làm dịch vụ khác của khách → 409 CUNG_PHONG_DANG_LAM, màn hỏi [Xong DV1 & bắt đầu DV2]."
    },
    {
     "man": "/phong/[ma]",
     "nut": "Điền phiếu kết quả rồi bấm [Hoàn tất]",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "PhieuKetQua.tsx gửi POST /api/phieu {thao_tac: hoan-tat, expected_revision, thuc_hien_boi, ly_do_sua}",
       "nguon": "src/dashboard/app/(dashboard)/_lam-viec/PhieuKetQua.tsx:318"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/phieu/{phieu_id}/hoan-tat (CompleteForm)",
       "nguon": "src/clinicai/api/v1/routers/phieu.py:100"
      },
      {
       "loai": "ham",
       "chu": "FormEngineService.hoan_tat (xác nhận TOÀN BỘ phiếu; sửa lại thì bắt buộc lý do; đóng hộ dịch vụ đang làm dở)",
       "nguon": "src/clinicai/services/form_engine_service.py:671"
      },
      {
       "loai": "bang",
       "chu": "UPDATE form_instance trang_thai=READY, hoan_tat_boi/luc, revision+1; lần sửa ghi visit_amendment",
       "nguon": "src/clinicai/services/form_engine_service.py:819"
      },
      {
       "loai": "su_kien",
       "chu": "pg_notify form_instance (chỉ khi đổi trang_thai/dang_sua) + result_form.completed + result.ready (chỉ dịch vụ có kết quả ngay tại phòng)",
       "nguon": "src/clinicai/services/form_engine_service.py:898"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "Bàn khám: kết quả tự hiện dưới mục C (PhieuKhamLuot nghe service_order, form_instance, tep_ket_qua)",
       "nguon": "src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx:268"
      }
     ],
     "ghi_chu": "Dịch vụ không có phiếu (lấy mẫu gửi đi) thì [Hoàn tất] gọi thẳng xong-v1 → ServiceExecutionService.xong → service.completed (src/clinicai/services/service_execution_service.py:579)."
    },
    {
     "man": "/phong/[ma]",
     "nut": "Bấm [Không làm được] (hàng phụ) kèm lý do",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "PhongDichVu.tsx gửi lenh(\"khong-lam-v1\", {lý do, revision})",
       "nguon": "src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx:1127"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/luot-kham/orders/{id}/execution/khong-lam",
       "nguon": "src/clinicai/api/v1/routers/luot_kham.py:1168"
      },
      {
       "loai": "ham",
       "chu": "ServiceExecutionService.khong_lam (đánh dấu không làm, đóng chỗ chờ, xem đã thu tiền chưa)",
       "nguon": "src/clinicai/services/service_execution_service.py:648"
      },
      {
       "loai": "bang",
       "chu": "service_order.execution_status = NOT_PERFORMED (+ lý do); queue_entry đóng; consumer trach_nhiem INSERT work_item OPS-FINANCIAL-RESOLUTION nếu đã thu",
       "nguon": "src/clinicai/events/consumers/trach_nhiem.py:110"
      },
      {
       "loai": "su_kien",
       "chu": "service.not_performed (da_thu_tien) → consumer TRACH_NHIEM_DICH_VU, VONG_DOC, SO_NO; hẹn kiểm lại sau 4 giờ, quá hạn nâng P0",
       "nguon": "src/clinicai/events/catalogue.py:1626"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "/viec-can-xu-ly hiện việc mới (useNgheBang work_item, work_item_event, staff_task)",
       "nguon": "src/dashboard/app/(dashboard)/viec-can-xu-ly/BangViecCanXuLy.tsx:101"
      }
     ],
     "ghi_chu": "Chưa thu tiền thì KHÔNG mở việc (src/clinicai/events/consumers/trach_nhiem.py:66). Việc không tự hoàn tiền; người xử lý xong bấm [Đã xử lý] = start → complete trên work_item."
    },
    {
     "man": "/truong-ca",
     "nut": "Kéo khách sang phòng cùng chức năng (hoặc chọn phòng trong popup)",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "keo-tha.ts timDichDen đọc chỉ định + gợi ý phòng, thả xuống gọi guiThaoTac(\"xep-phong-v1\", {room_id, expected_routing_revision, nguon: truong_ca})",
       "nguon": "src/dashboard/app/(dashboard)/truong-ca/keo-tha.ts:48"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/luot-kham/orders/{id}/routing/assign (AssignServiceRoom)",
       "nguon": "src/clinicai/api/v1/routers/luot_kham.py:843"
      },
      {
       "loai": "ham",
       "chu": "ServiceRoutingService.assign (lệnh DUY NHẤT xếp/đổi phòng; quyền service.routing.assign theo nguồn)",
       "nguon": "src/clinicai/services/service_routing_service.py:1204"
      },
      {
       "loai": "bang",
       "chu": "queue_entry đổi room_id (giữ tuổi chờ) hoặc INSERT chỗ chờ mới; service_order routing_status=ASSIGNED, room_id, routing_revision+1",
       "nguon": "src/clinicai/services/service_routing_service.py:2425"
      },
      {
       "loai": "su_kien",
       "chu": "pg_notify queue_entry, service_order + service.routed (consumer dòng thời gian lượt)",
       "nguon": "src/clinicai/services/service_routing_service.py:1460"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "/phong/[ma] của cả hai phòng nạp lại hàng chờ; /truong-ca pull overview + alerts; quầy thu nạp lại",
       "nguon": "src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx:244"
      }
     ],
     "ghi_chu": "Phòng hiện tại đã gọi/đang làm → ROOM_ALREADY_CALLED (src/clinicai/services/service_routing_service.py:2420). Dịch vụ ĐANG LÀM muốn chuyển phải dùng chuyen-phong-dang-lam, bắt buộc lý do (src/clinicai/api/v1/routers/luot_kham.py:901)."
    }
   ],
   "the": [
    {
     "hoi": "Phòng dịch vụ bấm [Bắt đầu] thì ghi vào bảng nào (không phải work_item)?",
     "dap": "INSERT service_execution_attempt (một lần làm) + service_order.execution_status = IN_PROGRESS.",
     "nguon": "src/clinicai/services/service_execution_service.py:471"
    },
    {
     "hoi": "/phong/[ma] nghe những bảng nào?",
     "dap": "queue_entry, service_order, visit, form_instance, tep_ket_qua — mỗi tin 1 lượt hang-cho.",
     "nguon": "src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx:244"
    },
    {
     "hoi": "Lưu nháp phiếu kết quả có làm Bàn khám nạp lại không?",
     "dap": "Không. Trigger form_instance chỉ bắn khi đổi trang_thai hoặc dang_sua (Hoàn tất / Mở sửa), không bắn khi lưu nháp du_lieu.",
     "nguon": "supabase/migrations/20260926000007_notify_ket_qua_hanh_trinh.sql:14"
    },
    {
     "hoi": "Sự kiện nào mở việc OPS-FINANCIAL-RESOLUTION, và khi nào thì không mở?",
     "dap": "service.not_performed — chỉ mở khi payload da_thu_tien = true; phát lại lịch sử cũng không mở.",
     "nguon": "src/clinicai/events/consumers/trach_nhiem.py:66"
    },
    {
     "hoi": "Sửa lại kết quả đã Hoàn tất cần gì?",
     "dap": "Bắt buộc lý do (ly_do_sua), lưu vào visit_amendment; phát result.corrected thay vì result.ready.",
     "nguon": "src/clinicai/services/form_engine_service.py:686"
    },
    {
     "hoi": "Vì sao màn /viec-can-xu-ly gửi hai lệnh khi bấm [Đã xử lý]?",
     "dap": "Máy trạng thái work_item chỉ cho complete từ IN_PROGRESS; việc mới mở luôn PENDING nên phải start trước.",
     "nguon": "src/dashboard/app/(dashboard)/viec-can-xu-ly/BangViecCanXuLy.tsx:128"
    }
   ]
  },
  {
   "id": "thu-ngan",
   "ten": "Thu ngân",
   "nhom": "hanh-trinh",
   "mau": "k5",
   "ngan": "Quầy thu tiền dịch vụ và tiền thuốc, hoàn tiền, trả trước liệu trình.",
   "routes": [
    "/thu-ngan/dich-vu",
    "/thu-ngan/thuoc",
    "/thu-ngan/dich-vu/lich-su",
    "/thu-ngan/thuoc/lich-su",
    "/print/phieu-thu/[id]"
   ]
  },
  {
   "id": "thuoc",
   "ten": "Cấp thuốc",
   "nhom": "hanh-trinh",
   "mau": "k6",
   "ngan": "Dược sĩ chọn lô, giao thuốc đã thu tiền, tư vấn cách dùng.",
   "routes": [
    "/pharmacy",
    "/pharmacy/consult",
    "/pharmacy/history",
    "/print/hoa-don-thuoc/[visitId]",
    "/print/tem-lo"
   ]
  },
  {
   "id": "check-out",
   "ten": "Check-out",
   "nhom": "hanh-trinh",
   "mau": "k7",
   "ngan": "Cho khách về: kiểm việc còn dở, tiền còn nợ, đóng lượt khám.",
   "routes": [
    "/reception/checkout"
   ]
  },
  {
   "id": "sau-kham",
   "ten": "Trả kết quả & CSKH",
   "nhom": "hanh-trinh",
   "mau": "k8",
   "ngan": "Gửi kết quả, gọi chăm sóc, nhắc tái khám, theo dõi liệu trình.",
   "routes": [
    "/customers",
    "/nhac-tai-kham",
    "/print/ket-qua-luot/[visitId]"
   ]
  },
  {
   "id": "kho",
   "ten": "Kho thuốc & vật tư",
   "nhom": "hau-truong",
   "mau": "k9",
   "ngan": "Nhập lô, tồn kho, kiểm kê ca, xuất vật tư theo nơi chứa.",
   "routes": [
    "/pharmacy/inventory",
    "/kho-vat-tu"
   ]
  },
  {
   "id": "bao-cao",
   "ten": "Báo cáo & tài chính",
   "nhom": "hau-truong",
   "mau": "k10",
   "ngan": "Báo cáo vận hành, cuối ngày, danh sách và xuất hoá đơn, kế toán.",
   "routes": [
    "/reports",
    "/hoa-don",
    "/xuat-hoa-don",
    "/ke-toan"
   ]
  },
  {
   "id": "nhan-su",
   "ten": "Nhân sự, lịch trực & quyền",
   "nhom": "hau-truong",
   "mau": "k11",
   "ngan": "Tài khoản, lịch làm việc, bật/tắt lego quyền, đăng nhập và chọn cơ sở.",
   "routes": [
    "/nhan-su",
    "/schedule",
    "/phan-quyen",
    "/settings/tai-khoan",
    "/settings/new-user",
    "/chon-co-so",
    "/login",
    "/forgot-password",
    "/reset-password",
    "/"
   ]
  },
  {
   "id": "cai-dat",
   "ten": "Cài đặt & vận hành",
   "nhom": "hau-truong",
   "mau": "k12",
   "ngan": "Bảng giá, phòng, luật đặt lịch, dây nối nghiệp vụ, mẫu kết quả, theo dõi lỗi.",
   "routes": [
    "/settings",
    "/cashier/dich-vu",
    "/cashier/thuoc",
    "/settings/clinic-config",
    "/settings/booking-policy",
    "/settings/day-noi",
    "/settings/mau-ket-qua",
    "/settings/don-du-lieu-thu",
    "/ops",
    "/audit-log",
    "/giam-sat",
    "/traffic",
    "/console",
    "/design-system"
   ]
  }
 ],
 "the_chung": [],
 "toc_do": {
  "/thu-ngan/dich-vu": {
   "den": "do",
   "nguon": "đã đo (prod 14–17/10)",
   "link": "https://github.com/Avalook/Clinic-AI-MacMini/pull/530",
   "chu": "Tải bảng quầy thu p95 ~3,4s; câu SQL quầy thu trung bình 4,3s, tối đa 14s. Ghi một lần thu chỉ ~0,13s — chậm nằm ở bảng, không ở nút. Gốc: CashierBoardService.board tính hoá đơn TỪNG khách nối tiếp (~10–25 câu SQL/khách) và vế 'lượt cũ chưa về' không có mốc ngày (#530 B4, cashier_board_service.py:593, 708–772). Sau khi bấm [Đã nhận đủ] màn còn await tai() tải lại cả bảng rồi mới tắt nút (QuayThuNgan.tsx:394)."
  },
  "/thu-ngan/thuoc": {
   "den": "do",
   "nguon": "đã đo (prod 14–17/10)",
   "link": "https://github.com/Avalook/Clinic-AI-MacMini/pull/530",
   "chu": "Cùng bảng quầy thu với /thu-ngan/dich-vu (cùng CashierBoardService.board, cùng QuayThuNgan.tsx) nên chung số đo p95 ~3,4s và chung gốc N+1 (#530 B4)."
  },
  "/reception/checkout": {
   "den": "do",
   "nguon": "báo cáo rà soát #530 (theo code, mức CAO)",
   "link": "https://github.com/Avalook/Clinic-AI-MacMini/pull/530",
   "chu": "N+1 tới 300 lượt × 15–25 câu: vòng lặp gọi hoa_don_con_no cho từng lượt (checkout_service.py:1071), và mỗi tin thời gian thực chạy nó HAI lần (trang không thuộc màn tự tải + LiveBoardSync) — #530 D2. Chưa có số đo riêng."
  },
  "/ban-kham": {
   "den": "vang",
   "nguon": "đã đo (prod 14–17/10)",
   "link": "https://github.com/Avalook/Clinic-AI-MacMini/pull/530",
   "chu": "SSR trung bình ~0,9s (đo 14/10: 880ms, tối đa 11,3s) dù phần máy chủ gần như trống. Gốc: layout gọi /phan-quyen/toi lặp một câu SQL cho mỗi ngày trực (#530 D1, cashier_scope_service.py:243) + 3 đợt gọi nối tiếp ở layout (D3). Phía trình duyệt: 3 lời gọi cho mỗi tin của 8 bảng nóng, tin 'không rõ bảng' bắn ~15 lời gọi (C2)."
  },
  "/ban-kham/[phong]": {
   "den": "vang",
   "nguon": "đã đo (prod 14–17/10)",
   "link": "https://github.com/Avalook/Clinic-AI-MacMini/pull/530",
   "chu": "Cùng trang Bàn khám (BanKham.tsx) — chung số đo SSR ~0,9s và chung gốc D1/D3/C2 của #530."
  },
  "/tu-van": {
   "den": "vang",
   "nguon": "báo cáo rà soát #530 (theo code)",
   "link": "https://github.com/Avalook/Clinic-AI-MacMini/pull/530",
   "chu": "Dùng chung khung làm việc với Bàn khám nên chịu cùng 'phí vào cửa' của layout (#530 D1, D3) và cùng kiểu nghe nhiều bảng (C2). Chưa đo riêng."
  },
  "/phong/[ma]": {
   "den": "vang",
   "nguon": "đã đo (prod 14–17/10)",
   "link": "https://github.com/Avalook/Clinic-AI-MacMini/pull/530",
   "chu": "SSR /phong/{id} trung bình ~0,9s (đo 14/10: 866ms, tối đa 14,3s). Gốc chính là layout (#530 D1 /phan-quyen/toi, D3), không phải dữ liệu của phòng — trang đã là màn tự tải."
  },
  "/reception/queue": {
   "den": "vang",
   "nguon": "đã đo (prod 14–17/10)",
   "link": "https://github.com/Avalook/Clinic-AI-MacMini/pull/530",
   "chu": "SSR trung bình ~0,9s. Ngoài phí layout (#530 D1/D3), màn này vừa tự router.refresh() sau thao tác vừa bị tin SSE dựng lại lần nữa (C1, QueueBoard.tsx:113); bảng lịch đọc v_viec_cskh → lich_vuot_suc_chua() quét mọi phòng khám (B3)."
  },
  "/home": {
   "den": "vang",
   "nguon": "báo cáo rà soát #530 (theo code)",
   "link": "https://github.com/Avalook/Clinic-AI-MacMini/pull/530",
   "chu": "Bảng lịch tuần đọc v_viec_cskh, view này gọi lich_vuot_suc_chua() quét mọi lịch tương lai của mọi phòng khám mỗi lần đọc (#530 B3). Trang thường: dựng lại theo mọi tin của LIVE_TABLES (A1)."
  },
  "/customers": {
   "den": "vang",
   "nguon": "báo cáo rà soát #530 (theo code)",
   "link": "https://github.com/Avalook/Clinic-AI-MacMini/pull/530",
   "chu": "Ghi nhac_tai_kham ngay trong lúc dựng trang (#530 D4, customers/page.tsx:296) — mỗi lần dựng lại vì tin thời gian thực là một lần ghi, ghi lại bắn tin."
  },
  "/truong-ca": {
   "den": "vang",
   "nguon": "báo cáo rà soát #530 (theo code)",
   "link": "https://github.com/Avalook/Clinic-AI-MacMini/pull/530",
   "chu": "Trang đọc dữ liệu sống ở máy chủ (15 lời gọi FastAPI lúc dựng) và có LiveBoardSync: mỗi tin của LIVE_TABLES dựng lại cả trang (#530 A1, C1)."
  },
  "/phong": {
   "den": "vang",
   "nguon": "báo cáo rà soát #530 (theo code)",
   "link": "https://github.com/Avalook/Clinic-AI-MacMini/pull/530",
   "chu": "Danh sách phòng có số khách đọc ở máy chủ nên không được vào màn tự tải; có LiveBoardSync → vào màn dựng hai lần, rồi dựng lại theo mọi tin (#530 C1, A1)."
  }
 },
 "toc_do_chung": {
  "mo_dau": "Không đo được prod từ máy cloud. Mỗi đèn ghi rõ nguồn: <b>đã đo</b> = số prod 14–17/10; <b>báo cáo rà soát #530</b> = phát hiện trong <a href='https://github.com/Avalook/Clinic-AI-MacMini/pull/530'>PR #530 (soát 22/10, khối 1 — tốc độ)</a>, đọc code cùng commit; <b>theo code</b> = script tự xếp từ dấu hiệu trong code (vòng lặp await truy vấn, số lời gọi máy chủ lúc dựng trang, số chỗ router.refresh), chờ khớp số đo. Đèn tự xếp là gợi ý để nhìn, không phải kết luận.",
  "diem": [
   {
    "chu": "Mỗi lần ghi kéo 7–10 lần dựng lại trang ở mọi tab đang mở (đã đo): RealtimeRefresher dựng lại toàn trang khi bất kỳ bảng nào trong LIVE_TABLES đổi, trừ màn tự tải (#530 A1).",
    "nguon": "src/dashboard/app/(dashboard)/RealtimeRefresher.tsx:88"
   },
   {
    "chu": "'Phí vào cửa' của mọi trang: layout gọi /phan-quyen/toi, hàm này lặp một câu SQL cho từng ngày trực của người không đứng quầy thu — chậm dần theo số ngày (#530 D1, ưu tiên sửa số 1).",
    "nguon": "src/clinicai/services/cashier_scope_service.py:243"
   },
   {
    "chu": "Layout chạy 3 đợt lời gọi nối tiếp, không cache giữa hai lần dựng (#530 D3).",
    "nguon": "src/dashboard/app/(dashboard)/layout.tsx:46"
   },
   {
    "chu": "Màn tự tải (không bị dựng lại cả trang theo tin): /ban-kham, /tu-van, /phong/[ma], /hanh-trinh, /thu-ngan/*. Danh sách nằm ở lib/man-tu-tai.ts.",
    "nguon": "src/dashboard/lib/man-tu-tai.ts:23"
   },
   {
    "chu": "Tin thời gian thực không mang cơ sở: ghi ở cơ sở B vẫn dựng lại màn ở cơ sở A (#530 E2).",
    "nguon": "supabase/migrations/20260806000001_notify_change_for_live_screens.sql:29"
   },
   {
    "chu": "Worker đối chiếu sổ nợ tính lại số dư tới 300 lượt mỗi 10 phút suốt giờ khám — nghi là nguồn chính của câu SQL chạy 67 nghìn lần (#530 B1).",
    "nguon": "src/clinicai/services/so_no_service.py:79"
   }
  ]
 },
 "xuyen_khoi": [
  "<b>Một lượt khám</b> (<code>visit</code>) là sợi chỉ xuyên mọi khối: lịch hẹn (<code>appointment</code>) check-in thì sinh lượt; chỉ định (<code>service_order</code>), đơn thuốc (<code>prescription</code>), lần thu (<code>payment_cycle</code>) đều treo vào lượt; check-out đóng lượt.",
  "<b>Giao diện chỉ vẽ và gửi lệnh.</b> Màn Next.js → route <code>app/api/**/route.ts</code> (chỉ chuyển tiếp) → FastAPI <code>/api/v1/…</code> (router mỏng) → hàm dịch vụ trong <code>src/clinicai/services</code> (luật nghiệp vụ) → Postgres.",
  "<b>Màn khác tự cập nhật thế nào:</b> bảng có trigger <code>notify_row_change</code> → <code>pg_notify</code> → FastAPI SSE <code>/api/events/stream</code> → <code>RealtimeRefresher</code> (dựng lại trang thường) hoặc <code>useNgheBang([...])</code> (màn tự tải hỏi lại đúng thứ nó vẽ).",
  "<b>Sự kiện nghiệp vụ</b> (vd khách đã trả mà dịch vụ không làm được) đi đường khác: hàm dịch vụ ghi sự kiện → worker <code>su-kien</code> chạy consumer → sinh việc ở <i>Việc cần xử lý</i>, thông báo, sổ nợ."
 ],
 "cach_doc": [
  "<b>Bốn tầng, đi từ to đến nhỏ.</b> Tầng 1 là trang đầu: hành trình khách và dải hậu trường. Bấm một khối → tầng 2: 5 điều phải nhớ, các màn, đường đi thao tác. Bấm một màn → tầng 3: tốc độ, nút nào đi đâu, bảng dữ liệu, toàn bộ API phía sau. Tầng 4 là Từ điển tên. Dòng 'Hành trình › …' ở đầu trang luôn đưa bạn quay lên.",
  "<b>Tên dễ hiểu đi trước, tên code viết nhỏ đi sau.</b> Mọi chip tên bảng/hàm bấm được: nó mở Từ điển, tìm sẵn tên đó. Rê chuột lên chip để xem nghĩa từng mảnh.",
  "<b>Hai nguồn dữ liệu.</b> <code>docs/so-hoc/du-lieu-sinh.js</code> do <code>python3 scripts/so-hoc-data.py</code> sinh từ code (màn → API → hàm router → service → bảng, nghe bảng nào, nghi N+1 ở đâu) — đừng sửa tay. <code>docs/so-hoc/viet-tay.js</code> là phần viết tay (khối, tên dễ hiểu, 5 điều phải nhớ, đường đi thao tác, thẻ, từ điển, đèn đã đo) — sửa thoải mái.",
  "<b>Giữ cho đúng.</b> Sau khi sửa code hay sửa viet-tay.js: <code>python3 scripts/so-hoc-data.py</code> (sinh lại + kiểm). <code>python3 scripts/so-hoc-data.py --kiem</code> chỉ kiểm: mọi <code>tệp:dòng</code> trong phần viết tay phải còn tồn tại, mọi route phải có màn. Dòng có thể trôi khi code đổi — script chỉ bắt được tệp mất hoặc dòng vượt cuối tệp.",
  "<b>Bảng 'Đọc/Ghi' của màn.</b> Ở tầng 2 là bảng chính viết tay (đã soát). Ở tầng 3 là bảng suy từ chuỗi SQL trong các hàm service màn gọi (đi tối đa một tầng hàm cùng tệp) — đủ để định hướng, có thể sót bảng ghi qua hàm ở tệp khác.",
  "<b>'Nghi N+1'</b> = vòng for/while có <code>await</code> một truy vấn (trực tiếp hoặc qua hàm cùng tệp). Vòng 3 phần tử cũng bị bắt, nên đó là chỗ để mở ra xem, không phải lỗi chắc chắn.",
  "<b>Mở trang:</b> bấm đúp <code>docs/so-hoc/index.html</code> (file://), hoặc <code>python3 -m http.server -d docs/so-hoc 8765</code> rồi mở http://localhost:8765. Không cần mạng, không thư viện ngoài."
 ],
 "tu_dien": [
  {
   "ma": "_tat_loi_cu",
   "loai": "hàm",
   "ten": "Tắt cửa API cũ: trả 410 và ghi log ai còn gọi",
   "manh": "tat = tắt · loi cu = lối cũ",
   "dong_nghia": [
    "LOI_CU_MO",
    "ENDPOINT_RETIRED"
   ],
   "nguon": "src/clinicai/api/v1/routers/luot_kham.py:42"
  },
  {
   "ma": "BangLuotKham",
   "loai": "hàm",
   "ten": "Bộ đọc bảng lượt khám (bang, hang_cho, phong_hom_nay, ket_qua_cho_duyet)",
   "manh": "bang = bảng · luot kham = lượt khám",
   "dong_nghia": [
    "luot_kham_doc.py"
   ],
   "nguon": "src/clinicai/services/luot_kham_doc.py:71"
  },
  {
   "ma": "BanKham.tsx",
   "loai": "tệp",
   "ten": "Màn Bàn khám (dùng chung cho /ban-kham, /ban-kham/[phong], /tu-van)",
   "manh": "ban = bàn · kham = khám",
   "dong_nghia": [
    "Bàn khám tư vấn (cheDo tu_van)",
    "doctor board (cũ)"
   ],
   "nguon": "src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:226"
  },
  {
   "ma": "ChiDinhService.dat_chi_dinh",
   "loai": "hàm",
   "ten": "Chốt chỉ định dịch vụ (một lệnh, không nháp)",
   "manh": "chi dinh = chỉ định · dat = đặt",
   "dong_nghia": [
    "PlaceServiceOrders",
    "CD-01",
    "chi-dinh"
   ],
   "nguon": "src/clinicai/services/chi_dinh_service.py:135"
  },
  {
   "ma": "complete_consultation",
   "loai": "hàm",
   "ten": "Khép phiên khám với kết quả + kế hoạch dịch vụ",
   "manh": "complete = hoàn tất · consultation = phiên khám",
   "dong_nghia": [
    "ket-thuc-kham",
    "consultation.completed"
   ],
   "nguon": "src/clinicai/services/luot_kham_service.py:2446"
  },
  {
   "ma": "consultation",
   "loai": "bảng",
   "ten": "Phiên khám (PRIMARY khám chính, REVIEW đọc kết quả, TU_VAN tư vấn)",
   "manh": "consultation = buổi khám/tư vấn",
   "dong_nghia": [
    "phiên khám",
    "kind"
   ],
   "nguon": "supabase/migrations/20260911000001_luot_kham_lat_1.sql:95"
  },
  {
   "ma": "consultation.completed",
   "loai": "sự kiện",
   "ten": "Khám xong — mốc duy nhất phát sự kiện của bệnh án",
   "manh": "completed = đã hoàn tất",
   "dong_nghia": [
    "KhamXong",
    "Hoàn tất"
   ],
   "nguon": "src/clinicai/events/catalogue.py:1485"
  },
  {
   "ma": "consultation_note",
   "loai": "bảng",
   "ten": "Ghi chú phiên khám (ô chữ tự do của bác sĩ tư vấn, mỗi lần lưu một dòng)",
   "manh": "consultation = phiên khám · note = ghi chú",
   "dong_nghia": [
    "noi-dung-tu-van",
    "mang_sang"
   ],
   "nguon": "supabase/migrations/20260911000001_luot_kham_lat_1.sql:134"
  },
  {
   "ma": "DispatchService",
   "loai": "hàm",
   "ten": "Dịch vụ điều phối của trưởng ca (overview, alerts, move, history)",
   "manh": "dispatch = điều phối",
   "dong_nghia": [
    "dispatch_service.py",
    "move_visit_to_station"
   ],
   "nguon": "src/clinicai/services/dispatch_service.py:310"
  },
  {
   "ma": "docBang",
   "loai": "hàm",
   "ten": "Đọc một bảng làm việc qua /api/luot-kham?xem=…",
   "manh": "doc = đọc · bang = bảng",
   "dong_nghia": [
    "gopDoc (gộp lượt đọc trùng)"
   ],
   "nguon": "src/dashboard/app/(dashboard)/_lam-viec/api.ts:189"
  },
  {
   "ma": "doi_quyen",
   "loai": "hàm",
   "ten": "Đòi quyền theo lego (capability), không theo vai",
   "manh": "doi = đòi · quyen = quyền",
   "dong_nghia": [
    "clinical.consult.perform",
    "clinical.order.place",
    "clinical.intake.perform"
   ],
   "nguon": "src/clinicai/permissions/can.py:115"
  },
  {
   "ma": "domain_event",
   "loai": "bảng",
   "ten": "Sổ sự kiện nghiệp vụ (service_order.placed, consultation.completed…)",
   "manh": "domain = nghiệp vụ · event = sự kiện",
   "dong_nghia": [
    "emit_event",
    "consumer"
   ],
   "nguon": "supabase/migrations/20260923000001_domain_event.sql:33"
  },
  {
   "ma": "duyet_ket_qua",
   "loai": "hàm",
   "ten": "Bác sĩ đánh giá + phê duyệt cho gửi kết quả một chỉ định",
   "manh": "duyet = duyệt · ket qua = kết quả",
   "dong_nghia": [
    "thu-hoi-ket-qua (hoàn tác)"
   ],
   "nguon": "src/clinicai/services/luot_kham_service.py:3514"
  },
  {
   "ma": "emit_event",
   "loai": "hàm",
   "ten": "Ghi một sự kiện nghiệp vụ CÙNG giao dịch với việc ghi dữ liệu",
   "manh": "emit = phát · event = sự kiện",
   "dong_nghia": [
    "catalogue.py",
    "phát sự kiện"
   ],
   "nguon": "src/clinicai/events/emit.py:118"
  },
  {
   "ma": "execution_status",
   "loai": "cột",
   "ten": "Trạng thái thực hiện thật của chỉ định (IN_PROGRESS, COMPLETED, NOT_PERFORMED, INTERRUPTED…)",
   "manh": "execution = thực hiện · status = trạng thái",
   "dong_nghia": [
    "exec_status (cột cũ, trigger chiếu sang)"
   ],
   "nguon": "supabase/migrations/20260922000001_service_lifecycle_v1_schema.sql:31"
  },
  {
   "ma": "form_instance",
   "loai": "bảng",
   "ten": "Phiếu kết quả của một chỉ định (form engine)",
   "manh": "form = biểu mẫu · instance = bản điền",
   "dong_nghia": [
    "phiếu kết quả",
    "phieu_id"
   ],
   "nguon": "supabase/migrations/20260923000005_form_engine.sql:63"
  },
  {
   "ma": "FormEngineService.hoan_tat",
   "loai": "hàm",
   "ten": "Hoàn tất phiếu kết quả (CompleteForm)",
   "manh": "form engine = máy biểu mẫu · hoan tat = hoàn tất",
   "dong_nghia": [
    "hoan-tat",
    "luu_nhap",
    "mo_sua"
   ],
   "nguon": "src/clinicai/services/form_engine_service.py:671"
  },
  {
   "ma": "guiThaoTac",
   "loai": "hàm",
   "ten": "Gửi một lệnh (thao tác) xuống /api/luot-kham kèm Idempotency-Key",
   "manh": "gui = gửi · thao tac = thao tác",
   "dong_nghia": [
    "lệnh"
   ],
   "nguon": "src/dashboard/app/(dashboard)/_lam-viec/api.ts:218"
  },
  {
   "ma": "hang_cho",
   "loai": "hàm",
   "ten": "Hàng chờ một phòng / hàng tư vấn chung, theo ngày",
   "manh": "hang cho = hàng chờ",
   "dong_nghia": [
    "GET /luot-kham/hang-cho",
    "queue"
   ],
   "nguon": "src/clinicai/services/luot_kham_doc.py:693"
  },
  {
   "ma": "Idempotency-Key",
   "loai": "khái niệm",
   "ten": "Khoá chống bấm trùng — biên nhận nằm trong cùng giao dịch",
   "manh": "idempotency = gửi lại không đổi kết quả",
   "dong_nghia": [
    "bien_nhan_doc",
    "bien_nhan_ghi",
    "khoaGuiLai"
   ],
   "nguon": "src/clinicai/services/lenh_kham_core.py:164"
  },
  {
   "ma": "kham_xong",
   "loai": "hàm",
   "ten": "Nút Hoàn tất / Đã khám xong — máy chủ tự chọn kết quả phiên",
   "manh": "kham xong = khám xong",
   "dong_nghia": [
    "Hoàn tất",
    "complete_consultation"
   ],
   "nguon": "src/clinicai/services/luot_kham_service.py:1582"
  },
  {
   "ma": "kiem_dung_ca",
   "loai": "hàm",
   "ten": "Cổng ca trực: người bấm phải đúng ca / đi kèm bác sĩ của phiên",
   "manh": "kiem = kiểm · dung ca = đúng ca",
   "dong_nghia": [
    "SafetyGateError"
   ],
   "nguon": "src/clinicai/permissions/ca_truc.py:150"
  },
  {
   "ma": "lenhHoanTac",
   "loai": "hàm",
   "ten": "Tạo lệnh hoàn tác cho thông báo “… · Hoàn tác”",
   "manh": "lenh = lệnh · hoan tac = hoàn tác",
   "dong_nghia": [
    "mo-lai-kham",
    "huy-chi-dinh",
    "hoan-tac-xong-v1"
   ],
   "nguon": "src/dashboard/app/(dashboard)/_lam-viec/hoan-tac.ts:30"
  },
  {
   "ma": "luot_kham.py",
   "loai": "tệp",
   "ten": "Router FastAPI lượt khám (hàng chờ, phiên khám, chỉ định, thực hiện, xếp phòng)",
   "manh": "luot kham = lượt khám",
   "dong_nghia": [
    "/api/v1/luot-kham/*"
   ],
   "nguon": "src/clinicai/api/v1/routers/luot_kham.py:171"
  },
  {
   "ma": "LuotKhamService",
   "loai": "hàm",
   "ten": "Dịch vụ lượt khám (nhận khách, khám xong, tư vấn, duyệt kết quả)",
   "manh": "luot kham = lượt khám · service = tầng luật",
   "dong_nghia": [
    "luot_kham_service.py"
   ],
   "nguon": "src/clinicai/services/luot_kham_service.py:170"
  },
  {
   "ma": "luu_don_thuoc",
   "loai": "hàm",
   "ten": "Lưu đơn thuốc mục E của lượt",
   "manh": "luu = lưu · don thuoc = đơn thuốc",
   "dong_nghia": [
    "luu-don",
    "luu_don_chua_ky",
    "prescription.saved"
   ],
   "nguon": "src/clinicai/services/phieu_kham_service.py:822"
  },
  {
   "ma": "luu_luot",
   "loai": "hàm",
   "ten": "Tự lưu phiếu khám một lần (gộp ô vừa đổi)",
   "manh": "luu = lưu · luot = lượt",
   "dong_nghia": [
    "luu-phieu",
    "thay_doi"
   ],
   "nguon": "src/clinicai/services/phieu_kham_service.py:374"
  },
  {
   "ma": "MAN_TU_TAI",
   "loai": "khái niệm",
   "ten": "Danh sách màn tự tải (RealtimeRefresher không dựng lại trang server)",
   "manh": "man = màn · tu tai = tự tải",
   "dong_nghia": [
    "laManTuTai",
    "canDungLaiTrang"
   ],
   "nguon": "src/dashboard/lib/man-tu-tai.ts:23"
  },
  {
   "ma": "NhanTaiPhongService",
   "loai": "hàm",
   "ten": "Nhận khách tại phòng (dây nhan_tai_phong)",
   "manh": "nhan = nhận · tai phong = tại phòng",
   "dong_nghia": [
    "nhan-vao-phong",
    "hoan-tac-nhan",
    "Sắp đến"
   ],
   "nguon": "src/clinicai/services/nhan_tai_phong.py:888"
  },
  {
   "ma": "nhipKhiHien",
   "loai": "hàm",
   "ten": "Nhịp hỏi lại lưới an toàn (chỉ chạy khi tab đang hiện)",
   "manh": "nhip = nhịp · khi hien = khi đang hiện",
   "dong_nghia": [
    "polling 60 giây"
   ],
   "nguon": "src/dashboard/lib/nhip-khi-hien.ts:68"
  },
  {
   "ma": "notify_row_change",
   "loai": "hàm",
   "ten": "Trigger Postgres bắn pg_notify(clinicai_changes) {bảng, phòng khám} khi dòng đổi",
   "manh": "notify = báo · row change = dòng đổi",
   "dong_nghia": [
    "trg_notify_<bảng>",
    "LISTEN/NOTIFY"
   ],
   "nguon": "supabase/migrations/20260806000001_notify_change_for_live_screens.sql:18"
  },
  {
   "ma": "OPS-FINANCIAL-RESOLUTION",
   "loai": "khái niệm",
   "ten": "Loại việc “đối soát tiền”: đã thu mà dịch vụ không làm",
   "manh": "OPS = vận hành · financial = tài chính · resolution = giải quyết",
   "dong_nghia": [
    "OPS-SERVICE-INTERRUPTED",
    "OPS-ROUTING-REASSIGN"
   ],
   "nguon": "src/clinicai/events/consumers/trach_nhiem.py:52"
  },
  {
   "ma": "phieu_kham_luot",
   "loai": "bảng",
   "ten": "Phiếu khám v5 của lượt (một dòng mỗi lượt × phiếu, cột du_lieu jsonb + revision)",
   "manh": "phieu kham = phiếu khám · luot = lượt",
   "dong_nghia": [
    "phiếu v5"
   ],
   "nguon": "supabase/migrations/20260924000008_phieu_kham_luot.sql:20"
  },
  {
   "ma": "PHIEU_V5",
   "loai": "khái niệm",
   "ten": "Công tắc dùng phiếu khám v5 (tự lưu)",
   "manh": "phieu = phiếu · v5 = bản 5",
   "dong_nghia": [
    "ServiceFormEngine + ClinicalRecordForm (đường cũ, OFF)"
   ],
   "nguon": "src/dashboard/app/(dashboard)/ban-kham/BanKham.tsx:157"
  },
  {
   "ma": "PhieuKetQua.tsx",
   "loai": "tệp",
   "ten": "Khung phiếu kết quả (mở, lưu nháp, hoàn tất, mở sửa)",
   "manh": "phieu = phiếu · ket qua = kết quả",
   "dong_nghia": [
    "/api/phieu",
    "/api/doi-tac/phieu"
   ],
   "nguon": "src/dashboard/app/(dashboard)/_lam-viec/PhieuKetQua.tsx:153"
  },
  {
   "ma": "PhieuKhamLuot.tsx",
   "loai": "tệp",
   "ten": "Phiếu khám của một lượt (vỏ nối 7 phiếu v5 vào Bàn khám)",
   "manh": "phieu kham = phiếu khám · luot = lượt khám",
   "dong_nghia": [
    "phiếu v5",
    "clinical shell"
   ],
   "nguon": "src/dashboard/app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx:119"
  },
  {
   "ma": "PhieuKhamService",
   "loai": "hàm",
   "ten": "Dịch vụ phiếu khám v5 (đọc/tự lưu phiếu, đơn thuốc, lịch tái khám)",
   "manh": "phieu kham = phiếu khám",
   "dong_nghia": [
    "phieu_kham_service.py"
   ],
   "nguon": "src/clinicai/services/phieu_kham_service.py:207"
  },
  {
   "ma": "PhongDichVu.tsx",
   "loai": "tệp",
   "ten": "Màn một phòng dịch vụ",
   "manh": "phong = phòng · dich vu = dịch vụ",
   "dong_nghia": [
    "/phong/[ma]",
    "service-queue (cũ)",
    "sono (cũ)"
   ],
   "nguon": "src/dashboard/app/(dashboard)/phong/[ma]/PhongDichVu.tsx:141"
  },
  {
   "ma": "prescription",
   "loai": "bảng",
   "ten": "Dòng đơn thuốc của lượt",
   "manh": "prescription = đơn thuốc",
   "dong_nghia": [
    "đơn thuốc",
    "mục E"
   ],
   "nguon": "supabase/migrations/20260714000001_baseline_schema.sql:786"
  },
  {
   "ma": "queue_entry",
   "loai": "bảng",
   "ten": "Chỗ chờ: mỗi lần khách chờ một phiên khám / một dịch vụ ở một phòng",
   "manh": "queue = hàng · entry = mục",
   "dong_nghia": [
    "hàng chờ",
    "chỗ chờ"
   ],
   "nguon": "supabase/migrations/20260911000001_luot_kham_lat_1.sql:263"
  },
  {
   "ma": "result.ready",
   "loai": "sự kiện",
   "ten": "Đã có kết quả để đọc (chỉ dịch vụ có kết quả tại phòng)",
   "manh": "result = kết quả · ready = sẵn sàng",
   "dong_nghia": [
    "result.corrected (lần sửa)"
   ],
   "nguon": "src/clinicai/events/catalogue.py:2227"
  },
  {
   "ma": "service.completed",
   "loai": "sự kiện",
   "ten": "Đã làm xong dịch vụ (KHÁC có kết quả)",
   "manh": "service = dịch vụ · completed = xong",
   "dong_nghia": [
    "DichVuDaXong",
    "xong-v1"
   ],
   "nguon": "src/clinicai/events/catalogue.py:1600"
  },
  {
   "ma": "service.not_performed",
   "loai": "sự kiện",
   "ten": "Tới lượt mà không làm được dịch vụ",
   "manh": "not performed = không thực hiện",
   "dong_nghia": [
    "khong-lam-v1",
    "DichVuKhongLam",
    "da_thu_tien"
   ],
   "nguon": "src/clinicai/events/catalogue.py:1618"
  },
  {
   "ma": "service_execution_attempt",
   "loai": "bảng",
   "ten": "Một lần làm dịch vụ ở phòng (giờ vào, giờ xong, người làm, ghi chú)",
   "manh": "service = dịch vụ · execution = thực hiện · attempt = lần",
   "dong_nghia": [
    "lần làm",
    "attempt_id"
   ],
   "nguon": "supabase/migrations/20260922000001_service_lifecycle_v1_schema.sql:106"
  },
  {
   "ma": "service_order",
   "loai": "bảng",
   "ten": "Chỉ định dịch vụ",
   "manh": "service = dịch vụ · order = chỉ định",
   "dong_nghia": [
    "chỉ định",
    "order"
   ],
   "nguon": "supabase/migrations/20260911000001_luot_kham_lat_1.sql:153"
  },
  {
   "ma": "service_order.placed",
   "loai": "sự kiện",
   "ten": "Đã đặt chỉ định (mỗi dịch vụ một tin)",
   "manh": "placed = đã đặt",
   "dong_nghia": [
    "ChiDinhDaDat"
   ],
   "nguon": "src/clinicai/events/catalogue.py:1418"
  },
  {
   "ma": "service_order_draft",
   "loai": "bảng",
   "ten": "Chỉ định nháp thư ký nhập chờ bác sĩ duyệt (ĐÃ NGHỈ)",
   "manh": "service order = chỉ định · draft = nháp",
   "dong_nghia": [
    "draft-orders",
    "authorize-orders"
   ],
   "nguon": "supabase/migrations/20260915000008_service_order_draft.sql:16"
  },
  {
   "ma": "ServiceExecutionService",
   "loai": "hàm",
   "ten": "Dịch vụ thực hiện ở phòng (bat_dau, xong, khong_lam, gian_doan, huy_bat_dau)",
   "manh": "service execution = thực hiện dịch vụ",
   "dong_nghia": [
    "bat-dau-v1",
    "xong-v1",
    "Lifecycle v1"
   ],
   "nguon": "src/clinicai/services/service_execution_service.py:364"
  },
  {
   "ma": "ServiceRoutingService.assign",
   "loai": "hàm",
   "ten": "Xếp / đổi phòng chính thức cho một chỉ định",
   "manh": "routing = điều tuyến · assign = gán",
   "dong_nghia": [
    "AssignServiceRoom",
    "xep-phong-v1",
    "service.routed"
   ],
   "nguon": "src/clinicai/services/service_routing_service.py:1204"
  },
  {
   "ma": "src/dashboard/app/api/luot-kham/route.ts",
   "loai": "tệp",
   "ten": "Proxy Next màn lượt khám — danh sách trắng thao tác → đường FastAPI",
   "manh": "luot kham = lượt khám · route = cửa API Next",
   "dong_nghia": [
    "THAO_TAC",
    "duongDoc"
   ],
   "nguon": "src/dashboard/app/api/luot-kham/route.ts:19"
  },
  {
   "ma": "start_consultation",
   "loai": "hàm",
   "ten": "Nhận khách vào phiên khám (nút Bắt đầu khám / Bắt đầu tư vấn)",
   "manh": "start = bắt đầu · consultation = phiên khám",
   "dong_nghia": [
    "nhan-kham",
    "consultation.started"
   ],
   "nguon": "src/clinicai/services/luot_kham_service.py:1709"
  },
  {
   "ma": "tep_ket_qua",
   "loai": "bảng",
   "ten": "Tệp kết quả (ảnh/video/PDF) gắn lượt hoặc chỉ định",
   "manh": "tep = tệp · ket qua = kết quả",
   "dong_nghia": [
    "KhungTep",
    "/api/cskh/ket-qua"
   ],
   "nguon": "supabase/migrations/20260809000008_tep_ket_qua.sql:21"
  },
  {
   "ma": "TepKetQuaService",
   "loai": "hàm",
   "ten": "Dịch vụ tệp kết quả (tải lên, xác nhận, mở để đọc)",
   "manh": "tep ket qua = tệp kết quả",
   "dong_nghia": [
    "xac_nhan_tep",
    "cho_xac_nhan"
   ],
   "nguon": "src/clinicai/services/tep_ket_qua_service.py:680"
  },
  {
   "ma": "trach_nhiem.py",
   "loai": "tệp",
   "ten": "Consumer mở việc cho trách nhiệm không được rơi",
   "manh": "trach nhiem = trách nhiệm",
   "dong_nghia": [
    "TRACH_NHIEM_DICH_VU",
    "mo_viec_khi_can"
   ],
   "nguon": "src/clinicai/events/consumers/trach_nhiem.py:80"
  },
  {
   "ma": "useDispatchLive",
   "loai": "hàm",
   "ten": "Hook giữ bảng điều phối luôn mới (nghe LIVE_TABLES)",
   "manh": "dispatch = điều phối · live = sống",
   "dong_nghia": [
    "LIVE_TABLES",
    "pull"
   ],
   "nguon": "src/dashboard/app/(dashboard)/truong-ca/shared.tsx:68"
  },
  {
   "ma": "useNgheBang",
   "loai": "hàm",
   "ten": "Hook nghe tin bảng đổi để màn tự fetch nạp lại",
   "manh": "use = hook React · nghe = lắng nghe · bang = bảng",
   "dong_nghia": [
    "SU_KIEN_BANG",
    "dòng SSE chung"
   ],
   "nguon": "src/dashboard/app/(dashboard)/dung-nghe-bang.ts:45"
  },
  {
   "ma": "work_item",
   "loai": "bảng",
   "ten": "Đầu việc của nhân lõi luồng — nay chủ yếu việc vận hành (OPS-*) và check-out",
   "manh": "work = việc · item = mục",
   "dong_nghia": [
    "việc cần xử lý",
    "node_code"
   ],
   "nguon": "supabase/migrations/20260730000005_workflow_kernel.sql:125"
  },
  {
   "ma": "work_item_event",
   "loai": "bảng",
   "ten": "Lịch sử từng lệnh trên một đầu việc",
   "manh": "work item = đầu việc · event = sự kiện",
   "dong_nghia": [],
   "nguon": "supabase/migrations/20260730000005_workflow_kernel.sql:219"
  },
  {
   "ma": "WorkItemService.issue",
   "loai": "hàm",
   "ten": "Ra lệnh trên đầu việc (start, complete, skip, cancel) có kiểm version",
   "manh": "work item = đầu việc · issue = ra lệnh",
   "dong_nghia": [
    "/work-items/{id}/commands/*"
   ],
   "nguon": "src/clinicai/services/work_item_service.py:121"
  },
  {
   "ma": "xong_tu_van",
   "loai": "hàm",
   "ten": "Bác sĩ tư vấn bấm Xong — chuyển khách sang bác sĩ chính",
   "manh": "xong = xong · tu van = tư vấn",
   "dong_nghia": [
    "CompleteIntake",
    "consultation.handed_over"
   ],
   "nguon": "src/clinicai/services/luot_kham_service.py:2027"
  }
 ],
 "manh": {
  "access": "quyền vào",
  "account": "tài khoản",
  "action": "thao tác",
  "activate": "bật",
  "active": "đang hiệu lực",
  "add": "thêm",
  "admin": "quản trị",
  "agent": "trợ lý AI",
  "alerts": "cảnh báo",
  "allocation": "phân bổ (chọn lô)",
  "amendment": "đính chính",
  "andrology": "nam khoa",
  "app": "ứng dụng",
  "applied": "đã áp",
  "apply": "áp dụng",
  "appointment": "lịch hẹn",
  "appointments": "lịch hẹn",
  "approval": "duyệt",
  "assign": "giao",
  "assignable": "giao được",
  "attempt": "lần thử",
  "audit": "kiểm vết",
  "authorize": "cho phép",
  "bac": "bác",
  "bac_si": "bác sĩ",
  "ban": "bàn",
  "ban_kham": "bàn khám",
  "bang": "bảng",
  "bang_gia": "bảng giá",
  "bao_cao": "báo cáo",
  "bat": "bật",
  "bat_dau": "bắt đầu",
  "batch": "lô",
  "benh_an": "bệnh án",
  "bill": "hoá đơn",
  "bio": "sinh trắc",
  "board": "bảng",
  "booking": "đặt lịch",
  "budget": "ngân sách",
  "buoi": "buổi",
  "ca": "ca",
  "ca_truc": "ca trực",
  "cai_dat": "cài đặt",
  "can": "cần",
  "candidates": "ứng viên",
  "canh_bao": "cảnh báo",
  "cap_phat": "cấp phát",
  "capability": "năng lực/quyền",
  "capacity": "sức chứa",
  "care": "chăm sóc",
  "care_episode": "đợt chăm sóc",
  "case": "ca",
  "cashier": "thu ngân",
  "catalog": "danh mục",
  "catalogue": "danh mục",
  "cau_hinh": "cấu hình",
  "cham_soc": "chăm sóc",
  "change": "đổi",
  "channel": "kênh",
  "channels": "kênh",
  "che": "che",
  "che_do": "chế độ",
  "check": "kiểm",
  "checkin": "check-in",
  "checkout": "check-out (cho về)",
  "chi_dinh": "chỉ định",
  "chia": "chia",
  "chip": "chip",
  "cho": "chờ/chỗ/cho",
  "chon": "chọn",
  "chot": "chốt",
  "chot_so": "chốt sổ",
  "chua": "chưa",
  "chuyen": "chuyển",
  "clinic": "phòng khám",
  "clinic_config": "cấu trúc phòng khám",
  "clinical": "lâm sàng",
  "clinical_record": "bệnh án",
  "close": "đóng",
  "co": "có",
  "co_so": "cơ sở",
  "command": "lệnh",
  "con": "còn",
  "con_no": "còn nợ",
  "config": "cấu hình",
  "confirm": "xác nhận",
  "cong": "cổng/cộng/công",
  "cong_no": "công nợ",
  "cong_ty": "công ty",
  "consent": "đồng ý",
  "console": "bảng điều khiển",
  "consultation": "buổi tư vấn",
  "contact": "liên hệ",
  "correction": "điều chỉnh",
  "create": "tạo",
  "credential": "thông tin đăng nhập",
  "cskh": "chăm sóc khách hàng",
  "cu": "cũ",
  "cua": "của",
  "cuoi_ngay": "cuối ngày",
  "customer": "khách hàng",
  "customers": "khách hàng",
  "cycle": "chu kỳ/lần",
  "da": "đã",
  "dang": "đang",
  "dang_nhap": "đăng nhập",
  "danh_muc": "danh mục",
  "danh_sach": "danh sách",
  "dat": "đặt",
  "dat_lich": "đặt lịch",
  "data": "dữ liệu",
  "dau": "đầu/dấu",
  "dau_vao": "đầu vào",
  "day": "dây",
  "day_noi": "dây nối",
  "days": "ngày",
  "deactivate": "tắt",
  "deadline": "hạn",
  "decide": "quyết",
  "definition": "định nghĩa",
  "delete": "xoá",
  "delivery": "giao",
  "dem": "đếm",
  "dependency": "phụ thuộc",
  "dich_vu": "dịch vụ",
  "dien_thoai": "điện thoại",
  "dieu_phoi": "điều phối",
  "dinh_nghia": "định nghĩa",
  "dispatch": "điều phối",
  "dispense": "giao thuốc",
  "display": "màn TV",
  "do_sinh_hieu": "đo sinh hiệu",
  "doan": "đoạn",
  "doc": "đọc",
  "doctor": "bác sĩ",
  "doi": "đổi/đối",
  "doi_chieu": "đối chiếu",
  "doi_lich": "đổi lịch",
  "doi_tac": "đối tác",
  "domain": "miền",
  "don": "đơn",
  "don_du_lieu_thu": "dọn dữ liệu thử",
  "don_thuoc": "đơn thuốc",
  "don_vi": "đơn vị",
  "dong": "đóng/dòng",
  "dong_bo": "đồng bộ",
  "dong_thoi_gian": "dòng thời gian",
  "draft": "bản nháp",
  "drug": "thuốc",
  "du_lieu": "dữ liệu",
  "dung": "dùng/dừng",
  "duong": "đường",
  "duplicate": "trùng",
  "duyet": "duyệt",
  "encounter": "lần gặp",
  "encounter_flow": "luồng khám của lượt",
  "engine": "bộ máy",
  "entry": "dòng/lượt vào",
  "episode": "đợt",
  "event": "sự kiện",
  "event_log": "nhật ký sự kiện",
  "events": "sự kiện",
  "execution": "thực hiện",
  "exempt": "miễn",
  "feature": "tính năng",
  "feedback": "phản hồi",
  "find": "tìm",
  "floor": "tầng",
  "flow": "luồng",
  "follow": "theo",
  "follow_up": "theo dõi",
  "follow_up_case": "ca theo dõi",
  "form": "biểu mẫu",
  "form_instance": "phiếu kết quả đã điền",
  "gan": "gắn",
  "gate": "cổng chặn",
  "get": "lấy",
  "ghi": "ghi",
  "gia": "giá",
  "giam_gia": "giảm giá",
  "giam_sat": "giám sát",
  "giao": "giao",
  "gio": "giờ",
  "giu": "giữ",
  "giu_cho": "giữ chỗ",
  "giu_lai": "giữ lại",
  "go": "gỡ",
  "goi": "gọi/gói",
  "goi_y": "gợi ý",
  "grant": "cấp",
  "hang": "hàng",
  "hang_cho": "hàng chờ",
  "hang_doi": "hàng đợi",
  "hang_so": "hằng số",
  "hanh_trinh": "hành trình",
  "hen": "hẹn",
  "hen_goi_lai": "hẹn gọi lại",
  "het": "hết",
  "history": "lịch sử",
  "ho_so": "hồ sơ",
  "hoa": "hoá",
  "hoa_don": "hoá đơn",
  "hoan": "hoàn",
  "hoan_tac": "hoàn tác",
  "hoan_tien": "hoàn tiền",
  "hold": "giữ chỗ",
  "hom_nay": "hôm nay",
  "home": "trang chủ",
  "hub": "trung tâm",
  "huong": "hướng",
  "huy": "huỷ",
  "idempotency": "chống ghi hai lần",
  "in": "in",
  "in_theo": "in theo",
  "instance": "bản điền",
  "invalidate": "làm mất hiệu lực",
  "inventory": "tồn kho",
  "invoice": "hoá đơn",
  "issue": "vấn đề",
  "item": "mục",
  "items": "các mục",
  "job": "việc",
  "ke_toan": "kế toán",
  "kenh": "kênh",
  "ket_qua": "kết quả",
  "ket_thuc": "kết thúc",
  "key": "khoá",
  "khach": "khách",
  "khach_cong_ty": "khách công ty",
  "khach_hang": "khách hàng",
  "kham": "khám",
  "kho": "kho",
  "khoa": "khoá/khoa",
  "khoan": "khoản",
  "khong": "không",
  "khung": "khung",
  "khung_ca": "khung ca",
  "kiem": "kiểm",
  "kiem_ke": "kiểm kê",
  "kiem_ke_ca": "kiểm kê ca",
  "kin": "người thân",
  "kpi": "chỉ số",
  "ky_nang": "kỹ năng",
  "la": "là",
  "lab": "xét nghiệm",
  "lai": "lại",
  "lam_sang": "lâm sàng",
  "lam_viec": "làm việc",
  "lan": "lần",
  "lan_thu": "lần thu",
  "landing": "trang đích",
  "lay_mau": "lấy mẫu",
  "le": "lẻ/lễ",
  "le_tan": "lễ tân",
  "lego": "lego (khối quyền)",
  "lich": "lịch",
  "lich_hen": "lịch hẹn",
  "lich_su": "lịch sử",
  "lich_truc": "lịch trực",
  "lieu_trinh": "liệu trình",
  "line": "dòng",
  "link": "liên kết",
  "list": "danh sách",
  "live": "sống",
  "llm": "mô hình AI",
  "lo": "lô",
  "location": "cơ sở",
  "log": "nhật ký",
  "loi": "lỗi",
  "loi_nhom": "nhóm lỗi",
  "luat": "luật",
  "luot": "lượt",
  "luot_kham": "lượt khám",
  "luot_phi_kham": "phí khám của lượt",
  "luot_vat_tu": "vật tư của lượt",
  "luu": "lưu",
  "ly_do": "lý do",
  "ma": "mã",
  "man": "màn",
  "man_hinh": "màn hình",
  "man_tu_tai": "màn tự tải",
  "mang_sang": "mang sang",
  "mat_khau": "mật khẩu",
  "mau": "mẫu/màu",
  "mau_ket_qua": "mẫu kết quả",
  "measurement": "lần đo",
  "medical": "y khoa",
  "membership": "thành viên",
  "merge": "gộp",
  "migrations": "migration",
  "misa": "MISA (phần mềm kế toán)",
  "mo": "mở",
  "mode": "chế độ",
  "moi": "mới/mọi",
  "mot": "một",
  "mot_luot": "một lượt",
  "move": "chuyển",
  "mpi": "chỉ mục bệnh nhân (chống trùng)",
  "mpiservice": "dịch vụ chống trùng khách",
  "multipart": "nhiều phần (tải tệp)",
  "nang": "nặng/nâng",
  "nav": "thanh bên",
  "navigation": "điều hướng",
  "next": "kế",
  "ngay": "ngày",
  "nghe": "nghe",
  "nghe_bang": "nghe bảng",
  "nghiep_vu": "nghiệp vụ",
  "ngoai": "ngoài",
  "ngoai_le": "ngoại lệ",
  "nguoi": "người",
  "nguoi_gioi_thieu": "người giới thiệu",
  "nguon": "nguồn",
  "nhac": "nhắc",
  "nhan": "nhận/nhãn",
  "nhan_dinh": "nhận định",
  "nhan_su": "nhân sự",
  "nhap": "nhập",
  "nhat_ky": "nhật ký",
  "nhom": "nhóm",
  "no": "nợ",
  "node": "nút",
  "nodes": "nút",
  "noi": "nối",
  "noi_chua": "nơi chứa",
  "note": "ghi chú",
  "notify": "báo tin",
  "nut": "nút",
  "o": "ô",
  "of": "của",
  "ops": "vận hành",
  "order": "chỉ định",
  "orders": "chỉ định",
  "outbox": "hộp thư đi",
  "override": "ngoại lệ",
  "overview": "tổng quan",
  "owner": "chủ phòng khám",
  "owner_feedback": "góp ý của chủ phòng khám",
  "partner": "đối tác",
  "patient": "bệnh nhân/khách",
  "patients": "bệnh nhân",
  "payment": "thanh toán",
  "payment_cycle": "một lần thu",
  "pending": "đang chờ",
  "permission": "quyền",
  "permissions": "quyền",
  "phan_hoi": "phản hồi",
  "phan_quyen": "phân quyền",
  "pharmacy": "nhà thuốc",
  "phi": "phí",
  "phi_kham": "phí khám",
  "phien": "phiên",
  "phien_ban": "phiên bản",
  "phieu": "phiếu",
  "phieu_kham": "phiếu khám",
  "phieu_kho": "phiếu kho",
  "phieu_kho_dong": "dòng phiếu kho",
  "phieu_thu": "phiếu thu",
  "phong": "phòng",
  "pin": "ghim",
  "policy": "luật",
  "pos": "máy POS",
  "pregnancy": "thai kỳ",
  "prescription": "đơn thuốc",
  "preset": "nhóm mẫu",
  "price": "giá",
  "profile": "hồ sơ",
  "province": "tỉnh",
  "quan_ly": "quản lý",
  "quay": "quầy",
  "quay_thu": "quầy thu",
  "queue": "hàng đợi",
  "queue_entry": "chỗ trong hàng đợi",
  "quote": "báo giá",
  "quyen": "quyền",
  "quyet": "quyết",
  "range": "khoảng",
  "readiness": "sẵn sàng",
  "realtime": "thời gian thực",
  "recall": "nhắc tái khám",
  "receipt": "phiếu thu",
  "record": "hồ sơ/ghi",
  "refresher": "bộ dựng lại",
  "refund": "hoàn tiền",
  "release": "nhả",
  "remove": "bỏ",
  "rename": "đổi tên",
  "reorder": "đổi thứ tự",
  "report": "báo cáo",
  "reports": "báo cáo",
  "requirement": "yêu cầu",
  "response": "phản hồi",
  "result": "kết quả",
  "return": "trả lại",
  "review": "duyệt",
  "revision": "bản sửa",
  "room": "phòng",
  "rooms": "các phòng",
  "roster": "lịch trực",
  "round": "vòng",
  "route": "đường",
  "routes": "các đường",
  "routing": "chuyển hướng",
  "row": "dòng",
  "rule": "luật",
  "save": "lưu",
  "schedule": "lịch làm việc",
  "schema": "lược đồ",
  "scope": "phạm vi",
  "sdt": "số điện thoại",
  "secret": "bí mật",
  "selection": "lựa chọn",
  "semen": "tinh dịch đồ",
  "service": "dịch vụ (tầng luật)",
  "service_order": "chỉ định dịch vụ",
  "service_price": "giá dịch vụ",
  "services": "các dịch vụ",
  "session": "phiên",
  "set": "đặt",
  "settings": "cài đặt",
  "shift": "ca",
  "si": "sĩ",
  "sieu_am": "siêu âm",
  "sinh_hieu": "sinh hiệu",
  "slot": "khung giờ",
  "slot_hold": "giữ chỗ khung giờ",
  "so": "sổ/số",
  "so_no": "sổ nợ",
  "staff": "nhân viên",
  "staff_task": "việc của nhân viên",
  "stale": "cũ",
  "start": "bắt đầu",
  "state": "trạng thái",
  "stations": "trạm",
  "status": "trạng thái",
  "su": "sự/sử",
  "su_kien": "sự kiện",
  "sua": "sửa",
  "suc": "sức",
  "suc_chua": "sức chứa",
  "summary": "tóm tắt",
  "tables": "bảng",
  "tai": "tải/tại",
  "tai_kham": "tái khám",
  "tai_khoan": "tài khoản",
  "tai_lai": "tải lại",
  "tang": "tầng",
  "tao": "tạo",
  "task": "việc",
  "tasks": "việc",
  "tat": "tắt",
  "telemetry": "đo đạc",
  "tem": "tem",
  "template": "mẫu",
  "ten": "tên",
  "tep": "tệp",
  "tep_ket_qua": "tệp kết quả",
  "thai_ky": "thai kỳ",
  "tham_chieu": "tham chiếu",
  "the": "thẻ",
  "them": "thêm",
  "theo": "theo",
  "thong_bao": "thông báo",
  "threshold": "ngưỡng",
  "thu": "thu",
  "thu_ngan": "thu ngân",
  "thu_nghiem": "thử nghiệm",
  "thu_thuat": "thủ thuật",
  "thu_tu": "thứ tự",
  "thue": "thuế",
  "thue_suat": "thuế suất",
  "thuoc": "thuốc",
  "tien": "tiền",
  "tien_thua": "tiền thừa",
  "tiep": "tiếp",
  "tiep_don": "tiếp đón",
  "tieu_hao": "tiêu hao",
  "tim": "tìm",
  "tim_khach": "tìm khách",
  "tinh": "tính",
  "toi": "tôi/tới",
  "tom_tat": "tóm tắt",
  "ton": "tồn",
  "tong": "tổng",
  "tong_quan": "tổng quan",
  "tra": "trả",
  "tra_truoc": "trả trước",
  "traffic": "lưu lượng",
  "tram": "trạm",
  "trang": "trang",
  "trang_chu": "trang chủ",
  "trang_thai": "trạng thái",
  "trg": "trigger",
  "truc": "trực",
  "truoc": "trước",
  "truong_ca": "trưởng ca",
  "tu": "tự/từ/tủ",
  "tu_van": "tư vấn",
  "tuan": "tuần",
  "tuong_tac": "tương tác",
  "txn": "giao dịch kho",
  "type": "loại",
  "ultrasound": "siêu âm",
  "ung": "ứng",
  "up": "dõi",
  "update": "cập nhật",
  "use": "dùng",
  "user": "người dùng",
  "users": "người dùng",
  "v": "view (bảng ảo)",
  "vai": "vai",
  "values": "giá trị",
  "van_hanh": "vận hành",
  "vat": "VAT/vật",
  "vat_tu": "vật tư",
  "version": "phiên bản",
  "vi_tri": "vị trí",
  "viec": "việc",
  "viec_can_xu_ly": "việc cần xử lý",
  "visit": "lượt khám",
  "vital": "sinh hiệu",
  "vitals": "sinh hiệu",
  "vuot": "vượt",
  "ward": "phường/xã",
  "wards": "phường/xã",
  "week": "tuần",
  "weeks": "tuần",
  "work": "làm việc",
  "work_item": "việc",
  "work_roster": "lịch trực",
  "worklist": "danh sách việc",
  "xac_nhan": "xác nhận",
  "xem": "xem",
  "xet_nghiem": "xét nghiệm",
  "xlsx": "tệp Excel",
  "xoa": "xoá",
  "xong": "xong",
  "xu_ly": "xử lý",
  "xuat": "xuất",
  "y_khoa": "y khoa",
  "yeu_cau": "yêu cầu"
 }
};
