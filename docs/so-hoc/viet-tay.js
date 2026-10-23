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
   ],
   "mo_ta": "Điểm khởi đầu hành trình: tạo hồ sơ khách (chống trùng), chọn khung giờ (giữ chỗ mềm) rồi ghi lịch hẹn. Khách “Trực tiếp” cho hôm nay được check-in luôn trong cùng lần đặt.",
   "dieu_phai_nho": [
    {
     "chu": "Giữ chỗ chỉ là lời báo, không phải khoá.",
     "vi_sao": "Dòng giữ chỗ rò (đóng tab giữa chừng) chỉ làm phiền người khác tối đa 10 phút và không bao giờ được làm một lịch hợp lệ bị từ chối; chốt thật là trigger sức chứa lúc INSERT.",
     "nguon": "docs/SO-LUAT.md:186"
    },
    {
     "chu": "Sức chứa là ghế của MỘT bác sĩ, kiểm lúc XẾP bác sĩ.",
     "vi_sao": "Lịch để trống bác sĩ luôn được nhận và rơi vào màn Chờ xếp bác sĩ; đặt không chọn bác sĩ rồi kết luận “vượt sức chứa” là đo sai.",
     "nguon": "docs/SO-LUAT.md:217"
    },
    {
     "chu": "Không gửi kênh = ghế đặt trước (NULL), không phải WALK_IN; WALK_IN + hôm nay = tự check-in.",
     "vi_sao": "Bản cũ mặc định WALK_IN nên mọi lịch CSKH đặt ăn vào ghế dành cho khách vãng lai; nay chỉ chọn rõ “Trực tiếp” cho hôm nay mới mở lượt và cần quyền check-in.",
     "nguon": "src/clinicai/services/booking_service.py:571"
    },
    {
     "chu": "Một khoá Idempotency-Key cho MỘT lần đặt: bỏ khoá khi máy chủ đã trả lời, giữ khoá khi mất mạng.",
     "vi_sao": "Dùng lại khoá sau 409 thì kẹt “đang xử lý” 5 phút; sinh khoá mới khi mất mạng thì bấm lại ra lịch thứ hai.",
     "nguon": "src/dashboard/app/(dashboard)/appointments/BookingHub.tsx:958"
    },
    {
     "chu": "Cảnh báo trùng hồ sơ dùng ĐÚNG hàm của đường lưu (MPIService.find_candidates); trùng SĐT chỉ cảnh báo, không chặn.",
     "vi_sao": "Hai luật khác nhau từng khiến màn báo “không trùng” rồi hồ sơ vẫn rơi vào hàng chờ gộp; mẹ đăng ký bằng số của mình cho con là hợp lệ nên chỉ gửi lại kèm force.",
     "nguon": "src/clinicai/api/v1/patients.py:105"
    }
   ],
   "man": [
    {
     "route": "/appointments",
     "ten": "Đặt lịch (hub đặt lịch CSKH)",
     "ai_dung": "CSKH, lễ tân (lego dat_lich)",
     "lam_duoc": [
      "Tìm khách trên toàn bộ hồ sơ (từ 2 ký tự) hoặc tạo khách mới ngay trong màn",
      "Xem lưới chỗ trống theo bác sĩ/tuần, thấy ô người khác đang giữ",
      "Chọn khung giờ (tự giữ chỗ 10 phút) và bấm [Đặt lịch hẹn], kể cả kênh “Trực tiếp” tự check-in",
      "Xem lịch sắp tới của khách và đổi lịch tại chỗ"
     ],
     "bang_doc": [
      "patient",
      "appointment",
      "service_type",
      "work_roster",
      "slot_hold",
      "clinic_location"
     ],
     "bang_ghi": [
      "appointment",
      "slot_hold",
      "visit",
      "idempotency_key",
      "event_log",
      "patient"
     ],
     "toc_do_ghi_chu": "Mở màn: 2 lời gọi song song (hub-dat-lich + danh sách bác sĩ) ở src/dashboard/app/(dashboard)/appointments/page.tsx:32. Giữ chỗ: nhịp hỏi 5 giây + nghe tin bảng slot_hold (src/dashboard/app/(dashboard)/appointments/dung-giu-cho.ts:90, src/dashboard/app/(dashboard)/appointments/dung-giu-cho.ts:120). Đặt xong: router.refresh + tăng bookingSeq để hỏi lại sức chứa (src/dashboard/app/(dashboard)/appointments/BookingHub.tsx:933). Trang KHÔNG thuộc man-tu-tai nên mọi tin appointment đều dựng lại trang.",
     "ghi_chu": "Lệch comment: src/dashboard/app/(dashboard)/appointments/BookingHub.tsx:836 nói “lớp ba là chốt ở database — chưa có”, nhưng chỉ mục uq_appointment_patient_slot_live đã có ở supabase/migrations/20260805000007_appointment_patient_slot_unique.sql:67."
    },
    {
     "route": "/appointments/cho-xep-bac-si",
     "ten": "Lịch chờ xếp bác sĩ",
     "ai_dung": "Quản lý, trưởng ca, CSKH (quyền booking.manage)",
     "lam_duoc": [
      "Xem lịch đặt trước còn trống bác sĩ (doctor_id IS NULL) hoặc vượt sức chứa",
      "Gán bác sĩ (assign_doctor) hoặc đổi giờ + bác sĩ trong một lệnh (reschedule)",
      "Khi đổi giờ: tự ghi một dòng sổ chăm sóc để CSKH gọi báo khách"
     ],
     "bang_doc": [
      "appointment",
      "patient",
      "work_roster",
      "staff"
     ],
     "bang_ghi": [
      "appointment",
      "work_roster",
      "tuong_tac_cskh",
      "appointment_doi_lich",
      "event_log"
     ],
     "toc_do_ghi_chu": "Mở màn 1 lời gọi /api/v1/appointments/cho-xep-bac-si (src/dashboard/app/(dashboard)/appointments/cho-xep-bac-si/page.tsx:34). Xếp xong gửi tuần tự PATCH lịch rồi POST sổ chăm sóc (src/dashboard/app/(dashboard)/appointments/cho-xep-bac-si/HangChoView.tsx:90, src/dashboard/app/(dashboard)/appointments/cho-xep-bac-si/HangChoView.tsx:117), sau đó router.refresh (src/dashboard/app/(dashboard)/appointments/cho-xep-bac-si/HangChoView.tsx:135).",
     "ghi_chu": "Hai lệnh đổi giờ và ghi sổ là hai request rời, không chung giao dịch; lệnh ghi sổ không gửi Idempotency-Key (src/dashboard/app/(dashboard)/appointments/cho-xep-bac-si/HangChoView.tsx:117). Gán bác sĩ cho lịch trống tự xếp bác sĩ vào lịch trực cùng giao dịch (src/clinicai/services/booking_service.py:1532)."
    },
    {
     "route": "/lich-do-ve",
     "ten": "Lịch đổ về (thống kê lịch theo khung giờ)",
     "ai_dung": "Quản lý (lego bao_cao)",
     "lam_duoc": [
      "Xem toàn bộ lịch một tuần",
      "Đếm số lịch theo từng khung giờ",
      "Tách khám mới / khám cũ / dịch vụ"
     ],
     "bang_doc": [
      "appointment",
      "patient",
      "staff",
      "service_type"
     ],
     "bang_ghi": [],
     "toc_do_ghi_chu": "1 lời gọi /api/v1/appointments/week (src/dashboard/app/(dashboard)/lich-do-ve/page.tsx:56); phép đếm theo khung chạy ở lib/thong-ke-khung-gio (src/dashboard/app/(dashboard)/lich-do-ve/page.tsx:61).",
     "ghi_chu": "Chỉ đọc. Dùng lại đúng nguồn của bảng lịch tuần Trang chủ (src/clinicai/api/v1/routers/booking.py:565), không viết truy vấn riêng."
    },
    {
     "route": "/patients/new",
     "ten": "Tạo hồ sơ khách (và đặt lịch luôn nếu muốn)",
     "ai_dung": "Lễ tân, CSKH (lego them_benh_nhan)",
     "lam_duoc": [
      "Nhập hồ sơ; chỉ Họ tên là bắt buộc",
      "Cảnh báo sớm hồ sơ có thể trùng (SĐT, CCCD, họ tên + năm sinh) khi đang gõ",
      "Lưu hồ sơ, xử lý trùng (Dùng hồ sơ này / vẫn tạo / ghi lý do trùng CCCD)",
      "Đặt lịch ngay sau khi lưu, hoặc chỉ lưu rồi sang /customers?selected="
     ],
     "bang_doc": [
      "patient",
      "patient_sdt_them",
      "service_type",
      "work_roster",
      "appointment"
     ],
     "bang_ghi": [
      "patient",
      "event_log",
      "mpi_merge_queue",
      "appointment"
     ],
     "toc_do_ghi_chu": "Kiểm trùng gửi sau khi ngừng gõ 450ms (src/dashboard/app/(dashboard)/patients/new/NewPatientForm.tsx:742, gọi ở src/dashboard/app/(dashboard)/patients/new/NewPatientForm.tsx:727). Lưu: 1 POST /api/patients (src/dashboard/app/(dashboard)/patients/new/NewPatientForm.tsx:1036) rồi nếu đặt lịch thì thêm 1 POST /api/appointments (src/dashboard/app/(dashboard)/patients/new/NewPatientForm.tsx:782).",
     "ghi_chu": "Đặt lịch từ form này KHÔNG gửi Idempotency-Key (src/dashboard/app/(dashboard)/patients/new/NewPatientForm.tsx:782), khác BookingHub. Ghế “trực tiếp” gửi WALK_IN (src/dashboard/app/(dashboard)/patients/new/NewPatientForm.tsx:794)."
    },
    {
     "route": "/print/[appointmentId]",
     "ten": "In phiếu tóm tắt khám của một lịch hẹn",
     "ai_dung": "Người có khối khám / kết quả (requireClinicalRole), thường lễ tân mở từ Trang chủ",
     "lam_duoc": [
      "Đọc hồ sơ khám của lịch hẹn và dựng phiếu A4",
      "In / xuất PDF"
     ],
     "bang_doc": [
      "appointment",
      "visit",
      "patient",
      "clinical_record",
      "lab_result",
      "patient_medical_profile"
     ],
     "bang_ghi": [],
     "toc_do_ghi_chu": "Hai lời gọi TUẦN TỰ ở server: hồ sơ theo lịch rồi phiếu của lượt (src/dashboard/app/print/[appointmentId]/page.tsx:116, src/dashboard/app/print/[appointmentId]/page.tsx:134) — lời sau cần visit_id của lời trước.",
     "ghi_chu": "Đặt ngoài nhóm (dashboard) nên không có thanh bên, in sạch A4."
    }
   ],
   "thao_tac": [
    {
     "man": "/appointments",
     "nut": "Bấm [Đặt lịch hẹn] (kể cả kênh “Trực tiếp” cho hôm nay)",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "BookingHub.handleConfirmBooking gửi POST /api/appointments kèm Idempotency-Key (khoá giữ qua mọi lần thử lại)",
       "nguon": "src/dashboard/app/(dashboard)/appointments/BookingHub.tsx:874"
      },
      {
       "loai": "api",
       "chu": "Route Next chỉ chuyển tiếp → POST /api/v1/appointments/bookings (router có IdempotencyGuard)",
       "nguon": "src/clinicai/api/v1/routers/booking.py:439"
      },
      {
       "loai": "ham",
       "chu": "BookingService.create (ghi một lịch hẹn): kiểm trùng mốc của khách, bác sĩ bận, ngoài ca, sức chứa; WALK_IN + hôm nay thì hỏi quyền check-in",
       "nguon": "src/clinicai/services/booking_service.py:474"
      },
      {
       "loai": "bang",
       "chu": "INSERT appointment; thả slot_hold cùng giao dịch; Trực tiếp hôm nay: INSERT visit (mở lượt) + event_log",
       "nguon": "src/clinicai/services/booking_service.py:665"
      },
      {
       "loai": "su_kien",
       "chu": "pg_notify bảng appointment (và visit); sự kiện appointment.booked → dong_thoi_gian; Trực tiếp: visit.checked_in → hanh_trinh xếp đường đi",
       "nguon": "src/clinicai/services/booking_service.py:760"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "Màn đặt tự router.refresh + bookingSeq; màn khác nghe appointment qua RealtimeRefresher (/reception/queue, /home, /customers); /do-sinh-hieu nghe visit",
       "nguon": "src/dashboard/app/(dashboard)/RealtimeRefresher.tsx:92"
      }
     ],
     "ghi_chu": "Bị chặn khi: khách đã có lịch còn sống cùng mốc (src/clinicai/services/booking_service.py:619 + chỉ mục uq_appointment_patient_slot_live), khung đầy (src/clinicai/services/booking_service.py:656 + trigger enforce_slot_capacity), ngoài ca, chưa đọc được luật đặt lịch. Cảnh báo (bác sĩ không có ca) đi KÈM thông báo thành công, không thay nó."
    },
    {
     "man": "/appointments",
     "nut": "Bấm chọn một ô khung giờ (giữ chỗ mềm)",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "Effect trong BookingHub chờ 400ms rồi POST /api/appointments/slot-hold (rời màn thì DELETE keepalive)",
       "nguon": "src/dashboard/app/(dashboard)/appointments/BookingHub.tsx:772"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/appointments/slot-hold",
       "nguon": "src/clinicai/api/v1/routers/booking.py:856"
      },
      {
       "loai": "ham",
       "chu": "SlotHoldService.hold (báo “đang có người giữ”; tự thả chỗ cũ của chính người này)",
       "nguon": "src/clinicai/services/slot_hold_service.py:60"
      },
      {
       "loai": "bang",
       "chu": "INSERT … ON CONFLICT vào slot_hold, hết hạn sau HOLD_MINUTES = 10",
       "nguon": "src/clinicai/services/slot_hold_service.py:86"
      },
      {
       "loai": "su_kien",
       "chu": "Trigger trg_notify_slot_hold → pg_notify (không có sự kiện nghiệp vụ; cố ý không nằm trong LIVE_TABLES)",
       "nguon": "supabase/migrations/20260814000001_notify_cho_man_cskh_va_giu_cho.sql:47"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "Hook useGiuCho trên máy CSKH khác nghe tin bảng slot_hold rồi chỉ hỏi lại GET slot-hold (không dựng lại trang)",
       "nguon": "src/dashboard/app/(dashboard)/appointments/dung-giu-cho.ts:120"
      }
     ],
     "ghi_chu": "Hỏng giữ chỗ thì vẫn đặt được (luật 6.1). Đặt xong, release_on_booking thả chỗ trong cùng giao dịch lịch hẹn (src/clinicai/services/slot_hold_service.py:221)."
    },
    {
     "man": "/patients/new",
     "nut": "Bấm [Lưu] hồ sơ khách mới",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "NewPatientForm gửi POST /api/patients (trước đó đã gọi /api/patients/check-duplicate khi gõ)",
       "nguon": "src/dashboard/app/(dashboard)/patients/new/NewPatientForm.tsx:1036"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/patients — 201 tạo mới, hoặc 200 {duplicate:true} không ghi",
       "nguon": "src/clinicai/api/v1/patients.py:46"
      },
      {
       "loai": "ham",
       "chu": "PatientService.create_patient (tạo hồ sơ): CCCD trùng → đòi lý do; SĐT trùng mà chưa force → trả danh sách trùng",
       "nguon": "src/clinicai/services/patient_service.py:103"
      },
      {
       "loai": "bang",
       "chu": "Khoá advisory theo (phòng khám, SĐT) rồi INSERT patient + event_log ‘patient.created’; sau đó MPI có thể INSERT mpi_merge_queue",
       "nguon": "src/clinicai/services/patient_service.py:184"
      },
      {
       "loai": "su_kien",
       "chu": "Không có emit_event; chỉ dòng event_log patient.created. Bảng patient không nằm trong LIVE_TABLES nên không màn nào tự dựng lại",
       "nguon": "src/clinicai/services/patient_service.py:213"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "Form tự đi tiếp: đặt lịch (nếu điền khối lịch) hoặc router.push sang /customers?selected=<khách>",
       "nguon": "src/dashboard/app/(dashboard)/patients/new/NewPatientForm.tsx:886"
      }
     ],
     "ghi_chu": "MPI chạy SAU khi commit và nuốt lỗi (src/clinicai/services/patient_service.py:253) — không bao giờ làm hỏng việc tạo hồ sơ. Khoá advisory chặn hai quầy tạo cùng một khách cùng lúc."
    }
   ],
   "the": [
    {
     "hoi": "Đặt lịch không chọn bác sĩ khi mọi bác sĩ đã kín thì sao?",
     "dap": "Vẫn được nhận; lịch vào màn Chờ xếp bác sĩ, sức chứa chỉ kiểm lúc xếp bác sĩ.",
     "nguon": "docs/SO-LUAT.md:217"
    },
    {
     "hoi": "Kênh “Trực tiếp” đặt cho hôm nay khác gì lịch thường?",
     "dap": "Tự check-in trong cùng giao dịch: mở visit, phát visit.checked_in; người đặt phải có quyền reception.checkin.perform.",
     "nguon": "src/clinicai/services/booking_service.py:592"
    },
    {
     "hoi": "Bấm đặt ba lần cùng một mốc cho một khách — chặn ở đâu?",
     "dap": "submittingRef + Idempotency-Key ở màn, kiểm trước _patient_double_booked, và chỉ mục uq_appointment_patient_slot_live ở Postgres.",
     "nguon": "supabase/migrations/20260805000007_appointment_patient_slot_unique.sql:67"
    },
    {
     "hoi": "Giữ chỗ sống bao lâu, đặt xong có tự thả không?",
     "dap": "10 phút (HOLD_MINUTES); đặt xong thả ngay trong cùng giao dịch bằng release_on_booking.",
     "nguon": "src/clinicai/services/slot_hold_service.py:34"
    },
    {
     "hoi": "Huỷ lịch cần gì và ai được làm?",
     "dap": "PATCH action=cancel kèm ly_do_huy_ma (bắt buộc), quyền booking.manage; lượt đang mở bị huỷ các bước còn dở.",
     "nguon": "src/clinicai/services/booking_service.py:376"
    },
    {
     "hoi": "Tạo khách trùng SĐT thì backend trả gì?",
     "dap": "HTTP 200 {duplicate: true, matches} và KHÔNG ghi; gửi lại kèm force mới tạo. CCCD trùng thì phải kèm ly_do_trung_cccd.",
     "nguon": "src/clinicai/services/patient_service.py:172"
    }
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
   ],
   "mo_ta": "Khách tới quầy: lễ tân check-in (mở lượt khám visit, cấp số), điều dưỡng đo sinh hiệu, rồi khối Hành trình tự xếp khách vào hàng tư vấn/bác sĩ; TV phòng chờ gọi tên.",
   "dieu_phai_nho": [
    {
     "chu": "Check-in chỉ ở /reception/queue, và mọi nút check-in đi chung MỘT lệnh PATCH action=checkin.",
     "vi_sao": "Hai đường check-in từng là hai luật cấp số lệch nhau; Trang chủ đã bỏ nút check-in (một việc, một chỗ).",
     "nguon": "src/dashboard/app/(dashboard)/reception/queue/QueueBoard.tsx:77"
    },
    {
     "chu": "Số do DATABASE cấp, không do trình duyệt; hoàn tác giữ nguyên số đã cấp.",
     "vi_sao": "Màn vãng lai từng tự tính max+1 nên hai quầy bấm cùng lúc ra trùng số; nay trigger + khoá advisory theo (phòng khám, cơ sở, ngày).",
     "nguon": "supabase/migrations/20260917000009_so_tiep_don_chung.sql:10"
    },
    {
     "chu": "Hoàn tác check-in chỉ khi khách CHƯA có việc thật.",
     "vi_sao": "Đã đo, vào phòng, có chỉ định hay nộp tiền mà hoàn tác thì số đo/tiền treo trên một lượt “bỏ về”; lúc đó nhờ trưởng ca điều phối.",
     "nguon": "src/clinicai/services/hoan_tac_check_in.py:4"
    },
    {
     "chu": "Lưu sinh hiệu phải sau [Bắt đầu]; chỉ số bất thường chỉ NHẮC, không chặn.",
     "vi_sao": "Không bắt đầu thì không biết đo lúc nào (VITALS_NOT_STARTED); “đo gì ghi nấy”, ô bất thường tô vàng.",
     "nguon": "src/clinicai/services/sinh_hieu_service.py:319"
    },
    {
     "chu": "TV phòng chờ chỉ nhận tên (có thể che), thứ tự giống hệt bảng nhân viên.",
     "vi_sao": "Thứ gì endpoint TV trả về là công khai với cả phòng chờ phụ khoa/hiếm muộn; mã, SĐT, ngày sinh, bác sĩ, chẩn đoán không bao giờ rời máy chủ.",
     "nguon": "src/clinicai/services/display_board_service.py:5"
    }
   ],
   "man": [
    {
     "route": "/reception/queue",
     "ten": "Tiếp đón khách (quầy lễ tân)",
     "ai_dung": "Lễ tân (lego tiep_don)",
     "lam_duoc": [
      "Check-in khách có lịch hôm nay (nơi DUY NHẤT)",
      "Đánh Không đến; Hoàn tác check-in khi khách chưa có việc gì",
      "Đổi lịch tại chỗ sang hôm nay + check-in một lần, đổi dịch vụ khám, huỷ lịch có lý do",
      "Thêm dịch vụ làm tại quầy (+ Nước tiểu…), check-out, xem lượt",
      "Lọc / tìm trên cả bảng Lịch hẹn và danh sách tiếp đón"
     ],
     "bang_doc": [
      "appointment",
      "visit",
      "encounter_flow",
      "queue_entry",
      "patient",
      "work_roster"
     ],
     "bang_ghi": [
      "appointment",
      "visit",
      "event_log",
      "appointment_doi_lich",
      "service_order",
      "tuong_tac_cskh"
     ],
     "toc_do_ghi_chu": "Mở màn: 7 lời gọi song song ở server (src/dashboard/app/(dashboard)/reception/queue/page.tsx:50), gồm /api/v1/reception/danh-sach và /api/v1/home/lich-hen-tuan. Không thuộc man-tu-tai + gắn LiveBoardSync (src/dashboard/app/(dashboard)/reception/queue/page.tsx:67): mỗi tin appointment/visit… dựng lại CẢ trang. Sau check-in: router.refresh (src/dashboard/app/(dashboard)/reception/queue/QueueBoard.tsx:113).",
     "ghi_chu": "Lệch comment: src/dashboard/app/api/appointments/route.ts:231 ghi xac_minh_cach “BẮT BUỘC khi checkin — backend canh”, nhưng backend coi là TUỲ CHỌN (src/clinicai/services/booking_service.py:214)."
    },
    {
     "route": "/do-sinh-hieu",
     "ten": "Đo sinh hiệu",
     "ai_dung": "Điều dưỡng (lego do_sinh_hieu)",
     "lam_duoc": [
      "Danh sách khách đã check-in theo thứ tự, chờ đo",
      "Gõ chỉ số; lần gõ đầu tự gửi [Bắt đầu]",
      "Bấm [Đo xong] → lưu và sang khách kế",
      "Tick “Bỏ qua bác sĩ tư vấn” (áp ngay), thêm dịch vụ làm tại quầy"
     ],
     "bang_doc": [
      "visit",
      "encounter_flow",
      "vital_measurement",
      "queue_entry",
      "patient"
     ],
     "bang_ghi": [
      "vital_measurement",
      "encounter_flow",
      "command_receipt",
      "event_log"
     ],
     "toc_do_ghi_chu": "Nghe tin 4 bảng qua useNgheBang (src/dashboard/app/(dashboard)/do-sinh-hieu/BangDoSinhHieu.tsx:210) + nhịp an toàn 60 giây. Sau [Đo xong] await tải lại cả bảng rồi mới sang khách kế (src/dashboard/app/(dashboard)/do-sinh-hieu/BangDoSinhHieu.tsx:402).",
     "ghi_chu": "Không có luật riêng ở màn: danh sách là GET /luot-kham/bang, ghi là POST …/vitals (src/dashboard/app/(dashboard)/do-sinh-hieu/page.tsx:9)."
    },
    {
     "route": "/home",
     "ten": "Trang chủ",
     "ai_dung": "Mọi vai",
     "lam_duoc": [
      "Lời chào + ô số (việc đang chờ, khách mới hôm nay…)",
      "Bảng lịch hẹn tuần (không có nút check-in)",
      "Ca trực hôm nay của mình",
      "Đổi lịch nhanh / đổi dịch vụ khám từ menu ⋯ của dòng lịch"
     ],
     "bang_doc": [
      "appointment",
      "visit",
      "work_roster",
      "patient"
     ],
     "bang_ghi": [
      "appointment",
      "appointment_doi_lich",
      "tuong_tac_cskh"
     ],
     "toc_do_ghi_chu": "MỘT lời gọi gói /api/v1/home/bang-dieu-khien (src/dashboard/app/(dashboard)/home/page.tsx:308) thay 6 vòng PostgREST + 3 endpoint cũ; khung trang hiện ngay, dữ liệu rót vào sau (Suspense).",
     "ghi_chu": "Check-in đã chuyển khỏi Trang chủ (src/dashboard/app/(dashboard)/reception/queue/page.tsx:40)."
    },
    {
     "route": "/hanh-trinh",
     "ten": "Hành trình khách hôm nay",
     "ai_dung": "Chưa rõ lego (BAN-DO-CODE ghi quyền “?”, trang chỉ gọi requireNavAccess)",
     "lam_duoc": [
      "Mỗi khách hôm nay: đang ở đâu, đã xong gì, còn chờ gì",
      "Tìm khách, xem lượt, check-out bằng nút dùng chung"
     ],
     "bang_doc": [
      "luot_dong_thoi_gian",
      "visit",
      "queue_entry",
      "patient"
     ],
     "bang_ghi": [
      "visit"
     ],
     "toc_do_ghi_chu": "Thuộc man-tu-tai (src/dashboard/lib/man-tu-tai.ts:27): không dựng lại trang khi có tin; chỉ hỏi lại /api/v1/hanh-trinh/hom-nay khi nghe luot_dong_thoi_gian/visit/queue_entry (src/dashboard/app/(dashboard)/hanh-trinh/BangHanhTrinh.tsx:92) + nhịp 60 giây (src/dashboard/app/(dashboard)/hanh-trinh/BangHanhTrinh.tsx:85).",
     "ghi_chu": "“Đã xong gì” dựng từ sổ sự kiện (dòng thời gian), máy chủ tính hết."
    },
    {
     "route": "/display",
     "ten": "TV phòng chờ (gọi tên)",
     "ai_dung": "Máy TV đăng nhập một tài khoản nhân viên/TV; khách ngồi chờ nhìn",
     "lam_duoc": [
      "Hiện khách đang gọi / đang chờ theo khu",
      "Lọc một phòng bằng ?phong=<mã>",
      "Chỉ hiện tên (che phần giữa nếu phòng khám bật)"
     ],
     "bang_doc": [
      "appointment",
      "patient",
      "visit",
      "clinic_room",
      "lab_result",
      "clinic"
     ],
     "bang_ghi": [],
     "toc_do_ghi_chu": "Nằm ngoài layout (dashboard) nên không có RealtimeRefresher: tự router.refresh mỗi 30 giây (src/dashboard/app/display/DisplayBoard.tsx:62, src/dashboard/app/display/DisplayBoard.tsx:103) → khách vừa được gọi hiện chậm tối đa ~30 giây.",
     "ghi_chu": "Đọc qua /api/v1/display/queue (src/clinicai/api/v1/routers/display.py:67) → DisplayBoardService.board, dùng chung luật xếp hàng với bảng nhân viên."
    },
    {
     "route": "/truong-ca/tv",
     "ten": "Danh sách TV phòng chờ",
     "ai_dung": "Trưởng ca (lego dieu_phoi)",
     "lam_duoc": [
      "Liệt kê phòng bật TV (show_on_tv) kèm số đang chờ",
      "Mở TV từng phòng hoặc TV chung cả phòng khám"
     ],
     "bang_doc": [
      "clinic_room",
      "visit",
      "queue_entry"
     ],
     "bang_ghi": [],
     "toc_do_ghi_chu": "loadLive gọi song song dispatch/overview + dispatch/alerts (src/dashboard/app/(dashboard)/truong-ca/load.ts:25) nhưng màn TV chỉ dùng danh sách phòng — phần alerts tải thừa.",
     "ghi_chu": ""
    }
   ],
   "chuyen_huong": [
    {
     "route": "/queue",
     "toi": "/reception/queue"
    }
   ],
   "thao_tac": [
    {
     "man": "/reception/queue",
     "nut": "Bấm [Check-in]",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "QueueBoard (DongKhach.checkIn) gửi PATCH /api/appointments {action: checkin}; bảng Lịch hẹn dùng cùng lệnh (WeeklyAppointmentsTable.act)",
       "nguon": "src/dashboard/app/(dashboard)/reception/queue/QueueBoard.tsx:103"
      },
      {
       "loai": "api",
       "chu": "Route Next không gác vai, chuyển tiếp → PATCH /api/v1/appointments/{id}",
       "nguon": "src/clinicai/api/v1/routers/booking.py:718"
      },
      {
       "loai": "ham",
       "chu": "BookingService.apply_action → _hanh_dong_trong_gd: hỏi quyền reception.checkin.perform rồi _check_in (đổi trạng thái + cấp số)",
       "nguon": "src/clinicai/services/booking_service.py:1057"
      },
      {
       "loai": "bang",
       "chu": "check_in_appointment: appointment → CHECKED_IN + queue_number theo bác sĩ (trigger cấp so_tiep_don); INSERT visit ON CONFLICT; event_log",
       "nguon": "src/clinicai/services/booking_service.py:2624"
      },
      {
       "loai": "su_kien",
       "chu": "pg_notify appointment + visit; visit.checked_in → consumer hanh_trinh: mang chỉ định lượt trước sang + xep_sau_check_in (tư vấn / bác sĩ chính / thẳng dịch vụ)",
       "nguon": "src/clinicai/events/consumers/hanh_trinh.py:82"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "Máy bấm router.refresh; RealtimeRefresher dựng lại /reception/queue, /home; /do-sinh-hieu (useNgheBang visit) và /hanh-trinh tự hỏi lại",
       "nguon": "src/dashboard/app/(dashboard)/do-sinh-hieu/BangDoSinhHieu.tsx:210"
      }
     ],
     "ghi_chu": "Chỉ nhận lịch đang SCHEDULED/CSKH_CONFIRMED/CONFIRMED (_PRE_ARRIVAL, src/clinicai/services/booking_service.py:276); bảng Lịch hẹn chỉ hiện nút cho HÔM NAY, ngày khác phải đổi lịch sang hôm nay."
    },
    {
     "man": "/reception/queue",
     "nut": "Bấm [Hoàn tác] check-in hoặc [Không đến]",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "WeeklyAppointmentsTable.act gửi PATCH /api/appointments {action: undo_checkin | no_show}",
       "nguon": "src/dashboard/app/(dashboard)/home/WeeklyAppointmentsTable.tsx:649"
      },
      {
       "loai": "api",
       "chu": "PATCH /api/v1/appointments/{id}",
       "nguon": "src/clinicai/api/v1/routers/booking.py:718"
      },
      {
       "loai": "ham",
       "chu": "Hoàn tác: chan_hoan_tac_neu_da_lam khoá lịch → lượt → luồng rồi hỏi cờ “đã làm”; Không đến: chuyển NO_SHOW",
       "nguon": "src/clinicai/services/hoan_tac_check_in.py:128"
      },
      {
       "loai": "bang",
       "chu": "UPDATE appointment … WHERE status = ANY(trạng thái hợp lệ); hoàn tác còn chạy _cancel_visit_workflow (đóng lượt INCOMPLETE, huỷ bước còn mở)",
       "nguon": "src/clinicai/services/booking_service.py:2115"
      },
      {
       "loai": "su_kien",
       "chu": "pg_notify appointment/visit; Không đến phát appointment.no_show (chỉ dòng thời gian nghe); hoàn tác chỉ ghi event_log appointment.checkin_undone",
       "nguon": "src/clinicai/services/booking_service.py:2870"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "router.refresh ở máy bấm; các màn khác qua RealtimeRefresher (bảng appointment, visit)",
       "nguon": "src/dashboard/app/(dashboard)/home/WeeklyAppointmentsTable.tsx:659"
      }
     ],
     "ghi_chu": "“Không đến” chưa có đường hoàn tác: không transition nào nhận NO_SHOW làm trạng thái gốc (TRANSITIONS, src/clinicai/services/booking_service.py:324) — lệch luật CLAUDE.md mục 7 “mọi thao tác hoàn tác được”. Câu từ chối hoàn tác check-in hiện nguyên văn ở màn."
    },
    {
     "man": "/do-sinh-hieu",
     "nut": "Bấm [Đo xong]",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "BangDoSinhHieu gửi POST /api/luot-kham {thao_tac: sinh-hieu} kèm Idempotency-Key (giữ khoá nếu cùng số, mất mạng bấm lại không ghi hai lần)",
       "nguon": "src/dashboard/app/(dashboard)/do-sinh-hieu/BangDoSinhHieu.tsx:366"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/luot-kham/visits/{visit_id}/vitals",
       "nguon": "src/clinicai/api/v1/routers/luot_kham.py:197"
      },
      {
       "loai": "ham",
       "chu": "SinhHieuService.record_vitals (ghi một lần đo): quyền vitals.measure, phải đã [Bắt đầu], thai kỳ thì bắt thêm chỉ số",
       "nguon": "src/clinicai/services/sinh_hieu_service.py:283"
      },
      {
       "loai": "bang",
       "chu": "INSERT vital_measurement; UPDATE encounter_flow SET vitals_status = 'recorded'; biên nhận command_receipt",
       "nguon": "src/clinicai/services/sinh_hieu_service.py:344"
      },
      {
       "loai": "su_kien",
       "chu": "pg_notify vital_measurement/encounter_flow; vitals.recorded → hanh_trinh xếp hàng (tự chữa nếu lỡ sự kiện check-in)",
       "nguon": "src/clinicai/services/sinh_hieu_service.py:390"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "Màn đo tự tải lại bảng; màn khác nghe vital_measurement qua RealtimeRefresher / useNgheBang",
       "nguon": "src/dashboard/app/(dashboard)/RealtimeRefresher.tsx:105"
      }
     ],
     "ghi_chu": "Có chỉ số bất thường: ĐÃ lưu nhưng đứng lại ở khách này để thấy ô tô vàng (src/dashboard/app/(dashboard)/do-sinh-hieu/BangDoSinhHieu.tsx:404). Lần đo mới nhất thắng, lần cũ còn để xem lại."
    }
   ],
   "the": [
    {
     "hoi": "Bấm Check-in ghi những bảng nào?",
     "dap": "appointment (CHECKED_IN, queue_number, so_tiep_don), INSERT visit, event_log; rồi phát visit.checked_in.",
     "nguon": "src/clinicai/services/booking_service.py:1057"
    },
    {
     "hoi": "Số tiếp đón ở quầy (so_tiep_don) do ai cấp?",
     "dap": "Trigger trong Postgres, khoá advisory theo phòng khám + cơ sở + ngày; hoàn tác không thu hồi số.",
     "nguon": "supabase/migrations/20260917000009_so_tiep_don_chung.sql:10"
    },
    {
     "hoi": "Khi nào nút Hoàn tác check-in bị từ chối?",
     "dap": "Khách đã bắt đầu/đã đo sinh hiệu, vào phòng, bắt đầu khám, có phiếu, có chỉ định, làm dịch vụ hoặc nộp tiền.",
     "nguon": "src/clinicai/services/hoan_tac_check_in.py:29"
    },
    {
     "hoi": "Sau check-in, ai quyết khách đi tư vấn hay vào thẳng bác sĩ?",
     "dap": "Consumer hanh_trinh nghe visit.checked_in rồi gọi LuotKhamService.xep_sau_check_in.",
     "nguon": "src/clinicai/events/consumers/hanh_trinh.py:101"
    },
    {
     "hoi": "Lưu sinh hiệu khi chưa bấm Bắt đầu thì sao?",
     "dap": "409 VITALS_NOT_STARTED; màn tự gửi bat-dau-do ở lần gõ đầu tiên nên người đo ít gặp.",
     "nguon": "src/dashboard/app/(dashboard)/do-sinh-hieu/BangDoSinhHieu.tsx:328"
    },
    {
     "hoi": "TV phòng chờ cập nhật thế nào?",
     "dap": "Tự router.refresh mỗi 30 giây; không nghe SSE vì nằm ngoài layout (dashboard).",
     "nguon": "src/dashboard/app/display/DisplayBoard.tsx:62"
    }
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
   ],
   "mo_ta": "Quầy thu tiền: khách khám xong (hoặc vừa có chỉ định / đơn thuốc) đến quầy, thu ngân xem hoá đơn máy chủ dựng sẵn rồi ghi một lần thu. Hai quầy tách hẳn: tiền dịch vụ ở /thu-ngan/dich-vu, tiền thuốc ở /thu-ngan/thuoc.",
   "dieu_phai_nho": [
    {
     "chu": "Tiền do MÁY CHỦ tính, màn không tự cộng. Màn chỉ gửi lại dấu hoá đơn (revision) đã thấy; lệch thì bị từ chối BILL_CHANGED.",
     "vi_sao": "Bản cũ để trình duyệt cộng tiền, quầy thuốc từng cộng đơn giá mà quên nhân số lượng.",
     "nguon": "src/clinicai/services/payment_service.py:905"
    },
    {
     "chu": "Một lần thu = một dòng payment_cycle. Bảng payment chỉ là “hình chiếu” một dòng cho mỗi (lượt, loại tiền).",
     "vi_sao": "Tiền dịch vụ thu được nhiều lần; sự thật tài chính là payment_cycle + payment_bill_line, payment chỉ trỏ lần thu PAID mới nhất cho code cũ đọc.",
     "nguon": "src/clinicai/services/payment_service.py:2104"
    },
    {
     "chu": "Thuốc và dịch vụ thu riêng hẳn: quầy thuốc thu tiền dịch vụ (hoặc ngược lại) bị 409 QUAY_KHAC_LOAI.",
     "vi_sao": "Tuyền chốt 01/10/2026: không cho quầy này thu hộ loại tiền của quầy kia; mọi lệnh gửi kèm quay.",
     "nguon": "src/clinicai/services/payment_service.py:120"
    },
    {
     "chu": "Chuyển khoản CHƯA phải đã thu: lần thu nằm ở PENDING_VERIFICATION tới khi bấm [Đã nhận tiền]. Tiền mặt thì PAID ngay.",
     "vi_sao": "Khách quét mã không phải bằng chứng đã trả; chỉ người xác minh tiền về mới làm lần thu thành PAID.",
     "nguon": "src/clinicai/services/payment_service.py:381"
    },
    {
     "chu": "Hoàn tác lần thu ≠ hoàn tiền ≠ huỷ phiếu. Thu nhầm → [Hoàn tác lần thu]; khách đã trả đúng mà cần trả lại → Hoàn tiền (theo dòng hoá đơn). Phiếu đã có khoản hoàn thì không hoàn tác được nữa.",
     "vi_sao": "Hoàn tác mà phiếu đã hoàn tiền thì khách được trả hai lần; hoàn tiền không đụng payment/payment_cycle gốc.",
     "nguon": "src/clinicai/services/payment_service.py:1642"
    }
   ],
   "man": [
    {
     "route": "/thu-ngan/dich-vu",
     "ten": "Quầy thu tiền dịch vụ",
     "ai_dung": "Lễ tân, thu ngân, quản lý (lego Thanh toán dịch vụ)",
     "lam_duoc": [
      "Xem danh sách khách chờ thu + hoá đơn một khách (tick dịch vụ khách làm, chọn phòng)",
      "Tạo bill: tiền mặt / chuyển khoản / chia hai hình thức, giảm giá, xuất hoá đơn về công ty",
      "Xác minh hoặc huỷ lần chuyển khoản chờ; hoàn tác lần thu vừa ghi",
      "Trả trước liệu trình, mua thêm vật tư, chọn dịch vụ khám",
      "Tab Đã thanh toán hôm nay (hoàn tiền, đổi hình thức, in phiếu) và Lịch sử giao dịch"
     ],
     "bang_doc": [
      "visit",
      "service_order",
      "payment_cycle",
      "payment_bill_line",
      "payment",
      "lieu_trinh_tra_truoc"
     ],
     "bang_ghi": [
      "payment_cycle",
      "payment_cycle_phan",
      "payment_bill_line",
      "payment",
      "payment_refund",
      "lieu_trinh_tra_truoc"
     ],
     "toc_do_ghi_chu": "Mở màn: 2 request NỐI TIẾP — /api/cashier?xem=ngay-truc (src/dashboard/app/(dashboard)/thu-ngan/NgayTruc.tsx:39) phải xong (src/dashboard/app/(dashboard)/thu-ngan/TabThuNgan.tsx:62 chờ phamVi.ready) rồi mới gọi bảng /api/cashier?modes= (src/dashboard/app/(dashboard)/thu-ngan/QuayThuNgan.tsx:260). Bảng có N+1: vòng từng lượt await tinh_hoa_don + pq.cua + _quay_thu (src/clinicai/services/cashier_board_service.py:708, :716, :745, :754). Sau khi thu: await tai() đọc lại cả bảng trước khi tắt chữ “Đang ghi…” (src/dashboard/app/(dashboard)/thu-ngan/QuayThuNgan.tsx:394, finally :399). Màn tự tải (src/dashboard/lib/man-tu-tai.ts:28) — RealtimeRefresher không dựng lại trang, chỉ useNgheBang 8 bảng (src/dashboard/app/(dashboard)/thu-ngan/QuayThuNgan.tsx:301) gộp qua taoMotLuot (src/dashboard/app/(dashboard)/thu-ngan/QuayThuNgan.tsx:292).",
     "ghi_chu": "Nút ghi tiền hiện tên [Tạo bill] (src/dashboard/app/(dashboard)/thu-ngan/HoaDonMot.tsx:436); docs/SITEMAP.md:132 còn gọi là “Đã nhận đủ” — lệch. Trang chỉ là vỏ: src/dashboard/app/(dashboard)/thu-ngan/dich-vu/page.tsx:26 → TabThuNgan quay=dich_vu."
    },
    {
     "route": "/thu-ngan/thuoc",
     "ten": "Quầy thu tiền thuốc",
     "ai_dung": "Lễ tân, thu ngân, dược sĩ (lego Thu tiền thuốc)",
     "lam_duoc": [
      "Xem lượt có đơn thuốc chờ thu, chỉnh đơn bán tại quầy (khách lấy thuốc nào, số lượng)",
      "Tạo bill tiền thuốc (tiền mặt / chuyển khoản)",
      "Xác minh chuyển khoản, hoàn tác lần thu",
      "Tab Đã thanh toán hôm nay: hoàn tiền thuốc, in phiếu"
     ],
     "bang_doc": [
      "visit",
      "prescription",
      "drug_catalog",
      "payment_cycle",
      "payment"
     ],
     "bang_ghi": [
      "payment_cycle",
      "payment_cycle_phan",
      "payment_bill_line",
      "payment",
      "payment_refund"
     ],
     "toc_do_ghi_chu": "Cùng component QuayThuNgan (quay=thuoc) nên cùng 2 request nối tiếp + N+1 tinh_hoa_don từng lượt (src/clinicai/services/cashier_board_service.py:716); quầy thuốc lọc chỉ lượt có đơn (src/clinicai/services/cashier_board_service.py:634).",
     "ghi_chu": "Docstring đầu src/clinicai/services/payment_service.py:8 còn ghi “tiền thuốc chỉ thu được khi bác sĩ đã khám xong”, nhưng code từ 24/09 cho thu khi lượt đã có đơn thuốc (src/clinicai/services/payment_service.py:1885) — lệch."
    },
    {
     "route": "/thu-ngan/dich-vu/lich-su",
     "ten": "Lịch sử thu dịch vụ (chỉ xem)",
     "ai_dung": "Như quầy dịch vụ",
     "lam_duoc": [
      "Xem giao dịch đã thanh toán theo ngày / ca",
      "Lịch sử gom theo khách, lọc, xuất Excel, in phiếu"
     ],
     "bang_doc": [
      "payment_cycle",
      "payment_bill_line",
      "payment_cycle_phan",
      "payment_refund"
     ],
     "bang_ghi": [],
     "toc_do_ghi_chu": "Một request lịch sử (src/dashboard/app/(dashboard)/thu-ngan/LichSuThu.tsx:131) sau request ngày trực (src/dashboard/app/(dashboard)/thu-ngan/NgayTruc.tsx:39).",
     "ghi_chu": "Cùng TabThuNgan với chiXem=true nên không có tab Chờ thanh toán (src/dashboard/app/(dashboard)/thu-ngan/TabThuNgan.tsx:28)."
    },
    {
     "route": "/thu-ngan/thuoc/lich-su",
     "ten": "Lịch sử thu thuốc (chỉ xem)",
     "ai_dung": "Như quầy thuốc",
     "lam_duoc": [
      "Xem giao dịch tiền thuốc đã ghi theo ngày / ca",
      "In lại phiếu thu"
     ],
     "bang_doc": [
      "payment_cycle",
      "payment_bill_line",
      "payment_refund"
     ],
     "bang_ghi": [],
     "toc_do_ghi_chu": "",
     "ghi_chu": "src/dashboard/app/(dashboard)/thu-ngan/thuoc/lich-su/page.tsx:11 — TabThuNgan quay=thuoc chiXem."
    },
    {
     "route": "/print/phieu-thu/[id]",
     "ten": "In phiếu thu / phiếu hoàn / phiếu hướng dẫn phòng (khổ 80mm)",
     "ai_dung": "Người đứng quầy thu, CSKH (máy chủ gác)",
     "lam_duoc": [
      "In phiếu thu của một lần thu",
      "?loai=hoan in phiếu hoàn; ?loai=huong_dan in giấy đi phòng (id = mã lượt)"
     ],
     "bang_doc": [
      "payment_cycle",
      "payment_bill_line",
      "payment_cycle_phan",
      "payment_refund",
      "visit"
     ],
     "bang_ghi": [],
     "toc_do_ghi_chu": "Một request (src/dashboard/app/print/phieu-thu/[id]/InPhieuThu.tsx:118) → GET /api/v1/cashier/phieu/{id} (src/clinicai/api/v1/routers/cashier.py:244).",
     "ghi_chu": "Trang in không gọi requireNavAccess; quyền do máy chủ gác (CashierScopeService.receipt, src/clinicai/api/v1/routers/cashier.py:255)."
    }
   ],
   "chuyen_huong": [
    {
     "route": "/cashier/board",
     "toi": "/thu-ngan/dich-vu"
    },
    {
     "route": "/cashier",
     "toi": "/cashier/thuoc (Bảng giá thuốc — KHÔNG phải quầy thu)"
    }
   ],
   "thao_tac": [
    {
     "man": "/thu-ngan/dich-vu",
     "nut": "Mở quầy (tab Chờ thanh toán)",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "TabThuNgan chờ ngày trực xong rồi dựng QuayThuNgan; QuayThuNgan gọi /api/cashier?modes=dich_vu",
       "nguon": "src/dashboard/app/(dashboard)/thu-ngan/QuayThuNgan.tsx:260"
      },
      {
       "loai": "api",
       "chu": "Next proxy → GET /api/v1/cashier/board (router kiểm ca trực từng loại quầy)",
       "nguon": "src/clinicai/api/v1/routers/cashier.py:45"
      },
      {
       "loai": "ham",
       "chu": "CashierBoardService.board (dựng bảng quầy thu: ai chờ, hoá đơn từng người) → mỗi lượt gọi bill_service.tinh_hoa_don (tính hoá đơn còn nợ)",
       "nguon": "src/clinicai/services/cashier_board_service.py:593"
      },
      {
       "loai": "bang",
       "chu": "CHỈ ĐỌC: một câu _SQL gom visit, service_order, prescription, payment, payment_cycle, cong_no…; rồi vòng từng lượt tính hoá đơn",
       "nguon": "src/clinicai/services/cashier_board_service.py:716"
      },
      {
       "loai": "su_kien",
       "chu": "Không phát gì (chỉ đọc)",
       "nguon": "src/clinicai/services/cashier_board_service.py:613"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "Quầy tự nghe service_order, visit, queue_entry, payment, payment_cycle, prescription, luot_vat_tu, so_sua_chi_dinh để đọc lại bảng",
       "nguon": "src/dashboard/app/(dashboard)/thu-ngan/QuayThuNgan.tsx:301"
      }
     ],
     "ghi_chu": "Đây là chỗ chậm nhất của quầy: N+1 theo số lượt trong ngày (src/clinicai/services/cashier_board_service.py:708)."
    },
    {
     "man": "/thu-ngan/dich-vu",
     "nut": "Bấm [Tạo bill] (tên cũ trong tài liệu: [Đã nhận đủ])",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "HoaDonMot gọi onThu → QuayThuNgan.thuMot → gui() POST /api/payment kèm Idempotency-Key, billRevision, amount, chon",
       "nguon": "src/dashboard/app/(dashboard)/thu-ngan/QuayThuNgan.tsx:354"
      },
      {
       "loai": "api",
       "chu": "Next /api/payment → POST /api/v1/payments (router record_payment)",
       "nguon": "src/clinicai/api/v1/routers/payment.py:116"
      },
      {
       "loai": "ham",
       "chu": "PaymentService.record_payment → _thu_dich_vu (khoá lượt, đọc biên nhận) → _ghi_lan_thu_dich_vu (dựng lại hoá đơn, so revision, ghi một lần thu)",
       "nguon": "src/clinicai/services/payment_service.py:829"
      },
      {
       "loai": "bang",
       "chu": "INSERT payment_cycle; INSERT payment_cycle_phan; tiền mặt thì upsert payment (ON CONFLICT visit_id, kind); INSERT payment_bill_line (ảnh chụp từng dòng)",
       "nguon": "src/clinicai/services/payment_service.py:923"
      },
      {
       "loai": "su_kien",
       "chu": "pg_notify bảng payment_cycle + payment; sự kiện nghiệp vụ payment.service_collected (Hành trình xếp phòng H4, công nợ, dòng thời gian)",
       "nguon": "src/clinicai/services/payment_service.py:2327"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "Quầy tự tải lại (await tai()); /reception/checkout nghe payment; tab Đã thanh toán nghe payment_cycle",
       "nguon": "src/dashboard/app/(dashboard)/reception/checkout/CheckoutBoard.tsx:115"
      }
     ],
     "ghi_chu": "Chặn khi: thiếu Idempotency-Key (src/clinicai/services/payment_service.py:737), hoá đơn có dòng chưa giá / vấn đề (:874), revision hoặc số tiền lệch → BILL_CHANGED (:905), đang có lần chuyển khoản chờ xác minh (:866), sai quầy (:120). Nút tắt khi chanThu (src/dashboard/app/(dashboard)/thu-ngan/HoaDonMot.tsx:195)."
    },
    {
     "man": "/thu-ngan/dich-vu",
     "nut": "Hoàn tiền (tab Đã thanh toán hôm nay → khối Hoàn tiền)",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "HoanTien.tsx gửi action hoan-tien kèm các dòng ảnh chụp hoá đơn + số lượng + lý do, có Idempotency-Key",
       "nguon": "src/dashboard/app/(dashboard)/thu-ngan/HoanTien.tsx:60"
      },
      {
       "loai": "api",
       "chu": "Next /api/payment (action hoan-tien) → POST /api/v1/payments/hoan-tien",
       "nguon": "src/clinicai/api/v1/routers/payment.py:378"
      },
      {
       "loai": "ham",
       "chu": "HoanTienService.tao (tạo một khoản hoàn; số tiền = số lượng × đơn giá ảnh chụp)",
       "nguon": "src/clinicai/services/hoan_tien_service.py:91"
      },
      {
       "loai": "bang",
       "chu": "INSERT payment_refund (tiền mặt COMPLETED ngay, chuyển khoản PENDING) + payment_refund_line; KHÔNG sửa payment / payment_cycle gốc",
       "nguon": "src/clinicai/services/hoan_tien_service.py:388"
      },
      {
       "loai": "su_kien",
       "chu": "pg_notify payment_refund; khi tiền đã trả khách thì phát payment.refunded",
       "nguon": "src/clinicai/services/hoan_tien_service.py:460"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "Chính tab GiaoDich đọc lại qua onXong; các màn thường (vd /pharmacy) dựng lại vì payment_refund nằm trong LIVE_TABLES",
       "nguon": "src/dashboard/app/(dashboard)/thu-ngan/GiaoDich.tsx:249"
      }
     ],
     "ghi_chu": "Quyền hoàn = quyền thu đúng loại tiền (payment.service.collect / payment.medicine.collect), không chỉ quản lý (src/clinicai/services/hoan_tien_service.py:44). Hoàn tiền KHÔNG đụng kho. Tab GiaoDich nghe payment_cycle/payment/ảnh CK nhưng không nghe payment_refund (src/dashboard/app/(dashboard)/thu-ngan/GiaoDich.tsx:64) — máy khác hoàn thì tab này chưa tự đổi."
    },
    {
     "man": "/thu-ngan/dich-vu",
     "nut": "Trả trước liệu trình: [Trả trước … buổi] / [Trả hết]",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "LieuTrinhQuay gọi lenhLT('tra-truoc') với số buổi + expected_so_buoi → POST /api/lieu-trinh",
       "nguon": "src/dashboard/app/(dashboard)/thu-ngan/LieuTrinhQuay.tsx:81"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/lieu-trinh/tra-truoc",
       "nguon": "src/clinicai/api/v1/routers/lieu_trinh.py:337"
      },
      {
       "loai": "ham",
       "chu": "LieuTrinhTienService.dat_tra_truoc (đặt số buổi trả trước vào hoá đơn đang thu; kiểm tối đa, chống lệch 409 STALE_TRA_TRUOC)",
       "nguon": "src/clinicai/services/lieu_trinh_tien.py:291"
      },
      {
       "loai": "bang",
       "chu": "INSERT lieu_trinh_tra_truoc (hoặc UPDATE số buổi nếu đã có dòng đang chọn) — CHƯA có tiền nào được ghi",
       "nguon": "src/clinicai/services/lieu_trinh_tien.py:378"
      },
      {
       "loai": "su_kien",
       "chu": "Sự kiện lieu_trinh.prepay_set + pg_notify lieu_trinh_tra_truoc",
       "nguon": "src/clinicai/services/lieu_trinh_tien.py:391"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "Khối liệu trình nghe lieu_trinh/lieu_trinh_buoi/lieu_trinh_tra_truoc; onDoi gọi tai() để hoá đơn quầy có dòng mới (revision mới)",
       "nguon": "src/dashboard/app/(dashboard)/thu-ngan/LieuTrinhQuay.tsx:47"
      }
     ],
     "ghi_chu": "Trả trước chỉ THÊM DÒNG nguồn lieu_trinh vào hoá đơn (src/clinicai/services/bill_service.py:486); tiền thật ghi khi bấm [Tạo bill]. Bỏ dòng bằng [Bỏ] trên hoá đơn, máy chủ từ chối nếu dòng đã nằm trong lần thu."
    }
   ],
   "the": [
    {
     "hoi": "Thu tiền ghi vào bảng nào?",
     "dap": "payment_cycle (mỗi lần thu một dòng) + payment_cycle_phan (chia TM/CK) + payment_bill_line (ảnh chụp từng dòng hoá đơn); tiền mặt thì upsert thêm payment (hình chiếu một dòng mỗi lượt + loại).",
     "nguon": "src/clinicai/services/payment_service.py:923"
    },
    {
     "hoi": "Màn quầy thu tính tiền bằng hàm nào?",
     "dap": "Không tự tính. CashierBoardService.board gọi bill_service.tinh_hoa_don cho từng lượt (dịch vụ = hoa_don_con_no); lúc thu PaymentService gọi lại đúng hàm ấy trong giao dịch.",
     "nguon": "src/clinicai/services/cashier_board_service.py:716"
    },
    {
     "hoi": "“Một lần thu” (payment_cycle) là gì, đi qua những trạng thái nào?",
     "dap": "Một dòng mỗi payment_cycle_id, không xoá: PENDING_VERIFICATION → PAID | CANCELLED (chuyển khoản), PAID → VOIDED (huỷ phiếu có lý do).",
     "nguon": "supabase/migrations/20260919000002_tien_thuoc_cp2_payment_cycle.sql:7"
    },
    {
     "hoi": "Mất mạng, bấm [Tạo bill] lần hai thì có thu hai lần không?",
     "dap": "Không. Mỗi thao tác mang một Idempotency-Key; tiền dịch vụ giữ biên nhận trong cùng giao dịch nên gửi lại trả đúng kết quả lần đầu. Thiếu khoá thì bị từ chối.",
     "nguon": "src/clinicai/services/payment_service.py:737"
    },
    {
     "hoi": "Khách chuyển khoản xong đã tính là đã thu chưa?",
     "dap": "Chưa. Lần thu ở PENDING_VERIFICATION, chỉ thành PAID khi thu ngân bấm [Đã nhận tiền] (xac_minh_dien_tu).",
     "nguon": "src/clinicai/services/payment_service.py:144"
    },
    {
     "hoi": "Bấm [Trả trước 3 buổi] liệu trình đã thu tiền chưa?",
     "dap": "Chưa — chỉ thêm/đổi dòng lieu_trinh_tra_truoc vào hoá đơn đang thu; tiền ghi khi bấm [Tạo bill].",
     "nguon": "src/clinicai/services/lieu_trinh_tien.py:301"
    },
    {
     "hoi": "Đứng ở /thu-ngan/thuoc có thu được tiền dịch vụ không?",
     "dap": "Không. Máy chủ trả 409 QUAY_KHAC_LOAI kèm câu chỉ đúng quầy.",
     "nguon": "src/clinicai/services/payment_service.py:133"
    }
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
   ],
   "mo_ta": "Quầy thuốc sau khi bác sĩ kê đơn: dược sĩ xác định thuốc kho, khai số khách mua, (tuỳ chọn) chọn lô; thu ngân thu tiền thuốc; rồi dược sĩ giao thuốc thật từ lô ở quầy. Kèm màn xem tư vấn dùng thuốc, lịch sử bàn giao, in hoá đơn thuốc và tem lô.",
   "dieu_phai_nho": [
    {
     "chu": "Thuốc chỉ GIAO khi tiền thuốc của lượt đã thu (có payment_cycle kind=thuoc, status PAID).",
     "vi_sao": "Contract tiền–thuốc CP3/CP4: thuốc được BÁN lúc thu tiền thành công, giao chỉ là thuốc rời quầy.",
     "nguon": "src/clinicai/services/pharmacy_service.py:721"
    },
    {
     "chu": "Hiện tại thu tiền thuốc KHÔNG đòi chọn lô trước (công tắc CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY mặc định tắt); có thể “giao không lô” rồi gán lô sau.",
     "vi_sao": "Tuyền chốt 20/09 và 28/09: chưa cần quan tâm lô lúc thu; kho trừ khi gán lô sau (gan_lo_da_giao).",
     "nguon": "src/clinicai/services/payment_service.py:98"
    },
    {
     "chu": "Lần thu đã bán theo lô thì phải giao đúng lô ấy, không vượt phần chưa giao — quyết theo DỮ LIỆU, không đọc công tắc.",
     "vi_sao": "Trước 24/09 lần thu không gắn lô rơi vào nhánh “giao đúng lô đã bán” và không giao được gì (bộ mô phỏng 20 khách bắt được).",
     "nguon": "src/clinicai/services/pharmacy_service.py:728"
    },
    {
     "chu": "Chỉ giao từ lô đang nằm ở QUẦY (noi_chua='QUAY') và còn hạn dùng.",
     "vi_sao": "Tách KHO / QUẦY (G7): lô còn ở kho phải chuyển ra quầy trước; lô hết hạn thì đổi lô hoặc hoàn phần chưa giao.",
     "nguon": "src/clinicai/services/pharmacy_service.py:850"
    },
    {
     "chu": "Mỗi lệnh giao mang Idempotency-Key: một lần bấm = một khoá, gửi lại bao nhiêu lần cũng chỉ trừ tồn một lần.",
     "vi_sao": "Đo 16/09: hai lời gọi cấp 1 viên cùng lúc đều thành công, lô 50 viên còn 48 — giao một phần là hợp lệ nên máy chủ không tự phân biệt được bấm trùng.",
     "nguon": "src/clinicai/api/v1/routers/pharmacy.py:1021"
    }
   ],
   "man": [
    {
     "route": "/pharmacy",
     "ten": "Cấp thuốc (quầy thuốc)",
     "ai_dung": "Dược sĩ, lễ tân (lego Kho thuốc); thu ngân thuốc cho khối bán lẻ",
     "lam_duoc": [
      "Xem lượt có đơn theo giai đoạn tiền thuốc (chờ khám xong / sẵn sàng / chờ xác minh / đã thu)",
      "Xác định thuốc kho, khai số khách mua, chọn / bỏ / đổi lô",
      "Giao thuốc (theo lô hoặc không lô), khách không mua, chốt dòng",
      "Khách trả thuốc, huỷ phần chưa giao",
      "Mở lượt bán lẻ (khách chỉ mua thuốc) và thu tại quầy"
     ],
     "bang_doc": [
      "prescription",
      "drug_catalog",
      "drug_batch",
      "prescription_allocation",
      "payment_cycle",
      "inventory_txn"
     ],
     "bang_ghi": [
      "prescription",
      "prescription_allocation",
      "inventory_txn",
      "drug_batch",
      "event_log"
     ],
     "toc_do_ghi_chu": "SSR một request /api/v1/pharmacy/ban-thuoc (src/dashboard/app/(dashboard)/pharmacy/page.tsx:25); máy chủ đọc theo lô ~12 câu rồi ghép trong Python, không N+1 (src/clinicai/services/ban_thuoc_service.py:208). Mỗi thao tác xong gọi router.refresh() dựng lại cả trang (src/dashboard/app/(dashboard)/pharmacy/DongThuoc.tsx:119); RealtimeRefresher cũng dựng lại khi prescription/payment… đổi.",
     "ghi_chu": "Nút nào hiện do máy chủ quyết (giai_doan + thao_tac), TSX chỉ vẽ (src/clinicai/services/ban_thuoc_service.py:4). prescription_allocation và drug_batch không có trigger báo tin → chọn lô ở máy A, máy B chỉ thấy khi tải lại / nhịp 60 giây."
    },
    {
     "route": "/pharmacy/consult",
     "ten": "Tư vấn dùng thuốc",
     "ai_dung": "Dược sĩ (lego Kho thuốc)",
     "lam_duoc": [
      "Xem dòng thuốc còn việc (chưa chốt, chưa bị đính chính) kèm hướng dẫn dùng, lưu ý",
      "Tìm theo tên khách / thuốc, chọn một dòng xem chi tiết"
     ],
     "bang_doc": [
      "prescription",
      "patient"
     ],
     "bang_ghi": [],
     "toc_do_ghi_chu": "Một request SSR /api/v1/pharmacy/cho-tu-van (src/dashboard/app/(dashboard)/pharmacy/consult/page.tsx:26), tối đa 100 dòng (src/clinicai/services/pharmacy_service.py:238).",
     "ghi_chu": "Chú thích đầu ConsultBoard ghi “ghi chú tư vấn” nhưng màn không có ô lưu, không gọi API ghi nào (src/dashboard/app/(dashboard)/pharmacy/consult/ConsultBoard.tsx:4) — lệch, màn CHỈ XEM."
    },
    {
     "route": "/pharmacy/history",
     "ten": "Lịch sử bàn giao thuốc",
     "ai_dung": "Dược sĩ (lego Kho thuốc)",
     "lam_duoc": [
      "Xem dòng thuốc đã giao, mới nhất trước (tối đa 200)",
      "So ba con số: bác sĩ kê · khách mua · đã giao"
     ],
     "bang_doc": [
      "prescription",
      "drug_catalog",
      "patient"
     ],
     "bang_ghi": [],
     "toc_do_ghi_chu": "Một request SSR /api/v1/pharmacy/lich-su (src/dashboard/app/(dashboard)/pharmacy/history/page.tsx:32).",
     "ghi_chu": "Hiện tên thuốc kho quầy chọn (c.name_raw), không phải chữ bác sĩ gõ (src/clinicai/services/pharmacy_service.py:215)."
    },
    {
     "route": "/print/hoa-don-thuoc/[visitId]",
     "ten": "In hoá đơn thuốc của lượt",
     "ai_dung": "Quầy thu, CSKH (máy chủ gác)",
     "lam_duoc": [
      "Một lần thu thuốc → in thẳng phiếu 80mm",
      "Nhiều lần thu → danh sách, mỗi lần mở /print/phieu-thu/{id}"
     ],
     "bang_doc": [
      "payment_cycle",
      "payment_bill_line",
      "payment_cycle_phan"
     ],
     "bang_ghi": [],
     "toc_do_ghi_chu": "Một request (src/dashboard/app/print/hoa-don-thuoc/[visitId]/InHoaDonThuoc.tsx:16); với người không miễn kiểm, router lặp từng lần thu: kiểm quyền + dựng phiếu mỗi vòng (src/clinicai/api/v1/routers/cashier.py:282) — N+1 nhỏ.",
     "ghi_chu": ""
    },
    {
     "route": "/print/tem-lo",
     "ten": "In tem lô thuốc (mã vạch)",
     "ai_dung": "Dược sĩ, người nhập kho",
     "lam_duoc": [
      "In tem theo danh sách lô hoặc theo phiếu nhập",
      "Chọn khổ decal / A4, cỡ tem"
     ],
     "bang_doc": [
      "drug_batch",
      "drug_catalog",
      "phieu_kho_dong"
     ],
     "bang_ghi": [],
     "toc_do_ghi_chu": "Một request docKho('tem-lo') (src/dashboard/app/print/tem-lo/InTemLo.tsx:47) → ma_vach_service.du_lieu_tem (src/clinicai/services/ma_vach_service.py:360).",
     "ghi_chu": ""
    }
   ],
   "thao_tac": [
    {
     "man": "/pharmacy",
     "nut": "Chọn lô cho dòng đơn",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "DongThuoc gọi goi('phan-lo') → POST /api/pharmacy/phan-lo kèm Idempotency-Key",
       "nguon": "src/dashboard/app/(dashboard)/pharmacy/DongThuoc.tsx:397"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/pharmacy/phan-lo",
       "nguon": "src/clinicai/api/v1/routers/pharmacy.py:1195"
      },
      {
       "loai": "ham",
       "chu": "PharmacyService.phan_lo (chọn lô trước khi thu — chưa giữ chỗ); đòi khám xong, đã xác định thuốc, có số lượng, đơn vị",
       "nguon": "src/clinicai/services/pharmacy_service.py:2211"
      },
      {
       "loai": "bang",
       "chu": "INSERT prescription_allocation (không trừ kho)",
       "nguon": "src/clinicai/services/pharmacy_service.py:2267"
      },
      {
       "loai": "su_kien",
       "chu": "Chỉ ghi nhật ký event_log pharmacy.allocated; bảng prescription_allocation không có trigger báo tin",
       "nguon": "src/clinicai/services/pharmacy_service.py:2290"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "Chỉ máy đang bấm: router.refresh(); máy khác đợi nhịp 60 giây / tải lại",
       "nguon": "src/dashboard/app/(dashboard)/pharmacy/DongThuoc.tsx:119"
      }
     ],
     "ghi_chu": "Bị chặn nếu bác sĩ chưa khám xong (src/clinicai/services/pharmacy_service.py:2228) hoặc chọn quá số bán. Hai khách có thể cùng chọn một lô — người thu sau được kiểm lại."
    },
    {
     "man": "/pharmacy",
     "nut": "Bấm [Giao thuốc]",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "DongThuoc gọi goi('dispense') với allocation/lô và số lượng, kèm Idempotency-Key",
       "nguon": "src/dashboard/app/(dashboard)/pharmacy/DongThuoc.tsx:284"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/pharmacy/dispense (IdempotencyGuard, trả khoá nếu bị từ chối)",
       "nguon": "src/clinicai/api/v1/routers/pharmacy.py:1010"
      },
      {
       "loai": "ham",
       "chu": "PharmacyService.cap_phat (giao thuốc một dòng đơn): kiểm đã thu → chọn nhánh giao theo phân lô / giao thẳng (lần thu cũ) / giao không lô",
       "nguon": "src/clinicai/services/pharmacy_service.py:672"
      },
      {
       "loai": "bang",
       "chu": "INSERT inventory_txn DISPENSE (trigger trừ drug_batch.quantity_on_hand); UPDATE prescription_allocation.handed_over_qty; UPDATE prescription.dispensed_qty",
       "nguon": "src/clinicai/services/pharmacy_service.py:913"
      },
      {
       "loai": "su_kien",
       "chu": "Sự kiện medicine.dispensed + pg_notify bảng prescription",
       "nguon": "src/clinicai/services/pharmacy_service.py:781"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "/pharmacy dựng lại (router.refresh + RealtimeRefresher vì prescription trong LIVE_TABLES); quầy /thu-ngan/thuoc nghe prescription",
       "nguon": "src/dashboard/app/(dashboard)/thu-ngan/QuayThuNgan.tsx:308"
      }
     ],
     "ghi_chu": "Chặn khi: dòng đã chốt; tiền thuốc chưa thu (src/clinicai/services/pharmacy_service.py:721); lô không thuộc phần đã bán; lô ở KHO hoặc hết hạn (:850, :854); tồn trên kệ không đủ."
    }
   ],
   "the": [
    {
     "hoi": "Chưa thu tiền thuốc mà dược sĩ bấm Giao thì sao?",
     "dap": "Máy chủ từ chối 409: “Tiền thuốc của lượt này chưa thu — thu tiền thuốc trước rồi mới giao thuốc.”",
     "nguon": "src/clinicai/services/pharmacy_service.py:721"
    },
    {
     "hoi": "Giao thuốc ghi vào những bảng nào?",
     "dap": "inventory_txn (dòng DISPENSE, trigger trừ tồn lô), prescription_allocation.handed_over_qty (nếu giao theo phân lô), prescription.dispensed_qty.",
     "nguon": "src/clinicai/services/pharmacy_service.py:913"
    },
    {
     "hoi": "Chọn lô có trừ kho / giữ chỗ không?",
     "dap": "Không. Chỉ thêm một dòng prescription_allocation; thu tiền mới “bán”, giao mới trừ tồn vật lý.",
     "nguon": "src/clinicai/services/pharmacy_service.py:2219"
    },
    {
     "hoi": "Màn /pharmacy biết nút nào được bấm bằng cách nào?",
     "dap": "Máy chủ trả giai_doan của lượt và thao_tac của từng dòng / phân lô (ban_thuoc_service); TSX chỉ vẽ đúng các nút ấy.",
     "nguon": "src/clinicai/services/ban_thuoc_service.py:9"
    },
    {
     "hoi": "Màn Tư vấn dùng thuốc có lưu ghi chú tư vấn không?",
     "dap": "Không — chỉ đọc dòng đơn chưa chốt (cho_tu_van), không có API ghi.",
     "nguon": "src/clinicai/services/pharmacy_service.py:238"
    }
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
   ],
   "mo_ta": "Bước cuối của lượt khám: lễ tân đối soát (còn nợ, tiền thừa, việc dở, đang ở phòng) rồi cho khách về — đóng lượt, rời mọi hàng chờ. Có nhánh “khách về giữa chừng”.",
   "dieu_phai_nho": [
    {
     "chu": "Check-out KHÔNG đổi visit.status (FINALIZED là khoá hồ sơ bệnh án của bác sĩ). Nó chỉ hoàn tất bước LUOTKHAM-15 và ghi visit.closed_at.",
     "vi_sao": "Đặt FINALIZED từ quầy sẽ khoá vĩnh viễn hồ sơ y tế theo TT13/2011 bằng một thao tác hành chính.",
     "nguon": "src/clinicai/services/checkout_service.py:5"
    },
    {
     "chu": "Còn nợ hoặc còn tiền thừa chưa xử lý → CHẶN CỨNG, lý do ngoại lệ không vượt được. Chỉ qua bằng: thu ngay, ghi nợ (kèm lý do), hoàn / giữ lại tiền thừa.",
     "vi_sao": "Sau sự cố 30/09: khoản đã làm / đã mua mà chưa thu là nợ (01/10/2026).",
     "nguon": "src/clinicai/services/checkout_service.py:770"
    },
    {
     "chu": "Vướng khác (dịch vụ chưa làm xong, kết quả chờ đọc, khách còn ở phòng) KHÔNG chặn: lễ tân không gõ lý do thì máy tự ghi “Lễ tân cho khách về.” kèm danh sách việc dở.",
     "vi_sao": "Tuyền 24/09: chưa thực hiện dịch vụ thì vẫn cho thanh toán đi về được.",
     "nguon": "src/clinicai/api/v1/routers/dispatch.py:437"
    },
    {
     "chu": "“Khách về giữa chừng” là đường DUY NHẤT ghi visit.status = INCOMPLETE, bắt lý do, và không phải trạng thái cuối — bác sĩ vẫn ký FINALIZED sau được.",
     "vi_sao": "Trước đây chỉ có cách huỷ lịch hẹn, hồ sơ trông như khách chưa từng đến.",
     "nguon": "src/clinicai/services/checkout_service.py:741"
    },
    {
     "chu": "Check-out hoàn tác được: “mở lại lượt” (HoanTacService.mo_lai_luot) — tiền đã thu, việc đã làm giữ nguyên, khách về lại hàng chờ còn dở.",
     "vi_sao": "Luật Tuyền 01/10: mọi thao tác nhân viên bấm phải hoàn tác được, không khoá cứng.",
     "nguon": "src/clinicai/services/hoan_tac_service.py:1181"
    }
   ],
   "man": [
    {
     "route": "/reception/checkout",
     "ten": "Check-out lượt khám",
     "ai_dung": "Lễ tân (lego Tiếp đón khách)",
     "lam_duoc": [
      "Xem lượt hôm nay chưa đóng, lọc Sẵn sàng / Bị chặn, xem chi tiết đối soát",
      "Xác nhận đóng lượt (có hoặc không lý do ngoại lệ)",
      "Đóng — khách về giữa chừng (bắt lý do)",
      "Ghi nợ / huỷ ghi nợ; hoàn tiền thừa / giữ lại tiền thừa",
      "Xem lượt tồn đọng từ những ngày trước"
     ],
     "bang_doc": [
      "visit",
      "service_order",
      "payment",
      "prescription",
      "work_item",
      "cong_no"
     ],
     "bang_ghi": [
      "visit",
      "work_item",
      "queue_entry",
      "appointment",
      "event_log",
      "cong_no"
     ],
     "toc_do_ghi_chu": "SSR GET /api/v1/reception/checkout (src/dashboard/app/(dashboard)/reception/checkout/page.tsx:26) + LiveBoardSync. Máy chủ: một câu _READINESS_SQL rồi N+1 trong _gan_doi_tac_tu_thu — mỗi lượt await hoa_don_con_no, no_khi_ve, tien_thua_khi_ve, (có đơn chưa thu) tinh_hoa_don (src/clinicai/services/checkout_service.py:1064, :1071, :1085). Sau khi đóng: await reload() rồi router.refresh() — đọc lại hai lần (src/dashboard/app/(dashboard)/reception/checkout/CheckoutBoard.tsx:167).",
     "ghi_chu": "Docstring pending_list nói “Một truy vấn cho cả danh sách” (src/clinicai/services/checkout_service.py:404) — lệch vì phần gắn nợ là N+1. docs/GIAI-THICH-CODE.md:4910 ghi close() “còn vướng thì phải có lý do ngoại lệ” và file 643 dòng — lệch: router truyền ly_do_tu_dong, file nay 1196 dòng."
    }
   ],
   "thao_tac": [
    {
     "man": "/reception/checkout",
     "nut": "Bấm [Xác nhận đóng lượt khám]",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "CheckoutBoard.close(row) POST /api/reception/checkout {visit_id, override_reason, incomplete:false}; nút tắt khi no_khi_ve.chan",
       "nguon": "src/dashboard/app/(dashboard)/reception/checkout/CheckoutBoard.tsx:136"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/reception/checkout (router truyền ly_do_tu_dong)",
       "nguon": "src/clinicai/api/v1/routers/dispatch.py:414"
      },
      {
       "loai": "ham",
       "chu": "CheckoutService.close: khoá visit, tính lại vướng mắc trong giao dịch (_readiness_locked → build_blockers), chặn nếu có vướng chan",
       "nguon": "src/clinicai/services/checkout_service.py:723"
      },
      {
       "loai": "bang",
       "chu": "UPDATE work_item LUOTKHAM-15 → COMPLETED; UPDATE visit closed_at, current_room_id=NULL; appointment CHECKED_IN → COMPLETED; huỷ work_item treo (trừ việc kết quả); queue_entry → left; INSERT event_log",
       "nguon": "src/clinicai/services/checkout_service.py:823"
      },
      {
       "loai": "su_kien",
       "chu": "Sự kiện visit.checked_out (dòng thời gian, Hành trình) + pg_notify visit / work_item",
       "nguon": "src/clinicai/services/checkout_service.py:1014"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "CheckoutBoard nghe visit, work_item, payment, service_order, consultation, cong_no; quầy thu nghe visit",
       "nguon": "src/dashboard/app/(dashboard)/reception/checkout/CheckoutBoard.tsx:115"
      }
     ],
     "ghi_chu": "Bị chặn khi build_blockers có mục chan: còn nợ (src/clinicai/services/checkout_service.py:1114) hoặc tiền thừa chưa xử lý (:1131). Lỗi trả về câu đầu tiên (:775)."
    },
    {
     "man": "/reception/checkout",
     "nut": "Bấm [Đóng — khách về giữa chừng]",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "close(row, true) gửi incomplete:true + incomplete_reason (bắt buộc gõ lý do)",
       "nguon": "src/dashboard/app/(dashboard)/reception/checkout/CheckoutBoard.tsx:374"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/reception/checkout",
       "nguon": "src/clinicai/api/v1/routers/dispatch.py:414"
      },
      {
       "loai": "ham",
       "chu": "CheckoutService.close(incomplete=True): thiếu lý do thì từ chối; nợ vẫn chặn",
       "nguon": "src/clinicai/services/checkout_service.py:757"
      },
      {
       "loai": "bang",
       "chu": "Như đóng thường + UPDATE visit SET status='INCOMPLETE', incomplete_reason (chỉ khi đang OPEN/IN_PROGRESS)",
       "nguon": "src/clinicai/services/checkout_service.py:942"
      },
      {
       "loai": "su_kien",
       "chu": "Sự kiện visit.left_early + event_log visit.closed_incomplete",
       "nguon": "src/clinicai/services/checkout_service.py:1004"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "Các màn nghe visit (check-out, quầy thu, Hành trình…) cập nhật; CSKH thấy lượt khám dở để gọi lại",
       "nguon": "supabase/migrations/20260806000001_notify_change_for_live_screens.sql:62"
      }
     ],
     "ghi_chu": "Hoàn tác bằng mở lại lượt (src/clinicai/services/hoan_tac_service.py:1181)."
    },
    {
     "man": "/reception/checkout",
     "nut": "Bấm [Ghi nợ] (khách về khi còn nợ)",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "KhoanNoKhiVe gửi POST /api/reception/checkout {hanh_dong:'ghi_no', ly_do}",
       "nguon": "src/dashboard/app/(dashboard)/_lam-viec/KhoanNoKhiVe.tsx:123"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/reception/checkout/ghi-no",
       "nguon": "src/clinicai/api/v1/routers/dispatch.py:446"
      },
      {
       "loai": "ham",
       "chu": "CongNoService.ghi (ghi nợ toàn bộ khoản chưa thu, kèm lý do)",
       "nguon": "src/clinicai/services/cong_no_service.py:502"
      },
      {
       "loai": "bang",
       "chu": "INSERT (hoặc UPDATE) cong_no",
       "nguon": "src/clinicai/services/cong_no_service.py:462"
      },
      {
       "loai": "su_kien",
       "chu": "Sự kiện cong_no.ghi + pg_notify cong_no",
       "nguon": "src/clinicai/services/cong_no_service.py:479"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "CheckoutBoard nghe cong_no → vướng “còn nợ” biến mất, nút đóng lượt mở",
       "nguon": "src/dashboard/app/(dashboard)/reception/checkout/CheckoutBoard.tsx:52"
      }
     ],
     "ghi_chu": "Khoản ghi nợ vẫn thu được sau ở quầy (thu ở đây là thu nợ)."
    }
   ],
   "the": [
    {
     "hoi": "Check-out bị chặn khi nào?",
     "dap": "Chỉ khi còn nợ (khoản đã làm / đã mua chưa thu, chưa ghi nợ phủ đủ) hoặc còn tiền thừa chưa hoàn / chưa giữ lại. Các vướng khác chỉ là cảnh báo.",
     "nguon": "src/clinicai/services/checkout_service.py:1114"
    },
    {
     "hoi": "Check-out có đổi visit.status không?",
     "dap": "Đóng thường thì không (chỉ closed_at + work_item LUOTKHAM-15). Chỉ “về giữa chừng” ghi INCOMPLETE.",
     "nguon": "src/clinicai/services/checkout_service.py:823"
    },
    {
     "hoi": "Gõ lý do ngoại lệ có vượt được khoản nợ không?",
     "dap": "Không. Mục chan=True luôn chặn, kể cả về giữa chừng và đóng hộ.",
     "nguon": "src/clinicai/services/checkout_service.py:773"
    },
    {
     "hoi": "Check-out nhầm thì làm sao?",
     "dap": "Hoàn tác check-out: HoanTacService.mo_lai_luot — mở lại lượt, khách về lại hàng chờ còn dở; tiền / việc giữ nguyên.",
     "nguon": "src/clinicai/services/hoan_tac_service.py:1181"
    },
    {
     "hoi": "Đóng lượt làm gì với hàng chờ và việc còn treo?",
     "dap": "queue_entry còn mở → left; work_item PENDING/IN_PROGRESS → CANCELLED, TRỪ việc nhóm ket_qua (nhập/duyệt kết quả) vẫn giữ.",
     "nguon": "src/clinicai/services/checkout_service.py:890"
    }
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
   ],
   "mo_ta": "Sau khi khám: CSKH ghi từng lần chạm khách (gọi, nhắn, trả kết quả), gọi nhắc tái khám theo việc có hạn, theo dõi liệu trình nhiều buổi, và in kết quả lượt cho khách.",
   "dieu_phai_nho": [
    {
     "chu": "Sổ chăm sóc không bao giờ xoá: hoàn tác chỉ đặt huy_luc.",
     "vi_sao": "“Log không được xoá” — dòng ở lại, view bỏ qua; riêng mốc CHECK_IN hoàn tác còn đảo lịch thật, CHECK_OUT thì không đảo được.",
     "nguon": "src/clinicai/services/tuong_tac_cskh_service.py:302"
    },
    {
     "chu": "Khoá Idempotency-Key theo THAO TÁC, không theo lần bấm.",
     "vi_sao": "Ngắt mạng 90ms sau khi bấm thì màn báo lỗi mà dòng đã ghi; bấm lại với khoá mới sẽ ra hai dòng “Đã gọi nhắc hẹn”.",
     "nguon": "src/dashboard/app/(dashboard)/customers/khoa-mot-lan.ts:14"
    },
    {
     "chu": "Loại TRA_KQ (đã trả kết quả) chỉ ghi khi kết quả là DA_LIEN_HE.",
     "vi_sao": "View coi mọi dòng TRA_KQ là đã đóng việc “có kết quả chưa gửi”; gọi hụt mang nhãn ấy làm việc biến mất.",
     "nguon": "src/clinicai/services/tuong_tac_cskh_service.py:134"
    },
    {
     "chu": "Việc gọi nhắc tái khám được SINH lúc mở màn (GET recall-jobs), hàm sinh idempotent.",
     "vi_sao": "Không ai mở màn thì việc không ra đời; mở mười lần vẫn đúng chừng ấy việc.",
     "nguon": "src/clinicai/services/recall_job_service.py:84"
    },
    {
     "chu": "Trạng thái CSKH phải nói về LƯỢT đang xem, không phải về cả người.",
     "vi_sao": "View một-dòng-một-khách từng làm lượt tái khám chưa đến hiện “Đã check-in — đang ở đây”.",
     "nguon": "docs/GIAI-THICH-CODE.md:402"
    }
   ],
   "man": [
    {
     "route": "/customers",
     "ten": "Quản lý khách hàng (màn CSKH chuẩn)",
     "ai_dung": "CSKH (lego cham_soc_khach); lễ tân, quản lý vào được khi có quyền",
     "lam_duoc": [
      "Danh sách khách có chip việc đang mở, lọc/tìm/phân trang ở backend",
      "Vùng làm việc một khách: làm từng bước (gọi xác nhận, nhắc hẹn, trả kết quả…), ghi cuộc gọi, hoàn tác",
      "Đặt / đổi / huỷ lịch, hẹn gọi lại, ghi phản hồi, phản hồi sau dùng thuốc",
      "Tải/đánh dấu đã gửi tệp kết quả, in phiếu khám / kết quả / hoá đơn thuốc theo lượt",
      "Liệu trình của khách, nhắc tái khám (lượt 1/lượt 2)"
     ],
     "bang_doc": [
      "patient",
      "appointment",
      "v_viec_cskh",
      "tuong_tac_cskh",
      "tep_ket_qua",
      "nhac_tai_kham"
     ],
     "bang_ghi": [
      "tuong_tac_cskh",
      "hen_goi_lai",
      "phan_hoi_khach",
      "tep_ket_qua",
      "appointment",
      "event_log"
     ],
     "toc_do_ghi_chu": "Hai vòng TUẦN TỰ ở server: danh-sach-khach (src/dashboard/app/(dashboard)/customers/page.tsx:166) rồi man-khach-hang theo id các khách đang hiện (src/dashboard/app/(dashboard)/customers/page.tsx:227, gộp 10 khối thành một lời gọi); recall-jobs chạy song song (src/dashboard/app/(dashboard)/customers/page.tsx:296) và GHI (sinh việc) ngay trong lời GET. Không thuộc man-tu-tai: mỗi tin tuong_tac_cskh/appointment… dựng lại cả trang.",
     "ghi_chu": "Backend vẫn nhận loai CHECK_IN qua sổ chăm sóc và đổi lịch thật (src/clinicai/services/tuong_tac_cskh_service.py:195) — chưa rõ màn nào còn nút này; luật “check-in chỉ ở /reception/queue” nói ở BAN-DO-SUA."
    },
    {
     "route": "/nhac-tai-kham",
     "ten": "Nhắc tái khám + Liệu trình (CSKH)",
     "ai_dung": "CSKH (lego cham_soc_khach)",
     "lam_duoc": [
      "Tab Nhắc: việc gọi lượt 1 (mời đặt lịch) / lượt 2 (nhắc đi khám), ghi kết quả cuộc gọi",
      "Tab Liệu trình: “Sắp hết lộ trình”, “Đề xuất chưa đăng ký”, “Đang dở quá X ngày”",
      "Đăng ký 1/N buổi, thêm buổi, dừng, mở lại, hoàn tác, [Đã xử lý]",
      "[Đặt lịch buổi kế] bằng bộ đặt lịch sẵn có"
     ],
     "bang_doc": [
      "nhac_tai_kham",
      "lieu_trinh",
      "lieu_trinh_buoi",
      "lieu_trinh_tra_truoc",
      "patient",
      "appointment"
     ],
     "bang_ghi": [
      "nhac_tai_kham",
      "cskh_log",
      "lieu_trinh",
      "lieu_trinh_lich_su",
      "tuong_tac_cskh",
      "command_receipt"
     ],
     "toc_do_ghi_chu": "Mở màn: 3 lời gọi song song (src/dashboard/app/(dashboard)/nhac-tai-kham/page.tsx:41), trong đó GET recall-jobs sinh việc trước khi đọc. Tab Liệu trình tự tải và nghe 5 bảng (src/dashboard/app/(dashboard)/nhac-tai-kham/LieuTrinhCskh.tsx:122). Ghi kết quả gọi chỉ router.refresh ở máy bấm (src/dashboard/app/(dashboard)/nhac-tai-kham/ViecGoiNhac.tsx:82).",
     "ghi_chu": "Lệch comment: src/dashboard/app/(dashboard)/nhac-tai-kham/page.tsx:1 ghi “lấy từ GET /api/v1/cskh/recalls” nhưng code gọi /api/v1/cskh/recall-jobs. Comment “dự án chưa có bộ hẹn giờ” (src/clinicai/api/v1/routers/cskh.py:324) cũng cũ: đã có events/hen_gio.py và chuông tới hạn nhac_tai_kham.den_han (src/clinicai/events/consumers/nhac_tai_kham.py:88) — nhưng chuông KHÔNG sinh việc, sinh việc vẫn chỉ khi mở màn."
    },
    {
     "route": "/print/ket-qua-luot/[visitId]",
     "ten": "In mọi phiếu kết quả của một lượt",
     "ai_dung": "Người có quyền in phiếu (requireInPhieu), thường CSKH mở từ thanh lượt khám",
     "lam_duoc": [
      "Liệt kê chỉ định ĐÃ có kết quả (phiếu hoặc tệp) của lượt",
      "Mỗi chỉ định một nút mở /print/ket-qua/{order} để in / tải PDF / tải ảnh"
     ],
     "bang_doc": [
      "service_order",
      "form_instance",
      "tep_ket_qua",
      "visit"
     ],
     "bang_ghi": [],
     "toc_do_ghi_chu": "1 lời gọi ở trình duyệt: /api/phieu-kham?visit_id=… → /api/v1/phieu-kham/luot/{id}/ket-qua-chi-dinh (src/dashboard/app/print/ket-qua-luot/[visitId]/InKetQuaLuot.tsx:21, src/dashboard/app/api/phieu-kham/route.ts:83).",
     "ghi_chu": "BAN-DO-CODE ghi màn này gọi thẳng /api/v1/phieu/in/{order}; thực tế danh sách chỉ dẫn link sang /print/ket-qua/{order}, trang ấy mới gọi phiếu in. Bảng đọc ghi theo tên khối, chưa soát từng câu SQL."
    }
   ],
   "chuyen_huong": [
    {
     "route": "/cskh-tasks",
     "toi": "/customers"
    },
    {
     "route": "/episodes",
     "toi": "/customers"
    },
    {
     "route": "/patients/[id]",
     "toi": "/patient-list?chon=<id>"
    }
   ],
   "thao_tac": [
    {
     "man": "/customers",
     "nut": "Bấm một bước ở vùng làm việc khách (ghi cuộc gọi chăm sóc)",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "HanhDongTrangThai.ghi gửi POST /api/cskh/tuong-tac, Idempotency-Key = khoaThaoTac(khách, lịch, loại, bước, kết quả)",
       "nguon": "src/dashboard/app/(dashboard)/customers/HanhDongTrangThai.tsx:298"
      },
      {
       "loai": "api",
       "chu": "Route Next chuyển tiếp khoá → POST /api/v1/cskh/tuong-tac (IdempotencyGuard, trả khoá khi bị từ chối nghiệp vụ)",
       "nguon": "src/clinicai/api/v1/routers/cskh.py:491"
      },
      {
       "loai": "ham",
       "chu": "TuongTacCskhService.ghi (ghi một lần chạm): kiểm loại/kênh/kết quả, lịch phải của khách này",
       "nguon": "src/clinicai/services/tuong_tac_cskh_service.py:109"
      },
      {
       "loai": "bang",
       "chu": "INSERT tuong_tac_cskh + INSERT event_log ‘cskh.tuong_tac’ cùng giao dịch; idempotency_key giữ phản hồi",
       "nguon": "src/clinicai/services/tuong_tac_cskh_service.py:238"
      },
      {
       "loai": "su_kien",
       "chu": "pg_notify tuong_tac_cskh (trigger 14/08); sự kiện patient.contacted (chưa có consumer)",
       "nguon": "src/clinicai/services/tuong_tac_cskh_service.py:279"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "Máy bấm router.refresh; CSKH khác: RealtimeRefresher dựng lại /customers (tuong_tac_cskh trong LIVE_TABLES); khối liệu trình nghe tuong_tac_cskh",
       "nguon": "src/dashboard/app/(dashboard)/RealtimeRefresher.tsx:126"
      }
     ],
     "ghi_chu": "Luật chéo: BO_QUA ⟺ kênh KHONG_LIEN_HE; mốc quầy (CHECK_IN/CHECK_OUT/THANH_TOAN/MUA_THUOC) phải TRUC_TIEP + GHI_NHAN; 5 loại bắt buộc gắn lịch hẹn (CAN_LICH_HEN). Lỗi 4xx thì màn bỏ khoá để lần sau là thao tác mới (src/dashboard/app/(dashboard)/customers/HanhDongTrangThai.tsx:362)."
    },
    {
     "man": "/nhac-tai-kham",
     "nut": "Ghi kết quả cuộc gọi nhắc tái khám (Đã liên hệ / Chưa nghe máy / Cần bác sĩ / Từ chối)",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "ViecGoiNhac.ghi gửi POST /api/recall-jobs/{id}/ket-qua (không kèm Idempotency-Key)",
       "nguon": "src/dashboard/app/(dashboard)/nhac-tai-kham/ViecGoiNhac.tsx:69"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/cskh/recall-jobs/{viec_id}/ket-qua",
       "nguon": "src/clinicai/api/v1/routers/cskh.py:344"
      },
      {
       "loai": "ham",
       "chu": "RecallJobService.ghi_ket_qua (đóng một việc gọi; kết quả bắt buộc kể cả khi không ai nghe)",
       "nguon": "src/clinicai/services/recall_job_service.py:238"
      },
      {
       "loai": "bang",
       "chu": "UPDATE nhac_tai_kham SET trang_thai = 'DA_GOI' … WHERE trang_thai = 'CHO_GOI' (bấm hai lần không ghi đè) + INSERT cskh_log cùng giao dịch",
       "nguon": "src/clinicai/services/recall_job_service.py:262"
      },
      {
       "loai": "su_kien",
       "chu": "Không emit_event; không thấy trigger notify trên nhac_tai_kham, cskh_log cũng không nằm trong LIVE_TABLES",
       "nguon": "src/dashboard/app/(dashboard)/RealtimeRefresher.tsx:88"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "Chỉ máy bấm router.refresh; CSKH khác chỉ thấy khi tải lại trang (hoặc khi một tin bảng khác làm trang dựng lại)",
       "nguon": "src/dashboard/app/(dashboard)/nhac-tai-kham/ViecGoiNhac.tsx:82"
      }
     ],
     "ghi_chu": "Chống ghi trùng nhờ một câu UPDATE có điều kiện trạng thái (luật 6.2), không nhờ khoá; bấm lại trả {da_ghi_tu_truoc: true}. Việc chưa tới hạn (han_goi > hôm nay) bị từ chối."
    },
    {
     "man": "/nhac-tai-kham",
     "nut": "Tab Liệu trình → [Đăng ký] 1 buổi / N buổi",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "LieuTrinhKhach gửi {thao_tac: dang-ky, so_buoi, expected_revision, idempotency_key ‘lt-<id>-dang-ky-<n>-r<revision>’} tới /api/cskh/lieu-trinh/{id}",
       "nguon": "src/dashboard/app/(dashboard)/_lam-viec/LieuTrinhKhach.tsx:369"
      },
      {
       "loai": "api",
       "chu": "Route Next ghép thao_tac vào đường → POST /api/v1/lieu-trinh/{id}/dang-ky",
       "nguon": "src/clinicai/api/v1/routers/lieu_trinh.py:174"
      },
      {
       "loai": "ham",
       "chu": "LieuTrinhService.dang_ky (chỉ ghi đăng ký; tiền thu ở quầy khi khách đến) — so revision, liệu trình đã dừng thì phải mở lại trước",
       "nguon": "src/clinicai/services/lieu_trinh_service.py:1309"
      },
      {
       "loai": "bang",
       "chu": "UPDATE lieu_trinh (trigger suy trạng thái + ghi lieu_trinh_lich_su); biên nhận command_receipt",
       "nguon": "src/clinicai/services/lieu_trinh_service.py:1006"
      },
      {
       "loai": "su_kien",
       "chu": "pg_notify lieu_trinh/lieu_trinh_lich_su; lieu_trinh.revised (không có consumer)",
       "nguon": "src/clinicai/services/lieu_trinh_service.py:976"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "LieuTrinhCskh và khối liệu trình ở khung khách (/customers) tự nạp lại qua useNgheBang",
       "nguon": "src/dashboard/app/(dashboard)/nhac-tai-kham/LieuTrinhCskh.tsx:122"
      }
     ],
     "ghi_chu": "Người khác vừa sửa → 409 STALE_LIEU_TRINH “đã tải lại, xem bản mới rồi bấm lại” (src/clinicai/services/lieu_trinh_service.py:957). Khoá có số revision nên bấm đúp cùng bản là một lần."
    }
   ],
   "the": [
    {
     "hoi": "Hoàn tác một cuộc gọi chăm sóc có xoá dòng sổ không?",
     "dap": "Không; chỉ UPDATE huy_luc, huy_boi_staff_id. View bỏ qua dòng đã huỷ.",
     "nguon": "src/clinicai/services/tuong_tac_cskh_service.py:398"
    },
    {
     "hoi": "Ghi cuộc gọi chăm sóc vào bảng nào?",
     "dap": "tuong_tac_cskh (kèm event_log ‘cskh.tuong_tac’), qua TuongTacCskhService.ghi.",
     "nguon": "src/clinicai/services/tuong_tac_cskh_service.py:238"
    },
    {
     "hoi": "Việc gọi nhắc tái khám (nhac_tai_kham) sinh ra khi nào?",
     "dap": "Mỗi lần gọi GET /cskh/recall-jobs (mở /customers hoặc /nhac-tai-kham): danh_sach() gọi sinh() trước khi đọc.",
     "nguon": "src/clinicai/services/recall_job_service.py:84"
    },
    {
     "hoi": "Ghi kết quả gọi nhắc tái khám ghi vào đâu?",
     "dap": "UPDATE nhac_tai_kham sang DA_GOI + INSERT cskh_log, cùng một giao dịch.",
     "nguon": "src/clinicai/services/recall_job_service.py:308"
    },
    {
     "hoi": "Đăng ký liệu trình có thu tiền không?",
     "dap": "Không — chỉ ghi đăng ký (đề xuất → DANG_LAM); tiền thu ở quầy khi khách đến.",
     "nguon": "src/clinicai/services/lieu_trinh_service.py:1318"
    },
    {
     "hoi": "CSKH in kết quả của một lượt cho khách bằng đường nào?",
     "dap": "Thanh lượt khám hỏi visit_id qua /api/cskh/ho-so-kham/{lịch} rồi mở /print/ket-qua-luot/{visit}.",
     "nguon": "src/dashboard/app/(dashboard)/customers/ThanhLuotKham.tsx:77"
    }
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
   ],
   "mo_ta": "Kho thuốc (lô, nhập phiếu, kiểm kho, kiểm kê ca, chuyển kho ↔ quầy, thẻ kho) và kho vật tư tiêu hao (sổ riêng theo nơi chứa / phòng). Không trực tiếp trong hành trình khách nhưng cấp nguồn cho quầy thuốc và phòng dịch vụ.",
   "dieu_phai_nho": [
    {
     "chu": "Sổ kho chỉ thêm; tồn không sửa tay mà do trigger cộng dồn từng dòng sổ (inventory_txn → drug_batch.quantity_on_hand; vat_tu_txn → vat_tu_ton.so_luong).",
     "vi_sao": "Trạng thái tính từ số liệu thì không bao giờ lệch với số liệu; sai thì ghi dòng điều chỉnh / phiếu đảo, không xoá.",
     "nguon": "supabase/migrations/20260802000001_pharmacy_inventory.sql:124"
    },
    {
     "chu": "Tồn THUỐC không được âm (CHECK drug_batch_qty_non_negative); tồn VẬT TƯ được âm, chỉ hiện cảnh báo “tồn âm — cần kiểm đếm”.",
     "vi_sao": "Thuốc là vật thật phải khớp kệ; vật tư tiêu hao đếm định kỳ, giữ chênh âm để soát thay vì chặn công việc.",
     "nguon": "src/clinicai/services/vat_tu_kho_service.py:442"
    },
    {
     "chu": "Kiểm kê ca: CHỐT chỉ ghi tồn máy + lệch, KHÔNG sửa tồn. “Điều chỉnh theo kiểm kê” là bước riêng ghi ADJUST, bắt lý do, hoàn tác được.",
     "vi_sao": "Tuyền chốt (G6): đếm là đếm, sửa sổ là quyết định riêng có người chịu trách nhiệm; lệch thì chuông báo người được giao.",
     "nguon": "src/clinicai/services/kiem_ke_ca_service.py:9"
    },
    {
     "chu": "Phiếu nhập thuốc / phiếu vật tư bắt buộc Idempotency-Key và chạy MỘT giao dịch: dòng nào hỏng thì cả phiếu không vào; gửi lại cùng khoá = cùng phiếu.",
     "vi_sao": "Chống nhập trùng khi mất mạng bấm lại (UNIQUE khoá gửi ở Postgres).",
     "nguon": "src/clinicai/services/kho_thuoc_service.py:499"
    },
    {
     "chu": "Phiếu vật tư đã lưu không thêm / sửa dòng; sai thì lập phiếu đảo (HOAN) đối ứng đúng từng dòng gốc.",
     "vi_sao": "Trigger chặn thêm dòng vào phiếu của giao dịch khác và ép phiếu đảo phải khớp số, giá, nơi chứa.",
     "nguon": "supabase/migrations/20261014180000_vat_tu_so_kho.sql:104"
    }
   ],
   "man": [
    {
     "route": "/pharmacy/inventory",
     "ten": "Kho thuốc",
     "ai_dung": "Dược sĩ, lễ tân xem (lego Kho thuốc); ghi kho cần quyền pharmacy.dispense",
     "lam_duoc": [
      "Xem tồn theo lô + hạn dùng, danh mục thuốc (tên, giá, hướng dẫn)",
      "Phiếu nhập nhiều dòng, nhập lô, điều chỉnh, huỷ lô hết hạn (hoàn tác được)",
      "Kiểm kho, kiểm kê đầu / cuối ca (đếm → chốt → điều chỉnh)",
      "Chuyển kho ↔ quầy, gán lô cho thuốc đã giao, xử lý thuốc khách trả",
      "Thẻ kho, xuất nhập tồn (Excel), in tem lô"
     ],
     "bang_doc": [
      "drug_batch",
      "drug_catalog",
      "inventory_txn",
      "phieu_kho",
      "kiem_ke_ca",
      "prescription"
     ],
     "bang_ghi": [
      "inventory_txn",
      "drug_batch",
      "phieu_kho",
      "phieu_kho_dong",
      "kiem_ke_ca",
      "kiem_ke_ca_dong"
     ],
     "toc_do_ghi_chu": "SSR 7 request song song (Promise.all) khi mở màn (src/dashboard/app/(dashboard)/pharmacy/inventory/page.tsx:50). Chốt kiểm kê lặp UPDATE từng dòng đếm (tối đa 500) trong giao dịch (src/clinicai/services/kiem_ke_ca_service.py:950). drug_batch / inventory_txn không có trong LIVE_TABLES → nhập ở máy khác thì màn này chỉ đổi khi tải lại / nhịp 60 giây; máy mình gọi router.refresh() (src/dashboard/app/(dashboard)/pharmacy/inventory/PhieuNhap.tsx:202).",
     "ghi_chu": "docs/GIAI-THICH-CODE.md:4931 ghi pharmacy_service.py 657 dòng — nay 3335 dòng (lệch, chỉ số liệu)."
    },
    {
     "route": "/kho-vat-tu",
     "ten": "Kho vật tư",
     "ai_dung": "Mọi người xem (lego Kho vật tư); quản lý chỉnh mức tối thiểu; lego Duyệt vật tư duyệt phiếu nhập cần duyệt",
     "lam_duoc": [
      "Xem tồn từng nơi chứa (kho chung / từng phòng) + cảnh báo dưới mức / tồn âm",
      "Lập phiếu: nhập, xuất phòng, trả kho, chuyển phòng, kiểm, điều chỉnh, huỷ, trả nhà sản xuất",
      "Đảo (hoàn) một phiếu",
      "Duyệt / từ chối / rút lại yêu cầu nhập chờ duyệt",
      "Báo cáo tiêu hao theo khoảng ngày"
     ],
     "bang_doc": [
      "vat_tu_ton",
      "vat_tu_phieu",
      "vat_tu_txn",
      "service_price",
      "clinic_room",
      "vat_tu_nhap_cho_duyet"
     ],
     "bang_ghi": [
      "vat_tu_phieu",
      "vat_tu_txn",
      "vat_tu_ton",
      "vat_tu_nhap_cho_duyet"
     ],
     "toc_do_ghi_chu": "SSR 4 request song song (src/dashboard/app/(dashboard)/kho-vat-tu/page.tsx:24). Nghe vat_tu_txn → router.refresh() dựng lại cả trang + đọc lại báo cáo tiêu hao (src/dashboard/app/(dashboard)/kho-vat-tu/KhoVatTu.tsx:72).",
     "ghi_chu": "Danh mục vật tư không có bảng riêng: là service_price nhóm 'vat_tu' (vat_tu_ton.vat_tu_id → service_price). Sổ kho vật tư tách khỏi vật tư bán ở quầy thu (luot_vat_tu) — chú thích migration: “không chạm thuốc hay vật tư đã thu tiền” (supabase/migrations/20261014180000_vat_tu_so_kho.sql:1)."
    }
   ],
   "thao_tac": [
    {
     "man": "/pharmacy/inventory",
     "nut": "Lưu phiếu nhập (tab Nhập)",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "PhieuNhap gọi guiKho('phieu-nhap') kèm Idempotency-Key → POST /api/pharmacy/phieu-nhap",
       "nguon": "src/dashboard/app/(dashboard)/pharmacy/inventory/PhieuNhap.tsx:169"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/pharmacy/phieu-nhap",
       "nguon": "src/clinicai/api/v1/routers/pharmacy.py:598"
      },
      {
       "loai": "ham",
       "chu": "kho_thuoc_service.tao_phieu_nhap (phiếu nhập nhiều dòng, một giao dịch) → từng dòng: quy_doi_dong_nhap + nhap_vao_lo",
       "nguon": "src/clinicai/services/kho_thuoc_service.py:488"
      },
      {
       "loai": "bang",
       "chu": "INSERT phieu_kho; mỗi dòng: tạo / dùng drug_batch, INSERT inventory_txn RECEIVE (trigger cộng tồn), INSERT phieu_kho_dong",
       "nguon": "src/clinicai/services/kho_thuoc_service.py:612"
      },
      {
       "loai": "su_kien",
       "chu": "Chỉ nhật ký event_log pharmacy.phieu_nhap; drug_batch / inventory_txn không có trigger báo tin",
       "nguon": "src/clinicai/services/kho_thuoc_service.py:634"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "Chỉ máy đang bấm: router.refresh(); máy khác đợi tải lại / nhịp 60 giây",
       "nguon": "src/dashboard/app/(dashboard)/pharmacy/inventory/PhieuNhap.tsx:202"
      }
     ],
     "ghi_chu": "Hạn dùng rác (vd 2027-02-31) bị từ chối thay vì lưu im thành “chưa có hạn” (src/clinicai/services/kho_thuoc_service.py:518). Số lô trùng trong phiếu bị từ chối."
    },
    {
     "man": "/pharmacy/inventory",
     "nut": "Kiểm kê ca: bấm [Chốt]",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "KiemKeCa lưu số đếm rồi buocPhieu('chot') → POST /api/pharmacy/kiem-ke-ca/{id}/chot",
       "nguon": "src/dashboard/app/(dashboard)/pharmacy/inventory/KiemKeCa.tsx:296"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/pharmacy/kiem-ke-ca/{phieu_id}/chot",
       "nguon": "src/clinicai/api/v1/routers/pharmacy.py:878"
      },
      {
       "loai": "ham",
       "chu": "kiem_ke_ca_service.chot (ghi tồn máy ở quầy tại giờ chốt, lệch = đếm − tồn máy; chốt lần hai trả lại phiếu cũ)",
       "nguon": "src/clinicai/services/kiem_ke_ca_service.py:884"
      },
      {
       "loai": "bang",
       "chu": "UPDATE kiem_ke_ca_dong (ton_may, lech) từng dòng; UPDATE kiem_ke_ca trang_thai='CHOT'. KHÔNG đụng drug_batch",
       "nguon": "src/clinicai/services/kiem_ke_ca_service.py:973"
      },
      {
       "loai": "su_kien",
       "chu": "pg_notify kiem_ke_ca; có lệch thì sự kiện pharmacy.stocktake_mismatch (chuông)",
       "nguon": "src/clinicai/services/kiem_ke_ca_service.py:998"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "KiemKeCa nạp phiếu trả về + đọc lại danh sách; kiem_ke_ca nằm trong LIVE_TABLES nên màn thường dựng lại",
       "nguon": "src/dashboard/app/(dashboard)/RealtimeRefresher.tsx:143"
      }
     ],
     "ghi_chu": "Muốn sửa tồn theo số đếm: bước riêng [Điều chỉnh theo kiểm kê] (src/clinicai/services/kiem_ke_ca_service.py:1023) ghi ADJUST, bắt lý do, hoàn tác được."
    },
    {
     "man": "/kho-vat-tu",
     "nut": "Lập phiếu xuất vật tư cho phòng (XUAT_PHONG)",
     "buoc": [
      {
       "loai": "giao_dien",
       "chu": "LapPhieuVatTu gọi guiVatTu('phieu', dữ liệu, khoá) → POST /api/vat-tu-kho/phieu",
       "nguon": "src/dashboard/app/(dashboard)/kho-vat-tu/LapPhieuVatTu.tsx:248"
      },
      {
       "loai": "api",
       "chu": "POST /api/v1/vat-tu-kho/phieu",
       "nguon": "src/clinicai/api/v1/routers/vat_tu_kho.py:110"
      },
      {
       "loai": "ham",
       "chu": "vat_tu_kho_service.tao_phieu (ghi nguyên phiếu) → _ghi_phieu: mỗi dòng XUAT_PHONG ghi hai dòng sổ (trừ nơi đi, cộng nơi đến)",
       "nguon": "src/clinicai/services/vat_tu_kho_service.py:308"
      },
      {
       "loai": "bang",
       "chu": "INSERT vat_tu_phieu; INSERT vat_tu_ton nếu nơi chứa chưa có; INSERT vat_tu_txn (−số ở kho, +số ở phòng); trigger vat_tu_txn_cong_ton cộng tồn",
       "nguon": "src/clinicai/services/vat_tu_kho_service.py:290"
      },
      {
       "loai": "su_kien",
       "chu": "pg_notify vat_tu_phieu / vat_tu_ton / vat_tu_txn (không có sự kiện nghiệp vụ)",
       "nguon": "supabase/migrations/20261014180000_vat_tu_so_kho.sql:181"
      },
      {
       "loai": "man_cap_nhat",
       "chu": "KhoVatTu nghe vat_tu_txn → router.refresh() + đọc lại báo cáo tiêu hao",
       "nguon": "src/dashboard/app/(dashboard)/kho-vat-tu/KhoVatTu.tsx:72"
      }
     ],
     "ghi_chu": "Lúc COMMIT trigger kiểm nguyên phiếu: không thể chuyển một nửa (supabase/migrations/20261014180000_vat_tu_so_kho.sql:147). Phiếu NHẬP có hàng cần duyệt thì thành yêu cầu chờ duyệt, chưa ghi sổ (src/clinicai/services/vat_tu_kho_service.py:351)."
    }
   ],
   "the": [
    {
     "hoi": "Tồn một lô thuốc nằm ở đâu, ai cập nhật?",
     "dap": "drug_batch.quantity_on_hand; chỉ trigger inventory_txn_apply cộng dồn khi có dòng inventory_txn mới.",
     "nguon": "supabase/migrations/20260802000001_pharmacy_inventory.sql:124"
    },
    {
     "hoi": "Chốt phiếu kiểm kê ca có sửa tồn không?",
     "dap": "Không. Chỉ ghi tồn máy + lệch; sửa tồn là bước “Điều chỉnh theo kiểm kê” riêng (ADJUST).",
     "nguon": "src/clinicai/services/kiem_ke_ca_service.py:889"
    },
    {
     "hoi": "Tồn vật tư có thể âm không?",
     "dap": "Có — không có CHECK ≥ 0 như thuốc; màn hiện cảnh báo “tồn âm — cần kiểm đếm”.",
     "nguon": "src/clinicai/services/vat_tu_kho_service.py:442"
    },
    {
     "hoi": "Xuất vật tư cho phòng ghi gì?",
     "dap": "Một vat_tu_phieu loại XUAT_PHONG; mỗi mặt hàng hai dòng vat_tu_txn: âm ở kho chung (room_id rỗng), dương ở phòng.",
     "nguon": "src/clinicai/services/vat_tu_kho_service.py:290"
    },
    {
     "hoi": "Danh mục vật tư lưu ở bảng nào?",
     "dap": "service_price nhóm 'vat_tu' (không có bảng danh mục vật tư riêng).",
     "nguon": "src/clinicai/services/vat_tu_kho_service.py:204"
    }
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
   "chu": "Tải bảng quầy thu p95 ~3,4s; câu SQL quầy thu trung bình 4,3s, tối đa 14s. Ghi một lần thu chỉ ~0,13s — chậm nằm ở bảng, không ở nút. Gốc: CashierBoardService.board tính hoá đơn TỪNG khách nối tiếp (~10–25 câu SQL/khách) và vế 'lượt cũ chưa về' không có mốc ngày (#530 B4, cashier_board_service.py:593, 708–772). Sau khi bấm [Tạo bill] (SITEMAP còn gọi tên cũ [Đã nhận đủ]) màn còn await tai() tải lại cả bảng rồi mới tắt nút (QuayThuNgan.tsx:394)."
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
   "ma": "/api/payment → POST /api/v1/payments",
   "loai": "route",
   "ten": "Cửa ghi lần thu (và hoàn tiền, hoàn tác, xác minh qua action)",
   "manh": "payment = thanh toán",
   "dong_nghia": [
    "record_payment"
   ],
   "nguon": "src/clinicai/api/v1/routers/payment.py:116"
  },
  {
   "ma": "/api/v1/appointments/bookings",
   "loai": "route",
   "ten": "API đặt lịch",
   "manh": "bookings = các lần đặt",
   "dong_nghia": [
    "/api/appointments POST"
   ],
   "nguon": "src/clinicai/api/v1/routers/booking.py:439"
  },
  {
   "ma": "_gan_doi_tac_tu_thu",
   "loai": "hàm",
   "ten": "Gắn trạng thái còn nợ / tiền thừa cho từng lượt check-out",
   "manh": "gan = gắn · doi_tac_tu_thu = đối tác tự thu",
   "dong_nghia": [],
   "nguon": "src/clinicai/services/checkout_service.py:1051"
  },
  {
   "ma": "_ghi_da_thu",
   "loai": "hàm",
   "ten": "Upsert hình chiếu payment + POS outbox + sự kiện khi tiền thật đã nhận",
   "manh": "ghi = ghi · da_thu = đã thu",
   "dong_nghia": [],
   "nguon": "src/clinicai/services/payment_service.py:2064"
  },
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
   "ma": "_thu_dich_vu / _ghi_lan_thu_dich_vu",
   "loai": "hàm",
   "ten": "Thu tiền dịch vụ (khoá lượt, biên nhận) / ghi lần thu dịch vụ",
   "manh": "thu = thu tiền · dich_vu = dịch vụ · ghi_lan_thu = ghi lần thu",
   "dong_nghia": [],
   "nguon": "src/clinicai/services/payment_service.py:708"
  },
  {
   "ma": "appointment",
   "loai": "bảng",
   "ten": "Lịch hẹn (lời hứa)",
   "manh": "appointment = cuộc hẹn",
   "dong_nghia": [
    "lịch",
    "lich hẹn",
    "booking"
   ],
   "nguon": "supabase/migrations/20260714000001_baseline_schema.sql:313"
  },
  {
   "ma": "appointment.booked",
   "loai": "sự kiện",
   "ten": "Lịch đã đặt",
   "manh": "booked = đã đặt",
   "dong_nghia": [
    "LichDaDat"
   ],
   "nguon": "src/clinicai/events/catalogue.py:1930"
  },
  {
   "ma": "appointment_doi_lich",
   "loai": "bảng",
   "ten": "Lịch sử đổi lịch (từ → đến, ai, lý do)",
   "manh": "doi_lich = đổi lịch",
   "dong_nghia": [
    "reschedule"
   ],
   "nguon": "supabase/migrations/20260924000004_ket_qua_chuong_doi_lich.sql:58"
  },
  {
   "ma": "ban_thuoc_service.man_nha_thuoc / giai_doan",
   "loai": "hàm",
   "ten": "Dữ liệu màn Nhà thuốc + giai đoạn tiền thuốc của lượt",
   "manh": "ban_thuoc = bán thuốc · man = màn · giai_doan = giai đoạn",
   "dong_nghia": [
    "CHUA_SAN_SANG",
    "SAN_SANG",
    "CHO_XAC_MINH",
    "DA_THU"
   ],
   "nguon": "src/clinicai/services/ban_thuoc_service.py:199"
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
   "ma": "BILL_CHANGED (BillChangedError)",
   "loai": "khái niệm",
   "ten": "Lỗi “hoá đơn vừa thay đổi — tải lại rồi thu”",
   "manh": "bill = hoá đơn · changed = đã đổi",
   "dong_nghia": [],
   "nguon": "src/clinicai/api/exceptions.py:27"
  },
  {
   "ma": "bill_service.tinh_hoa_don",
   "loai": "hàm",
   "ten": "Tính hoá đơn (thuốc / dịch vụ) từ dữ liệu chuẩn",
   "manh": "bill = hoá đơn · tinh_hoa_don = tính hoá đơn",
   "dong_nghia": [
    "hoá đơn máy chủ",
    "HoaDon"
   ],
   "nguon": "src/clinicai/services/bill_service.py:1126"
  },
  {
   "ma": "billing_owner",
   "loai": "cột",
   "ten": "Bên thu của dòng: CLINIC (phòng khám) hay EXTERNAL_PARTNER (khách trả đối tác)",
   "manh": "billing = thu tiền · owner = chủ",
   "dong_nghia": [
    "đối tác tự thu",
    "thu hộ đối tác"
   ],
   "nguon": "src/clinicai/services/bill_service.py:41"
  },
  {
   "ma": "booking_channel",
   "loai": "cột",
   "ten": "Kênh đặt lịch (WALK_IN = trực tiếp tại quầy)",
   "manh": "booking = đặt · channel = kênh; is_walkin phải khớp",
   "dong_nghia": [
    "kênh",
    "WALK_IN",
    "Trực tiếp",
    "vãng lai"
   ],
   "nguon": "src/clinicai/services/booking_service.py:435"
  },
  {
   "ma": "BookingService",
   "loai": "hàm",
   "ten": "Dịch vụ lịch hẹn (đặt + máy trạng thái)",
   "manh": "booking = đặt lịch · service = tầng luật",
   "dong_nghia": [
    "booking_service.py"
   ],
   "nguon": "src/clinicai/services/booking_service.py:466"
  },
  {
   "ma": "BookingService.apply_action",
   "loai": "hàm",
   "ten": "Chuyển trạng thái lịch (checkin, undo_checkin, no_show, cancel, reschedule…)",
   "manh": "apply = áp · action = hành động",
   "dong_nghia": [
    "PATCH /api/v1/appointments/{id}"
   ],
   "nguon": "src/clinicai/services/booking_service.py:838"
  },
  {
   "ma": "BookingService.create",
   "loai": "hàm",
   "ten": "Ghi một lịch hẹn (kèm tự check-in khách trực tiếp hôm nay)",
   "manh": "create = tạo",
   "dong_nghia": [
    "POST /api/v1/appointments/bookings"
   ],
   "nguon": "src/clinicai/services/booking_service.py:474"
  },
  {
   "ma": "build_blockers",
   "loai": "hàm",
   "ten": "Biến vướng mắc thành câu đọc được (mục chan=True là chặn cứng)",
   "manh": "build = dựng · blockers = vật cản",
   "dong_nghia": [
    "vướng mắc",
    "chan"
   ],
   "nguon": "src/clinicai/services/checkout_service.py:1099"
  },
  {
   "ma": "canDungLaiTrang",
   "loai": "hàm",
   "ten": "Quyết tin bảng có đáng dựng lại trang không (man-tu-tai)",
   "manh": "can = có cần · dung_lai = dựng lại · trang",
   "dong_nghia": [
    "MAN_TU_TAI",
    "laManTuTai"
   ],
   "nguon": "src/dashboard/lib/man-tu-tai.ts:46"
  },
  {
   "ma": "cashier_board_service.py · CashierBoardService.board",
   "loai": "hàm",
   "ten": "Dựng bảng quầy thu (ai chờ thu, hoá đơn từng khách)",
   "manh": "cashier = thu ngân · board = bảng · service = tầng luật",
   "dong_nghia": [
    "bảng thu ngân",
    "/cashier/board"
   ],
   "nguon": "src/clinicai/services/cashier_board_service.py:593"
  },
  {
   "ma": "check_in_appointment",
   "loai": "hàm",
   "ten": "Hàm SQL check-in (đổi trạng thái + cấp số, có khoá)",
   "manh": "check_in = khách đến · appointment = lịch hẹn",
   "dong_nghia": [],
   "nguon": "supabase/migrations/20260812000001_ket_qua_nhac_gui_va_so_kham_theo_bac_si.sql:248"
  },
  {
   "ma": "CheckoutService.close",
   "loai": "hàm",
   "ten": "Đóng lượt khám (cho khách về)",
   "manh": "checkout = trả phòng / ra về · close = đóng",
   "dong_nghia": [
    "check-out",
    "đóng lượt",
    "cho khách về",
    "dispatch.checkout"
   ],
   "nguon": "src/clinicai/services/checkout_service.py:723"
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
   "ma": "command_receipt",
   "loai": "bảng",
   "ten": "Biên nhận lệnh (chống ghi hai lần ở lệnh khám/liệu trình)",
   "manh": "command = lệnh · receipt = biên nhận",
   "dong_nghia": [
    "bien_nhan"
   ],
   "nguon": "supabase/migrations/20260911000001_luot_kham_lat_1.sql:311"
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
   "ma": "cong_no",
   "loai": "bảng",
   "ten": "Ghi nợ khi khách về",
   "manh": "cong_no = công nợ",
   "dong_nghia": [
    "ghi nợ",
    "nợ khi về",
    "debt"
   ],
   "nguon": "supabase/migrations/20261002500000_cong_no.sql:18"
  },
  {
   "ma": "CongNoService.ghi",
   "loai": "hàm",
   "ten": "Ghi nợ toàn bộ khoản chưa thu",
   "manh": "cong_no = công nợ · ghi = ghi",
   "dong_nghia": [
    "ghi_no"
   ],
   "nguon": "src/clinicai/services/cong_no_service.py:502"
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
   "ma": "cskh_log",
   "loai": "bảng",
   "ten": "Nhật ký CSKH cũ (hồ sơ đọc ‘ai đã gọi’)",
   "manh": "cskh = chăm sóc khách · log = nhật ký",
   "dong_nghia": [],
   "nguon": "supabase/migrations/20260714000001_baseline_schema.sql:483"
  },
  {
   "ma": "dieu_chinh_theo_kiem_ke",
   "loai": "hàm",
   "ten": "Điều chỉnh tồn theo số đếm đã chốt (ghi ADJUST)",
   "manh": "dieu_chinh = điều chỉnh · theo_kiem_ke = theo kiểm kê",
   "dong_nghia": [
    "ADJUST",
    "hoan_tac_dieu_chinh"
   ],
   "nguon": "src/clinicai/services/kiem_ke_ca_service.py:1023"
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
   "ma": "DisplayBoardService.board",
   "loai": "hàm",
   "ten": "Dữ liệu bảng TV phòng chờ (đã lọc danh tính)",
   "manh": "display = màn chiếu · board = bảng",
   "dong_nghia": [
    "/api/v1/display/queue"
   ],
   "nguon": "src/clinicai/services/display_board_service.py:154"
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
   "ma": "drug_batch",
   "loai": "bảng",
   "ten": "Lô thuốc (tồn từng lô)",
   "manh": "drug = thuốc · batch = lô",
   "dong_nghia": [
    "lô",
    "batch_code = số lô",
    "quantity_on_hand = tồn"
   ],
   "nguon": "supabase/migrations/20260802000001_pharmacy_inventory.sql:57"
  },
  {
   "ma": "drug_catalog",
   "loai": "bảng",
   "ten": "Danh mục thuốc kho",
   "manh": "drug = thuốc · catalog = danh mục",
   "dong_nghia": [
    "danh mục thuốc",
    "thuốc kho"
   ],
   "nguon": "supabase/migrations/20260714000001_baseline_schema.sql:512"
  },
  {
   "ma": "dung_kho_thuoc_khi_thanh_toan",
   "loai": "hàm",
   "ten": "Công tắc: thu tiền thuốc có đòi đủ lô không (mặc định tắt)",
   "manh": "dung_kho = dùng kho · khi_thanh_toan = khi thu",
   "dong_nghia": [
    "CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY"
   ],
   "nguon": "src/clinicai/services/payment_service.py:98"
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
   "ma": "encounter_flow",
   "loai": "bảng",
   "ten": "Luồng của lượt khám (trạng thái đo, đường đi)",
   "manh": "encounter = cuộc khám · flow = luồng; cột vitals_status, route_decision",
   "dong_nghia": [
    "luồng"
   ],
   "nguon": "supabase/migrations/20260911000001_luot_kham_lat_1.sql:33"
  },
  {
   "ma": "enforce_slot_capacity",
   "loai": "hàm",
   "ten": "Trigger chốt sức chứa (ghế mỗi bác sĩ mỗi khung)",
   "manh": "enforce = ép · slot = khung · capacity = sức chứa",
   "dong_nghia": [
    "2+1",
    "Khung giờ đã đầy"
   ],
   "nguon": "supabase/migrations/20260915000017_doi_bac_si_khach_da_co_mat.sql:9"
  },
  {
   "ma": "event_log",
   "loai": "bảng",
   "ten": "Sổ sự kiện / nhật ký thao tác",
   "manh": "event = sự kiện · log = sổ",
   "dong_nghia": [
    "nhật ký",
    "audit"
   ],
   "nguon": "supabase/migrations/20260714000001_baseline_schema.sql:528"
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
   "ma": "expected_revision",
   "loai": "khái niệm",
   "ten": "Số phiên bản mong đợi (chống sửa đè)",
   "manh": "expected = mong đợi · revision = bản sửa",
   "dong_nghia": [
    "STALE_LIEU_TRINH",
    "_dung_ban"
   ],
   "nguon": "src/clinicai/services/lieu_trinh_service.py:957"
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
   "ma": "GET /api/v1/cashier/board",
   "loai": "route",
   "ten": "Đọc bảng quầy thu",
   "manh": "cashier = thu ngân · board = bảng",
   "dong_nghia": [
    "/api/cashier?modes="
   ],
   "nguon": "src/clinicai/api/v1/routers/cashier.py:45"
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
   "ma": "hen_goi_lai",
   "loai": "bảng",
   "ten": "Hẹn gọi lại khách (CSKH tự hẹn)",
   "manh": "hen = hẹn · goi_lai = gọi lại",
   "dong_nghia": [
    "HEN_GOI_LAI"
   ],
   "nguon": "supabase/migrations/20260809000005_trang_thai_cskh_suy_ra.sql:94"
  },
  {
   "ma": "hoa_don_con_no",
   "loai": "hàm",
   "ten": "Hoá đơn dịch vụ CÒN NỢ (chỉ khoản chưa được phủ)",
   "manh": "con_no = còn nợ",
   "dong_nghia": [
    "outstanding bill"
   ],
   "nguon": "src/clinicai/services/bill_service.py:853"
  },
  {
   "ma": "HoaDonMot.tsx",
   "loai": "tệp",
   "ten": "Hoá đơn một khách ở quầy dịch vụ (nút [Tạo bill])",
   "manh": "hoa_don = hoá đơn · mot = một",
   "dong_nghia": [
    "quầy một hoá đơn",
    "quay_thu"
   ],
   "nguon": "src/dashboard/app/(dashboard)/thu-ngan/HoaDonMot.tsx:249"
  },
  {
   "ma": "HoanTacService.mo_lai_luot",
   "loai": "hàm",
   "ten": "Hoàn tác check-out — mở lại lượt",
   "manh": "mo_lai = mở lại · luot = lượt",
   "dong_nghia": [
    "ReopenVisit",
    "visit.reopened"
   ],
   "nguon": "src/clinicai/services/hoan_tac_service.py:1181"
  },
  {
   "ma": "HoanTienService.tao",
   "loai": "hàm",
   "ten": "Tạo khoản hoàn tiền theo dòng hoá đơn",
   "manh": "hoan_tien = hoàn tiền · tao = tạo",
   "dong_nghia": [
    "refund",
    "hoàn tiền"
   ],
   "nguon": "src/clinicai/services/hoan_tien_service.py:91"
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
   "ma": "idempotency_key",
   "loai": "bảng",
   "ten": "Sổ khoá chống gửi hai lần",
   "manh": "idempotency = gửi lại không đổi kết quả · key = khoá",
   "dong_nghia": [
    "Idempotency-Key",
    "khoá thao tác"
   ],
   "nguon": "supabase/migrations/20260714000003_idempotency_key.sql:7"
  },
  {
   "ma": "IdempotencyGuard",
   "loai": "hàm",
   "ten": "Chốt chống gửi hai lần ở router",
   "manh": "guard = người gác",
   "dong_nghia": [
    "tra_khoa_neu_bi_tu_choi"
   ],
   "nguon": "src/clinicai/api/idempotency.py:53"
  },
  {
   "ma": "inventory_txn",
   "loai": "bảng",
   "ten": "Sổ kho thuốc (chỉ thêm)",
   "manh": "inventory = kho · txn = giao dịch",
   "dong_nghia": [
    "sổ kho",
    "RECEIVE = nhập",
    "DISPENSE = giao",
    "ADJUST = điều chỉnh",
    "DISCARD = huỷ"
   ],
   "nguon": "supabase/migrations/20260802000001_pharmacy_inventory.sql:86"
  },
  {
   "ma": "inventory_txn_apply",
   "loai": "hàm",
   "ten": "Trigger cộng dòng sổ vào tồn lô",
   "manh": "apply = áp vào",
   "dong_nghia": [],
   "nguon": "supabase/migrations/20260802000001_pharmacy_inventory.sql:124"
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
   "ma": "kho_thuoc_service.tao_phieu_nhap",
   "loai": "hàm",
   "ten": "Tạo phiếu nhập thuốc nhiều dòng",
   "manh": "kho_thuoc = kho thuốc · tao_phieu_nhap = tạo phiếu nhập",
   "dong_nghia": [
    "phieu-nhap",
    "nhập kho"
   ],
   "nguon": "src/clinicai/services/kho_thuoc_service.py:488"
  },
  {
   "ma": "khoaThaoTac",
   "loai": "hàm",
   "ten": "Sinh khoá chống ghi trùng theo thao tác (màn CSKH)",
   "manh": "khoa = khoá · thao_tac = thao tác",
   "dong_nghia": [
    "xongThaoTac",
    "khoa-mot-lan.ts"
   ],
   "nguon": "src/dashboard/app/(dashboard)/customers/khoa-mot-lan.ts:32"
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
   "ma": "kiem_ke_ca / kiem_ke_ca_dong",
   "loai": "bảng",
   "ten": "Phiếu kiểm kê đầu / cuối ca ở quầy và dòng đếm",
   "manh": "kiem_ke = kiểm kê · ca = ca trực",
   "dong_nghia": [
    "kiểm kê ca",
    "stocktake",
    "G6"
   ],
   "nguon": "supabase/migrations/20261014170000_kiem_ke_ca.sql:17"
  },
  {
   "ma": "kiem_ke_ca_service.chot",
   "loai": "hàm",
   "ten": "Chốt phiếu kiểm kê ca",
   "manh": "kiem_ke_ca = kiểm kê ca · chot = chốt",
   "dong_nghia": [
    "CHOT"
   ],
   "nguon": "src/clinicai/services/kiem_ke_ca_service.py:884"
  },
  {
   "ma": "kiem_quay / QUAY_KHAC_LOAI",
   "loai": "hàm",
   "ten": "Chặn quầy thu sai loại tiền",
   "manh": "kiem = kiểm · quay = quầy",
   "dong_nghia": [
    "quay",
    "quầy dịch vụ / quầy thuốc"
   ],
   "nguon": "src/clinicai/services/payment_service.py:120"
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
   "ma": "lieu_trinh",
   "loai": "bảng",
   "ten": "Liệu trình điều trị nhiều buổi",
   "manh": "lieu_trinh = liệu trình; có cột revision chống sửa đè",
   "dong_nghia": [
    "treatment plan"
   ],
   "nguon": "supabase/migrations/20261008100000_lieu_trinh.sql:39"
  },
  {
   "ma": "lieu_trinh_lich_su",
   "loai": "bảng",
   "ten": "Lịch sử sửa liệu trình (chỉ thêm)",
   "manh": "lich_su = lịch sử",
   "dong_nghia": [],
   "nguon": "supabase/migrations/20261008100000_lieu_trinh.sql:83"
  },
  {
   "ma": "lieu_trinh_tra_truoc",
   "loai": "bảng",
   "ten": "Dòng trả trước liệu trình trong hoá đơn đang thu",
   "manh": "lieu_trinh = liệu trình · tra_truoc = trả trước",
   "dong_nghia": [
    "trả trước k buổi",
    "prepay"
   ],
   "nguon": "supabase/migrations/20261008110000_lieu_trinh_tien.sql:22"
  },
  {
   "ma": "LieuTrinhService.dang_ky",
   "loai": "hàm",
   "ten": "Đăng ký liệu trình (đề xuất → đang làm)",
   "manh": "dang_ky = đăng ký",
   "dong_nghia": [
    "[Đăng ký]",
    "dang-ky"
   ],
   "nguon": "src/clinicai/services/lieu_trinh_service.py:1309"
  },
  {
   "ma": "LieuTrinhTienService.dat_tra_truoc",
   "loai": "hàm",
   "ten": "Đặt số buổi trả trước liệu trình vào hoá đơn",
   "manh": "lieu_trinh_tien = tiền liệu trình · dat = đặt · tra_truoc = trả trước",
   "dong_nghia": [
    "Trả trước k buổi",
    "Trả hết"
   ],
   "nguon": "src/clinicai/services/lieu_trinh_tien.py:291"
  },
  {
   "ma": "LIVE_TABLES",
   "loai": "khái niệm",
   "ten": "Danh sách bảng làm màn dựng lại",
   "manh": "live = sống · tables = bảng",
   "dong_nghia": [
    "RealtimeRefresher"
   ],
   "nguon": "src/dashboard/app/(dashboard)/RealtimeRefresher.tsx:88"
  },
  {
   "ma": "LiveBoardSync",
   "loai": "hàm",
   "ten": "Component dựng lại trang khi vào màn bảng sống",
   "manh": "live board = bảng sống · sync = đồng bộ",
   "dong_nghia": [],
   "nguon": "src/dashboard/app/(dashboard)/LiveBoardSync.tsx:45"
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
   "ma": "LUOTKHAM-15",
   "loai": "khái niệm",
   "ten": "Bước “Đóng lượt” trong checklist lượt khám (work_item)",
   "manh": "CLOSE_NODE = nút đóng",
   "dong_nghia": [
    "CLOSE_NODE",
    "work_item đóng lượt"
   ],
   "nguon": "src/clinicai/services/checkout_service.py:63"
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
   "ma": "LuotKhamService.xep_sau_check_in",
   "loai": "hàm",
   "ten": "Xếp đường đi sau check-in (tư vấn / bác sĩ chính / thẳng dịch vụ)",
   "manh": "xep = xếp · sau_check_in = sau khi khách đến",
   "dong_nghia": [
    "RouteAfterCheckIn",
    "H1"
   ],
   "nguon": "src/clinicai/services/luot_kham_service.py:264"
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
   "ma": "ly_do_khong_hoan_tac",
   "loai": "hàm",
   "ten": "Câu nói vì sao không hoàn tác check-in được",
   "manh": "ly_do = lý do · khong_hoan_tac = không hoàn tác",
   "dong_nghia": [
    "chan_hoan_tac_neu_da_lam",
    "VIEC_DA_LAM_SQL"
   ],
   "nguon": "src/clinicai/services/hoan_tac_check_in.py:43"
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
   "ma": "medicine.dispensed",
   "loai": "sự kiện",
   "ten": "Đã giao thuốc",
   "manh": "medicine = thuốc · dispensed = đã cấp phát",
   "dong_nghia": [
    "pharmacy.dispensed (event_log)"
   ],
   "nguon": "src/clinicai/events/catalogue.py:2145"
  },
  {
   "ma": "mpi_merge_queue",
   "loai": "bảng",
   "ten": "Hàng chờ gộp hồ sơ nghi trùng",
   "manh": "MPI = chỉ mục bệnh nhân chủ · merge = gộp · queue = hàng chờ",
   "dong_nghia": [
    "hàng gộp hồ sơ"
   ],
   "nguon": "supabase/migrations/20260714000001_baseline_schema.sql:600"
  },
  {
   "ma": "MPIService.find_candidates",
   "loai": "hàm",
   "ten": "Tìm hồ sơ có thể trùng (SĐT, CCCD, họ tên + năm sinh)",
   "manh": "find = tìm · candidates = ứng viên",
   "dong_nghia": [
    "check-duplicate"
   ],
   "nguon": "src/clinicai/services/mpi_service.py:85"
  },
  {
   "ma": "nhac_tai_kham",
   "loai": "bảng",
   "ten": "Việc gọi nhắc tái khám (lượt 1 / lượt 2)",
   "manh": "nhac = nhắc · tai_kham = tái khám",
   "dong_nghia": [
    "recall job",
    "recall-jobs",
    "việc gọi nhắc"
   ],
   "nguon": "supabase/migrations/20260807000005_nhac_tai_kham_hai_luot_goi.sql:29"
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
   "ma": "nhap_vao_lo",
   "loai": "hàm",
   "ten": "Nhập số lượng vào một lô (tạo lô nếu chưa có) + ghi RECEIVE",
   "manh": "nhap = nhập · vao_lo = vào lô",
   "dong_nghia": [
    "receive",
    "nhap_lo"
   ],
   "nguon": "src/clinicai/services/pharmacy_service.py:3100"
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
   "ma": "no_khi_ve",
   "loai": "hàm",
   "ten": "Tính khoản nợ khi khách về",
   "manh": "no = nợ · khi_ve = khi về",
   "dong_nghia": [
    "chan_no"
   ],
   "nguon": "src/clinicai/services/cong_no_service.py:277"
  },
  {
   "ma": "noi_chua",
   "loai": "cột",
   "ten": "Nơi chứa lô: KHO hay QUẦY",
   "manh": "noi_chua = nơi chứa",
   "dong_nghia": [
    "tách kho / quầy",
    "G7"
   ],
   "nguon": "src/clinicai/services/pharmacy_service.py:850"
  },
  {
   "ma": "notify_row_change",
   "loai": "hàm",
   "ten": "Trigger báo bảng vừa đổi (pg_notify)",
   "manh": "notify = báo · row_change = dòng đổi",
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
   "ma": "patient",
   "loai": "bảng",
   "ten": "Hồ sơ khách / bệnh nhân",
   "manh": "patient = bệnh nhân; khoá clinic_patient_id",
   "dong_nghia": [
    "khách",
    "bệnh nhân",
    "BN"
   ],
   "nguon": "supabase/migrations/20260714000001_baseline_schema.sql:617"
  },
  {
   "ma": "patient.contacted",
   "loai": "sự kiện",
   "ten": "CSKH đã liên hệ khách",
   "manh": "contacted = đã liên hệ",
   "dong_nghia": [
    "CskhDaLienHe"
   ],
   "nguon": "src/clinicai/events/catalogue.py:2104"
  },
  {
   "ma": "patient_sdt_them",
   "loai": "bảng",
   "ten": "Số điện thoại thêm của khách",
   "manh": "sdt = số điện thoại · them = thêm",
   "dong_nghia": [],
   "nguon": "supabase/migrations/20260815000002_nhieu_so_dien_thoai.sql:20"
  },
  {
   "ma": "PatientService.create_patient",
   "loai": "hàm",
   "ten": "Tạo hồ sơ khách (chặn mềm trùng CCCD/SĐT)",
   "manh": "create = tạo · patient = khách",
   "dong_nghia": [
    "POST /api/v1/patients"
   ],
   "nguon": "src/clinicai/services/patient_service.py:103"
  },
  {
   "ma": "payment",
   "loai": "bảng",
   "ten": "Khoản đã thu (hình chiếu)",
   "manh": "payment = thanh toán",
   "dong_nghia": [
    "thanh toán",
    "khoản thu"
   ],
   "nguon": "supabase/migrations/20260714000001_baseline_schema.sql:744"
  },
  {
   "ma": "payment.service_collected / payment.medicine_collected",
   "loai": "sự kiện",
   "ten": "Đã thu tiền dịch vụ / Đã thu tiền thuốc",
   "manh": "service = dịch vụ · medicine = thuốc · collected = đã thu",
   "dong_nghia": [
    "payment.recorded (tên cũ trước 22/09)",
    "payment.confirmed (event_log)"
   ],
   "nguon": "src/clinicai/events/catalogue.py:2166"
  },
  {
   "ma": "payment_bill_line",
   "loai": "bảng",
   "ten": "Dòng ảnh chụp hoá đơn của một lần thu",
   "manh": "payment = thanh toán · bill = hoá đơn · line = dòng",
   "dong_nghia": [
    "ảnh chụp hoá đơn",
    "dòng hoá đơn"
   ],
   "nguon": "supabase/migrations/20260919000001_tien_thuoc_cp1_hoa_don.sql:85"
  },
  {
   "ma": "payment_cycle",
   "loai": "bảng",
   "ten": "Lần thu (sổ các lần thu)",
   "manh": "payment = thanh toán · cycle = vòng / lần",
   "dong_nghia": [
    "lần thu",
    "phiếu thu",
    "payment_cycle_id",
    "cycle_id",
    "bill"
   ],
   "nguon": "supabase/migrations/20260919000002_tien_thuoc_cp2_payment_cycle.sql:21"
  },
  {
   "ma": "payment_cycle_phan",
   "loai": "bảng",
   "ten": "Phần theo hình thức của lần thu (tiền mặt / chuyển khoản)",
   "manh": "payment_cycle = lần thu · phan = phần",
   "dong_nghia": [
    "chia hình thức",
    "phan"
   ],
   "nguon": "supabase/migrations/20261002300000_thu_nhieu_hinh_thuc.sql:43"
  },
  {
   "ma": "payment_refund",
   "loai": "bảng",
   "ten": "Khoản hoàn tiền",
   "manh": "payment = thanh toán · refund = hoàn tiền",
   "dong_nghia": [
    "hoàn tiền",
    "phiếu hoàn",
    "refund_id"
   ],
   "nguon": "supabase/migrations/20260919000004_tien_thuoc_cp5_hoan_tra.sql:41"
  },
  {
   "ma": "payment_refund_line",
   "loai": "bảng",
   "ten": "Dòng hoàn tiền (trỏ dòng ảnh chụp hoá đơn)",
   "manh": "refund = hoàn · line = dòng",
   "dong_nghia": [],
   "nguon": "supabase/migrations/20260919000004_tien_thuoc_cp5_hoan_tra.sql:79"
  },
  {
   "ma": "PaymentService.hoan_tac",
   "loai": "hàm",
   "ten": "Hoàn tác một lần thu (thu nhầm, trả về chưa thu)",
   "manh": "hoan_tac = làm lại / huỷ thao tác",
   "dong_nghia": [
    "void_payment = huỷ phiếu",
    "huy_cho_xac_minh"
   ],
   "nguon": "src/clinicai/services/payment_service.py:1625"
  },
  {
   "ma": "PaymentService.record_payment",
   "loai": "hàm",
   "ten": "Ghi một lần thu",
   "manh": "record = ghi · payment = thanh toán",
   "dong_nghia": [
    "thu tiền",
    "Tạo bill",
    "Đã nhận đủ"
   ],
   "nguon": "src/clinicai/services/payment_service.py:353"
  },
  {
   "ma": "PENDING_VERIFICATION (CHO_XAC_MINH)",
   "loai": "khái niệm",
   "ten": "Lần chuyển khoản chờ xác minh — chưa tính là đã thu",
   "manh": "pending = đang chờ · verification = xác minh",
   "dong_nghia": [
    "chờ xác minh",
    "Đã nhận tiền",
    "xac_minh_dien_tu"
   ],
   "nguon": "src/clinicai/services/payment_service.py:144"
  },
  {
   "ma": "PharmacyService.cap_phat",
   "loai": "hàm",
   "ten": "Giao thuốc một dòng đơn",
   "manh": "pharmacy = nhà thuốc · cap_phat = cấp phát",
   "dong_nghia": [
    "dispense",
    "giao thuốc",
    "cấp phát",
    "bàn giao"
   ],
   "nguon": "src/clinicai/services/pharmacy_service.py:672"
  },
  {
   "ma": "PharmacyService.phan_lo",
   "loai": "hàm",
   "ten": "Chọn lô cho dòng đơn trước khi thu",
   "manh": "phan_lo = phân lô",
   "dong_nghia": [
    "chọn lô",
    "allocate"
   ],
   "nguon": "src/clinicai/services/pharmacy_service.py:2211"
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
   "ma": "phieu_kho / phieu_kho_dong",
   "loai": "bảng",
   "ten": "Phiếu kho thuốc (nhập, kiểm, chuyển) và dòng phiếu",
   "manh": "phieu = phiếu · kho · dong = dòng",
   "dong_nghia": [
    "phiếu nhập",
    "phiếu kiểm kho"
   ],
   "nguon": "supabase/migrations/20260929960000_kho_kieu_kiotviet.sql:30"
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
   "ma": "POST /api/v1/pharmacy/dispense",
   "loai": "route",
   "ten": "Giao thuốc",
   "manh": "pharmacy = nhà thuốc · dispense = cấp phát",
   "dong_nghia": [
    "/api/pharmacy/dispense",
    "cap_phat"
   ],
   "nguon": "src/clinicai/api/v1/routers/pharmacy.py:1010"
  },
  {
   "ma": "POST /api/v1/reception/checkout",
   "loai": "route",
   "ten": "Đóng lượt (check-out)",
   "manh": "reception = lễ tân · checkout = cho về",
   "dong_nghia": [
    "/api/reception/checkout"
   ],
   "nguon": "src/clinicai/api/v1/routers/dispatch.py:414"
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
   "ma": "prescription.dispensed_qty / dispense_status",
   "loai": "cột",
   "ten": "Số đã giao / trạng thái giao (tính từ số liệu)",
   "manh": "dispensed = đã cấp phát · qty = số lượng",
   "dong_nghia": [
    "đã giao",
    "cấp phát",
    "purchased_qty = số khách mua"
   ],
   "nguon": "src/clinicai/services/pharmacy_service.py:18"
  },
  {
   "ma": "prescription_allocation",
   "loai": "bảng",
   "ten": "Phân lô cho dòng đơn",
   "manh": "allocation = phân bổ",
   "dong_nghia": [
    "phân lô",
    "chọn lô",
    "allocation_id"
   ],
   "nguon": "supabase/migrations/20260919000003_tien_thuoc_cp3_phan_lo_ban.sql:47"
  },
  {
   "ma": "QuayThuNgan.tsx",
   "loai": "tệp",
   "ten": "Thân quầy thu ngân (dùng chung hai quầy)",
   "manh": "quay = quầy · thu_ngan = thu ngân",
   "dong_nghia": [
    "cashier",
    "quầy thu"
   ],
   "nguon": "src/dashboard/app/(dashboard)/thu-ngan/QuayThuNgan.tsx:3"
  },
  {
   "ma": "queue_entry",
   "loai": "bảng",
   "ten": "Chỗ của khách trong hàng chờ (tư vấn/bác sĩ/phòng)",
   "manh": "queue = hàng chờ · entry = một chỗ",
   "dong_nghia": [
    "hàng chờ"
   ],
   "nguon": "supabase/migrations/20260911000001_luot_kham_lat_1.sql:263"
  },
  {
   "ma": "queue_number",
   "loai": "cột",
   "ten": "Số khám riêng theo bác sĩ",
   "manh": "queue = hàng · number = số",
   "dong_nghia": [
    "số khám"
   ],
   "nguon": "supabase/migrations/20260812000001_ket_qua_nhac_gui_va_so_kham_theo_bac_si.sql:248"
  },
  {
   "ma": "RecallJobService",
   "loai": "hàm",
   "ten": "Dịch vụ việc gọi nhắc tái khám (sinh, liệt kê, đóng)",
   "manh": "recall = gọi nhắc quay lại · job = việc",
   "dong_nghia": [
    "nhac_tai_kham",
    "danh_sach",
    "ghi_ket_qua"
   ],
   "nguon": "src/clinicai/services/recall_job_service.py:84"
  },
  {
   "ma": "release_on_booking",
   "loai": "hàm",
   "ten": "Thả chỗ giữ khi đặt xong (cùng giao dịch)",
   "manh": "release = thả · on booking = lúc đặt",
   "dong_nghia": [],
   "nguon": "src/clinicai/services/slot_hold_service.py:221"
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
   "ma": "revision / bill_revision",
   "loai": "khái niệm",
   "ten": "Dấu nội dung hoá đơn (để phát hiện hoá đơn đổi)",
   "manh": "revision = phiên bản",
   "dong_nghia": [
    "billRevision",
    "dấu hoá đơn"
   ],
   "nguon": "src/clinicai/services/bill_service.py:24"
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
   "ma": "sinh_viec_nhac_tai_kham",
   "loai": "hàm",
   "ten": "Hàm SQL sinh việc gọi nhắc tái khám (idempotent)",
   "manh": "sinh = tạo · viec = việc",
   "dong_nghia": [
    "RecallJobService.sinh"
   ],
   "nguon": "supabase/migrations/20261006100000_luot_that_ho_so_cu.sql:40"
  },
  {
   "ma": "SinhHieuService.record_vitals",
   "loai": "hàm",
   "ten": "Ghi một lần đo sinh hiệu",
   "manh": "record = ghi · vitals = sinh hiệu",
   "dong_nghia": [
    "[Đo xong]",
    "sinh-hieu"
   ],
   "nguon": "src/clinicai/services/sinh_hieu_service.py:283"
  },
  {
   "ma": "slot_hold",
   "loai": "bảng",
   "ten": "Giữ chỗ mềm khung giờ",
   "manh": "slot = khung giờ · hold = giữ",
   "dong_nghia": [
    "giữ chỗ",
    "đang có người giữ"
   ],
   "nguon": "supabase/migrations/20260804000008_slot_hold.sql:20"
  },
  {
   "ma": "SlotHoldService",
   "loai": "hàm",
   "ten": "Dịch vụ giữ chỗ mềm",
   "manh": "slot hold = giữ khung",
   "dong_nghia": [
    "slot_hold_service.py"
   ],
   "nguon": "src/clinicai/services/slot_hold_service.py:56"
  },
  {
   "ma": "so_tiep_don",
   "loai": "cột",
   "ten": "Số tiếp đón chung của quầy trong ngày",
   "manh": "so = số · tiep_don = tiếp đón",
   "dong_nghia": [
    "số quầy"
   ],
   "nguon": "supabase/migrations/20260917000009_so_tiep_don_chung.sql:16"
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
   "ma": "TabThuNgan.tsx",
   "loai": "tệp",
   "ten": "Ba tab quầy thu: Chờ thanh toán · Đã thanh toán hôm nay · Lịch sử",
   "manh": "tab · thu_ngan",
   "dong_nghia": [],
   "nguon": "src/dashboard/app/(dashboard)/thu-ngan/TabThuNgan.tsx:15"
  },
  {
   "ma": "tep_ket_qua",
   "loai": "bảng",
   "ten": "Tệp kết quả (ảnh/video/PDF) gửi khách",
   "manh": "tep = tệp · ket_qua = kết quả",
   "dong_nghia": [],
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
   "ma": "tien_thua_giu_lai",
   "loai": "bảng",
   "ten": "Tiền thừa giữ lại (có lý do)",
   "manh": "tien_thua = tiền thừa · giu_lai = giữ lại",
   "dong_nghia": [
    "tiền thừa"
   ],
   "nguon": "supabase/migrations/20261006200003_tien_thua_xu_ly_va_chan_thu_dong_huy.sql:27"
  },
  {
   "ma": "TiepDonService",
   "loai": "hàm",
   "ten": "Dịch vụ danh sách tiếp đón hôm nay",
   "manh": "tiep_don = tiếp đón",
   "dong_nghia": [
    "/api/v1/reception/danh-sach"
   ],
   "nguon": "src/clinicai/services/tiep_don_service.py:403"
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
   "ma": "TRANSITIONS",
   "loai": "khái niệm",
   "ten": "Bảng chuyển trạng thái lịch hẹn (từ đâu → đi đâu, ai, quyền nào)",
   "manh": "transition = bước chuyển",
   "dong_nghia": [
    "máy trạng thái"
   ],
   "nguon": "src/clinicai/services/booking_service.py:324"
  },
  {
   "ma": "tuong_tac_cskh",
   "loai": "bảng",
   "ten": "Sổ chạm khách của CSKH (mỗi cuộc gọi/nhắn một dòng)",
   "manh": "tuong_tac = tương tác · cskh = chăm sóc khách hàng",
   "dong_nghia": [
    "sổ chăm sóc",
    "lần chạm",
    "cuộc gọi"
   ],
   "nguon": "supabase/migrations/20260809000003_so_tuong_tac_cskh.sql:30"
  },
  {
   "ma": "TuongTacCskhService.ghi",
   "loai": "hàm",
   "ten": "Ghi một lần chạm khách",
   "manh": "ghi = ghi sổ",
   "dong_nghia": [
    "POST /api/v1/cskh/tuong-tac"
   ],
   "nguon": "src/clinicai/services/tuong_tac_cskh_service.py:109"
  },
  {
   "ma": "TuongTacCskhService.hoan_tac",
   "loai": "hàm",
   "ten": "Rút lại một lần chạm (không xoá dòng)",
   "manh": "hoan_tac = hoàn tác",
   "dong_nghia": [
    "huy_luc"
   ],
   "nguon": "src/clinicai/services/tuong_tac_cskh_service.py:299"
  },
  {
   "ma": "uq_appointment_patient_slot_live",
   "loai": "khái niệm",
   "ten": "Chỉ mục: một khách một lịch còn sống mỗi mốc giờ",
   "manh": "uq = duy nhất · patient_slot = khách + mốc · live = còn sống",
   "dong_nghia": [],
   "nguon": "supabase/migrations/20260805000007_appointment_patient_slot_unique.sql:67"
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
   "ma": "useGiuCho",
   "loai": "hàm",
   "ten": "Hook vẽ ô người khác đang giữ",
   "manh": "giu_cho = giữ chỗ",
   "dong_nghia": [
    "dung-giu-cho.ts"
   ],
   "nguon": "src/dashboard/app/(dashboard)/appointments/dung-giu-cho.ts:40"
  },
  {
   "ma": "useNgheBang",
   "loai": "hàm",
   "ten": "Hook nghe tin bảng đổi rồi tự tải lại phần mình",
   "manh": "use = hook React · nghe · bang = bảng",
   "dong_nghia": [
    "dung-nghe-bang.ts"
   ],
   "nguon": "src/dashboard/app/(dashboard)/dung-nghe-bang.ts:45"
  },
  {
   "ma": "v_viec_cskh",
   "loai": "khái niệm",
   "ten": "View việc CSKH đang mở (suy ra từ dữ liệu)",
   "manh": "v_ = view · viec = việc",
   "dong_nghia": [
    "CHO_XAC_NHAN",
    "trạng thái CSKH"
   ],
   "nguon": "supabase/migrations/20261015110000_goi_xac_nhan_moi_lich_dat_ho.sql:30"
  },
  {
   "ma": "vat_tu_kho_service.tao_phieu",
   "loai": "hàm",
   "ten": "Lập phiếu kho vật tư (nhập / xuất / kiểm / điều chỉnh…)",
   "manh": "vat_tu_kho = kho vật tư · tao_phieu = tạo phiếu",
   "dong_nghia": [
    "lap_phieu",
    "hoan_phieu = phiếu đảo"
   ],
   "nguon": "src/clinicai/services/vat_tu_kho_service.py:308"
  },
  {
   "ma": "vat_tu_phieu",
   "loai": "bảng",
   "ten": "Phiếu kho vật tư",
   "manh": "vat_tu = vật tư · phieu = phiếu",
   "dong_nghia": [
    "NHAP",
    "XUAT_PHONG = xuất phòng",
    "HOAN = phiếu đảo"
   ],
   "nguon": "supabase/migrations/20261014180000_vat_tu_so_kho.sql:2"
  },
  {
   "ma": "vat_tu_ton",
   "loai": "bảng",
   "ten": "Tồn vật tư theo nơi chứa (kho chung hoặc phòng)",
   "manh": "ton = tồn",
   "dong_nghia": [
    "nơi chứa",
    "room_id rỗng = kho chung"
   ],
   "nguon": "supabase/migrations/20261014180000_vat_tu_so_kho.sql:20"
  },
  {
   "ma": "vat_tu_txn",
   "loai": "bảng",
   "ten": "Sổ vật tư (dòng biến động, chỉ thêm)",
   "manh": "txn = giao dịch",
   "dong_nghia": [
    "sổ vật tư"
   ],
   "nguon": "supabase/migrations/20261014180000_vat_tu_so_kho.sql:31"
  },
  {
   "ma": "vat_tu_txn_cong_ton",
   "loai": "hàm",
   "ten": "Trigger kiểm dòng sổ vật tư rồi cộng vào tồn",
   "manh": "cong_ton = cộng tồn",
   "dong_nghia": [],
   "nguon": "supabase/migrations/20261014180000_vat_tu_so_kho.sql:94"
  },
  {
   "ma": "visit",
   "loai": "bảng",
   "ten": "Lượt khám (sự việc khách đã tới)",
   "manh": "visit = lần tới khám; khoá chính tên visit_id",
   "dong_nghia": [
    "lượt",
    "luot-kham"
   ],
   "nguon": "supabase/migrations/20260714000001_baseline_schema.sql:684"
  },
  {
   "ma": "visit.checked_in",
   "loai": "sự kiện",
   "ten": "Khách đã tới (check-in)",
   "manh": "visit = lượt · checked_in = đã vào",
   "dong_nghia": [
    "KhachDaToi"
   ],
   "nguon": "src/clinicai/events/catalogue.py:1431"
  },
  {
   "ma": "visit.checked_out / visit.left_early",
   "loai": "sự kiện",
   "ten": "Khách đã về / Khách về giữa chừng",
   "manh": "checked_out = đã trả phòng · left_early = về sớm",
   "dong_nghia": [
    "dispatch.checkout",
    "visit.closed_incomplete (event_log)"
   ],
   "nguon": "src/clinicai/events/catalogue.py:1984"
  },
  {
   "ma": "visit.closed_at",
   "loai": "cột",
   "ten": "Mốc khách đã về (check-out)",
   "manh": "closed = đã đóng · at = lúc",
   "dong_nghia": [
    "đóng lượt",
    "đã về"
   ],
   "nguon": "src/clinicai/services/checkout_service.py:826"
  },
  {
   "ma": "visit.status",
   "loai": "cột",
   "ten": "Trạng thái hồ sơ lượt (OPEN, IN_PROGRESS, INCOMPLETE, FINALIZED…)",
   "manh": "status = trạng thái; FINALIZED = bác sĩ đã ký, khoá hồ sơ; INCOMPLETE = khám dở",
   "dong_nghia": [
    "khoá hồ sơ bệnh án",
    "khám dở"
   ],
   "nguon": "src/clinicai/services/checkout_service.py:5"
  },
  {
   "ma": "vital_measurement",
   "loai": "bảng",
   "ten": "Một lần đo sinh hiệu",
   "manh": "vital = sinh hiệu · measurement = lần đo",
   "dong_nghia": [
    "sinh hiệu",
    "vitals"
   ],
   "nguon": "supabase/migrations/20260911000001_luot_kham_lat_1.sql:62"
  },
  {
   "ma": "vitals.recorded",
   "loai": "sự kiện",
   "ten": "Đã đo sinh hiệu",
   "manh": "vitals = sinh hiệu · recorded = đã ghi",
   "dong_nghia": [
    "SinhHieuDaDo"
   ],
   "nguon": "src/clinicai/events/catalogue.py:1505"
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
  },
  {
   "ma": "xu_ly_hanh_trinh",
   "loai": "hàm",
   "ten": "Consumer Hành trình (nghe check-in, sinh hiệu… để xếp khách)",
   "manh": "xu_ly = xử lý · hanh_trinh = hành trình",
   "dong_nghia": [
    "hanh_trinh_luot_kham",
    "HANH_TRINH"
   ],
   "nguon": "src/clinicai/events/consumers/hanh_trinh.py:73"
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
