"use client";

// HÀNH ĐỘNG ỨNG VỚI TRẠNG THÁI ĐANG CHỌN — khối bên phải màn Quản lý khách hàng.
//
// Đặc tả chị Thu qua Quang (09/08/2026): mỗi trạng thái có một bộ nút RIÊNG,
// không phải bốn nút chung cho mọi trạng thái. Bấm xong thì node bên trái tích
// xanh. Bảng dưới đây là bản dịch trực tiếp của đặc tả ấy, từng dòng một.
//
// MỌI NÚT ĐỀU GHI SỔ. Không nút nào chỉ đổi màu trên màn hình: tất cả đi qua
// POST /api/cskh/tuong-tac → `tuong_tac_cskh` + `event_log`, nên node tích xanh
// vì có một dòng THẬT trong database, không vì một biến trong trình duyệt.
// Đó cũng là lý do tích xanh sống qua F5 và người ca sau nhìn thấy.

import { useState } from "react";
import { nhanLoi } from "@/lib/loi-api";
import { khoaThaoTac, xongThaoTac, dinhDanhThaoTac } from "./khoa-mot-lan";
import { useRouter } from "next/navigation";
import { Phone, Upload, Send, Check, X, CalendarPlus } from "lucide-react";
import { LY_DO_HUY, LY_DO_HUY_THU_TU } from "@/lib/ly-do-huy";
import TepKetQua, { type TepKetQuaRow } from "./TepKetQua";

/** Khối hành động ĐỔI THEO VIỆC ĐANG PHẢI LÀM.
 *
 *  TRƯỚC ĐÂY NÓ ĐỨNG YÊN. Bốn nút — Gọi, Ghi kết quả gọi, Zalo nhắc hẹn, Zalo
 *  báo có KQ — hiện y hệt nhau bất kể khách đang ở bước nào. Hai chỗ sai rõ
 *  nhất, và cả hai đều dẫn người trực làm sai việc:
 *
 *    · Bước "Hỏi đơn vị xét nghiệm" bày ra một nút quay số MÁY KHÁCH HÀNG.
 *      Việc ấy là gọi cho phòng xét nghiệm, không phải gọi cho bệnh nhân — gọi
 *      khách lúc này là gọi để nói "em chưa có kết quả".
 *    · Bước "Nhắc bác sĩ duyệt kết quả" cũng vậy: người cần chạm là bác sĩ.
 *
 *  Ngoài ra ô "Việc gì" luôn mở sẵn ở "Gọi nhắc hẹn" nên mọi cuộc gọi vào sổ
 *  dưới cùng một loại, và cột "Tương tác gần nhất" nói sai về việc vừa làm.
 *
 *  `goiKhach = false` KHÔNG ẩn ô ghi kết quả — việc vẫn phải được ghi lại. Nó
 *  chỉ bỏ cái nút quay số nhầm người.
 */
interface HanhDongViec {
  tieuDe: string;
  /** Loại tương tác mở sẵn khi CSKH bấm "Ghi kết quả". */
  loai: string;
  /** Có quay số cho KHÁCH ở bước này không. */
  goiKhach: boolean;
  /** Mẫu tin Zalo hợp với bước này; null = không có mẫu nào đúng. */
  zalo: "NHAC_HEN" | "TRA_KET_QUA" | null;
  /** Câu nói rõ bước này chạm tới ai — hiện khi không phải gọi khách. */
  nhacNho?: string;
  /** Bước này ghi ở khối khác (Nhắc tái khám), không ghi ở đây. */
  oKhoiKhac?: string;
}

const HANH_DONG: Record<string, HanhDongViec> = {
  CHO_XAC_NHAN: {
    tieuDe: "Gọi xác nhận lịch",
    loai: "XAC_NHAN_LICH",
    goiKhach: true,
    zalo: "NHAC_HEN",
  },
  NHAC_HEN_MAI: {
    tieuDe: "Gọi nhắc hẹn ngày mai",
    loai: "NHAC_HEN",
    goiKhach: true,
    zalo: "NHAC_HEN",
  },
  GOI_LAI: {
    tieuDe: "Gọi lại — lần trước chưa gặp",
    loai: "NHAC_HEN",
    goiKhach: true,
    zalo: "NHAC_HEN",
  },
  HOI_LY_DO_HUY: {
    tieuDe: "Gọi hỏi vì sao huỷ",
    loai: "HOI_LY_DO_HUY",
    goiKhach: true,
    zalo: null,
  },
  HEN_GOI_LAI: {
    tieuDe: "Đã hẹn gọi lại hôm nay",
    loai: "HOI_THAM",
    goiKhach: true,
    zalo: null,
  },
  KQ_CHUA_GUI: {
    tieuDe: "Gọi trả kết quả cho khách",
    loai: "TRA_KQ",
    goiKhach: true,
    zalo: "TRA_KET_QUA",
  },
  CHO_KQ_XN: {
    tieuDe: "Hỏi đơn vị xét nghiệm",
    loai: "CHECK_XN",
    goiKhach: false,
    zalo: null,
    nhacNho:
      "Bước này gọi cho ĐƠN VỊ XÉT NGHIỆM, không phải cho khách. Ghi lại kết quả hỏi được.",
  },
  CHO_BAC_SI: {
    tieuDe: "Nhắc bác sĩ duyệt kết quả",
    loai: "KHAC",
    goiKhach: false,
    zalo: null,
    nhacNho:
      "Kết quả đang chờ BÁC SĨ xem. Nhắc bác sĩ rồi ghi lại — chưa gọi khách ở bước này.",
  },
  MOI_TAI_KHAM: {
    tieuDe: "Gọi mời tái khám",
    loai: "HOI_THAM",
    goiKhach: true,
    zalo: null,
    oKhoiKhac: "Hẹn ngày tái khám",
  },
  NHAC_DI_KHAM: {
    tieuDe: "Gọi nhắc đi khám",
    loai: "HOI_THAM",
    goiKhach: true,
    zalo: null,
    oKhoiKhac: "Hẹn ngày tái khám",
  },
};

// Năm trạng thái BỔ SUNG theo đặc tả chị Thu (09/08/2026). Chúng không có
// trong `v_trang_thai_cskh` vì view chỉ suy được việc CÒN PHẢI LÀM; đây là chỗ
// khách ĐANG ĐỨNG, và CSKH chọn tay ở cột trạng thái bên trái.
const HANH_DONG_THEM: Record<string, HanhDongViec> = {
  DA_CHECKIN: {
    tieuDe: "Đã check-in — xem việc tiếp theo",
    // Chưa biết là trả kết quả hay hẹn tái khám: đó chính là việc CSKH phải
    // quyết sau khi xem tình trạng sau khám. Ghi dưới dạng "việc khác" rồi
    // chuyển sang đúng trạng thái ở cột bên trái.
    loai: "KHAC",
    goiKhach: false,
    zalo: null,
    nhacNho:
      "Xem tình trạng sau khám rồi chọn tiếp: “Chờ kết quả xét nghiệm” nếu còn đợi xét nghiệm, hoặc bấm “Hẹn ngày tái khám…” ngay dưới khối này.",
  },
  DA_TRA_KQ: {
    tieuDe: "Đã trả kết quả — có cần tái khám không",
    loai: "KHAC",
    goiKhach: false,
    zalo: null,
    oKhoiKhac: "Hẹn ngày tái khám",
    nhacNho:
      "Kết quả đã trả. Việc còn lại là quyết có hẹn tái khám hay không — hẹn thì bấm “Hẹn ngày tái khám…” ngay dưới khối này — hệ thống tự sinh hai mốc gọi.",
  },
  KHONG_FOLLOW_UP: {
    tieuDe: "Không cần follow up sau thủ thuật",
    loai: "KHAC",
    goiKhach: false,
    zalo: null,
    nhacNho:
      "Ghi lại để ca sau KHÔNG gọi vào ngày mai. Không ghi thì người trực kế tiếp không có cách nào biết, và khách bị gọi thừa.",
  },
  SAU_SINH_1_THANG: {
    tieuDe: "Sau sinh 1 tháng — chúc mừng đầy tháng",
    loai: "HOI_THAM",
    goiKhach: true,
    zalo: null,
    nhacNho:
      "Chúc mừng đầy tháng và mời khám lại sau sinh. Hệ thống KHÔNG tự biết ngày sinh thật (chỉ có ngày dự sinh), nên trạng thái này do CSKH chọn.",
  },
  SAU_THU_THUAT_1_NGAY: {
    tieuDe: "Sau thủ thuật 1 ngày — hỏi thăm",
    loai: "HOI_THAM",
    goiKhach: true,
    zalo: null,
    nhacNho:
      "Gọi hỏi thăm tình trạng sau thủ thuật. Trạng thái này do CSKH chọn — dịch vụ thủ thuật đang tắt nên máy không suy ra được.",
  },
};

/** Tiêu đề của khối hành động, theo trạng thái đang chọn.
 *
 *  Xuất ra để `CustomersView` dựng tiêu đề từ CÙNG một bảng với các nút bên
 *  dưới. Hai bảng cho cùng một khái niệm là hai bảng sẽ lệch — và ở đây lệch
 *  nghĩa là tiêu đề nói một việc còn nút làm một việc khác. */
export function tieuDeHanhDong(ma: string | null | undefined): string {
  if (!ma) return MAC_DINH.tieuDe;
  return (HANH_DONG[ma] ?? HANH_DONG_THEM[ma] ?? MAC_DINH).tieuDe;
}

/** MÃ TRẠNG THÁI THẬT SỰ CÓ BỘ NÚT ở khối này.
 *
 *  Xuất ra để `?viec=` trên đường dẫn được KIỂM trước khi dùng. Chuông thông
 *  báo và ba màn khác đều dựng đường dẫn tới `/customers`, và một mã gõ sai
 *  (hoặc một mã cũ còn nằm trong `thong_bao.duong_dan` sinh từ tuần trước) sẽ
 *  mở màn ở một trạng thái không có nút nào. Thà bỏ qua tham số ấy và chạy theo
 *  việc gấp nhất, còn hơn mở ra một khối trống. */
export function coBoNut(ma: string | null | undefined): boolean {
  if (!ma) return false;
  return ma in HANH_DONG || ma in HANH_DONG_THEM;
}

const MAC_DINH: HanhDongViec = {
  tieuDe: "Gọi khách & ghi tương tác",
  loai: "NHAC_HEN",
  goiKhach: true,
  zalo: "NHAC_HEN",
};

/** Lý do huỷ có sẵn — LẤY TỪ DANH MỤC CHUNG, không chép tay nữa.
 *
 *  Ba dòng cũ ở đây là BẢN THỨ TƯ của cùng một danh mục (sau CHECK trong SQL,
 *  `LY_DO_HUY` ở `booking_service.py`, và `lib/ly-do-huy.ts`), và nó đã lệch
 *  sẵn: chữ khác hẳn ba bản kia, lại thiếu `DAT_TRUNG` thêm ngày 10/08. Chép
 *  một danh mục là hẹn ngày mỗi màn nói một kiểu về cùng một lần huỷ — đúng
 *  chuyện đã làm nút "Bỏ lịch này" trả 500 hôm nay.
 *
 *  Bỏ `DAT_TRUNG` khỏi ô này: nó là lý do của người dọn lịch trùng, không phải
 *  câu khách nói qua điện thoại. Ô này ghi lời khách. */
const LY_DO_HUY_SAN: string[] = LY_DO_HUY_THU_TU.filter(
  (ma) => ma !== "DAT_TRUNG" && ma !== "KHAC",
).map((ma) => LY_DO_HUY[ma]!);

interface Props {
  trangThai: string | null;
  clinicPatientId: string;
  // `patientCode` ĐÃ BỎ cùng nút "Đặt lịch tái khám" của khối DA_CHECKIN — nó
  // chỉ tồn tại để dựng `/appointments?bn=…`. Giữ một prop không ai đọc là để
  // lần sau có người tưởng khối này còn cần mã bệnh nhân.
  appointmentId: string | null;
  phone: string | null;
  tepKetQua: TepKetQuaRow[];
  /** Trạng thái này đã có dấu vết xử lý chưa — để nút nói "làm lại". */
  daXong: boolean;
  /** Ghi chú đang gõ — do `CustomersView` giữ, dùng chung với cột giữa. */
  ghiChu: string;
  onGhiChu: (v: string) => void;
}

export default function HanhDongTrangThai({
  trangThai,
  clinicPatientId,
  appointmentId,
  phone,
  tepKetQua,
  daXong,
  ghiChu,
  onGhiChu,
}: Props) {
  const router = useRouter();
  const [dangLuu, setDangLuu] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [xong, setXong] = useState(false);
  // GHI CHÚ DO CHA GIỮ, không phải state riêng của khối này.
  //
  // Từ 10/08/2026 nút ghi của nhiều trạng thái nằm ở CỘT GIỮA (`MOT_CHAM`), còn
  // ô gõ ghi chú thì ở ĐÂY. Hai cột phải đọc cùng một chuỗi, nếu không thì gõ
  // xong bấm bên kia là ghi chú rơi mất — và người dùng không có cách nào biết
  // nó rơi.
  const [lyDo, setLyDo] = useState("");
  const [moLyDoSan, setMoLyDoSan] = useState(false);
  const [moTaiKham, setMoTaiKham] = useState(false);
  const [ngayTaiKham, setNgayTaiKham] = useState("");
  const [lyDoTaiKham, setLyDoTaiKham] = useState("");
  const [daHenTaiKham, setDaHenTaiKham] = useState(false);
  const [moHen, setMoHen] = useState(false);
  const [ngayHen, setNgayHen] = useState("");
  /** "" = chỉ hẹn tới ngày. Không mặc định 00:00 — xem chú thích ô nhập. */
  const [gioHen, setGioHen] = useState("");
  const [lyDoHen, setLyDoHen] = useState("");
  const [daHen, setDaHen] = useState(false);

  /** Ghi một lần chạm. `loai`/`ket_qua` phải nằm trong bộ từ backend canh
   *  (LOAI_HOP_LE, KET_QUA_HOP_LE ở tuong_tac_cskh_service.py). */
  async function ghi(
    ma: string,
    loai: string,
    ketQua: string,
    noiDung?: string,
  ) {
    // MỐC QUẦY có luật riêng ở backend: kênh phải là TRUC_TIEP và kết quả phải
    // là GHI_NHAN (chúng là việc XẢY RA, không phải cuộc gọi). Gửi sai là 422.
    const mocQuay = ["CHECK_IN", "CHECK_OUT", "THANH_TOAN", "MUA_THUOC"].includes(
      loai,
    );
    setDangLuu(ma);
    setLoi(null);
    // Khoá theo THAO TÁC, không theo lần bấm: bấm đúp hay gửi lại sau khi mạng
    // rớt đều mang cùng khoá, nên backend nhận ra và không ghi thêm dòng thứ
    // hai. Xem khoa-mot-lan.ts để biết vì sao không sinh khoá mới mỗi lần bấm.
    const thaoTac = dinhDanhThaoTac(clinicPatientId, appointmentId, loai, ma, ketQua);
    try {
      const res = await fetch("/api/cskh/tuong-tac", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": khoaThaoTac(thaoTac),
        },
        body: JSON.stringify({
          clinic_patient_id: clinicPatientId,
          // LUÔN GẮN LỊCH HẸN KHI CÓ.
          //
          // Chỗ này từng chỉ gắn cho năm loại của `CAN_LICH_HEN` — tập hợp
          // backend BẮT BUỘC phải có lịch — và gửi null cho mọi loại khác. Đúng
          // theo nghĩa "không vi phạm ràng buộc", nhưng nó vứt đi thông tin lượt
          // khám: `CHECK_XN`, `KHAC`, `TRA_KQ`, `HOI_THAM` vào sổ mà không biết
          // thuộc lượt nào.
          //
          // Hệ quả lộ ra ngày 10/08/2026, khi timeline bắt đầu lọc sổ theo lượt:
          // bấm mấy nút ấy thì ghi thật nhưng không tích xanh, vì chính màn hình
          // loại dòng vừa ghi ra. Và ô "Lịch sử các lần khám" cũng không gom
          // được chúng vào đúng lượt.
          //
          // Backend chỉ ĐÒI với năm loại kia; nó NHẬN với mọi loại và tự kiểm
          // lịch hẹn có đúng của khách này không.
          appointment_id: appointmentId,
          loai,
          // "BỎ QUA" LÀ KHÔNG GỌI AI CẢ, nên kênh phải là KHONG_LIEN_HE.
          //
          // Chỗ này từng gửi cứng "GOI" cho mọi thứ không phải mốc quầy, kể cả
          // nút "Ghi nhận: không cần gọi" (ket_qua = BO_QUA). Cả backend lẫn
          // ràng buộc `tuong_tac_bo_qua_thi_khong_lien_he` của database đều đòi
          // BO_QUA ⟺ KHONG_LIEN_HE, nên nút ấy CHƯA TỪNG ghi được lần nào: bấm
          // là hiện dòng đỏ "'Bỏ qua' phải đi cùng 'không liên hệ'", và bước
          // trên timeline không bao giờ tích xanh.
          //
          // Ghi một dòng "đã gọi" cho một việc mà cả ý nghĩa của nó là KHÔNG
          // gọi thì còn tệ hơn: nó vào sổ chăm sóc như một cuộc gọi chưa từng có.
          kenh: mocQuay
            ? "TRUC_TIEP"
            : ketQua === "BO_QUA"
              ? "KHONG_LIEN_HE"
              : "GOI",
          ket_qua: mocQuay ? "GHI_NHAN" : ketQua,
          noi_dung: (noiDung ?? ghiChu).trim() || null,
          // MÃ TRẠNG THÁI mà thao tác này đóng lại. Đây là thứ timeline dò để
          // tích xanh — không dò theo `loai` nữa, vì nhiều trạng thái dùng
          // chung một loại (xem migration 20260810000002).
          trang_thai_ma: trangThai,
        }),
      });
      if (!res.ok) {
        const d = (await res.json().catch(() => null)) as {
          error?: string;
          message?: string;
        } | null;
        // MÁY CHỦ TỪ CHỐI (4xx) ⇒ BỎ KHOÁ. Nó từ chối vì một điều kiện nghiệp vụ
        // — "chưa gửi tệp kết quả cho khách", "mốc tại quầy mới ghi kết quả này"
        // — nghĩa là CHẮC CHẮN chưa ghi gì. Người trực sẽ sửa rồi bấm lại, và
        // lần ấy là một thao tác MỚI. Giữ khoá thì lần bấm lại nhận 409 "đang
        // được xử lý", và câu giải thích thật biến mất — đúng thứ nhìn thấy trên
        // staging 13/08: 422, 422, rồi 409, 409 mãi trong 5 phút.
        //
        // 5xx VÀ LỖI MẠNG THÌ GIỮ. Lúc đó không ai biết máy chủ đã ghi tới đâu,
        // và chính ca ấy là lý do khoá này tồn tại: ngắt mạng ở mốc 90ms sau khi
        // bấm thì màn hình báo lỗi trong khi dữ liệu ĐÃ vào.
        if (res.status >= 400 && res.status < 500) xongThaoTac(thaoTac);
        setLoi(nhanLoi(d, "Không ghi được."));
        return false;
      }
      // THÀNH CÔNG ⇒ bỏ khoá. Lần bấm sau là một thao tác MỚI và phải được ghi
      // thật; giữ khoá lại thì thao tác thứ hai bị nuốt vì tưởng là gửi trùng.
      xongThaoTac(thaoTac);
      setXong(true);
      onGhiChu("");
      router.refresh();
      return true;
    } finally {
      setDangLuu(null);
    }
  }

  /** HẸN NGÀY TÁI KHÁM — bác sĩ dặn "tháng sau quay lại", CSKH gõ vào đây.
   *
   *  ĐƯỜNG NÀY TỪNG MẤT HẲN ĐƯỜNG VÀO. `POST /api/cskh/nhac-tai-kham` sống từ
   *  lâu và sinh ra HAI mốc gọi (trước 7 ngày mời đặt lịch, trước 1 ngày nhắc
   *  đi khám). Nhưng khối `NhacTaiKham` bị gỡ khỏi màn 09/08/2026, và từ đó
   *  KHÔNG nút nào gọi tới — trong khi SÁU chỗ trên chính giao diện này vẫn bảo
   *  người dùng *"gõ ngày ở khối Nhắc tái khám"*. Người trực đi tìm một khối
   *  không còn tồn tại.
   *
   *  Đo khi nghiệm thu 10/08/2026: `grep NhacTaiKham` trong thư mục customers
   *  chỉ ra ba dòng `import type` — không một chỗ nào dựng component.
   *
   *  Vì sao phải có: việc nhắc tái khám TỰ SINH chỉ đọc được lời dặn nằm trong
   *  `soap_plan.tai_kham.ngay` của một phiếu khám ĐÃ CHỐT. Khách nói qua điện
   *  thoại thì không có phiếu nào để đọc — câu ấy nằm trong đầu người trực và
   *  mất khi đổi ca. Chính chú thích của route đã viết đúng như vậy.
   *
   *  Đặt cạnh "Hẹn gọi lại ngày…" vì cùng hình dạng (ngày + lý do + gửi) và
   *  cùng tính chất: việc người trực tự đặt cho mình, không suy ra được. */
  async function henTaiKham() {
    setDangLuu("taikham");
    setLoi(null);
    try {
      const res = await fetch("/api/cskh/nhac-tai-kham", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          clinic_patient_id: clinicPatientId,
          ngay_tai_kham: ngayTaiKham,
          ly_do: lyDoTaiKham.trim() || null,
        }),
      });
      if (!res.ok) {
        const d = (await res.json().catch(() => null)) as {
          error?: string;
          message?: string;
        } | null;
        setLoi(nhanLoi(d, "Không hẹn được ngày tái khám."));
        return;
      }
      setDaHenTaiKham(true);
      setMoTaiKham(false);
      router.refresh();
    } finally {
      setDangLuu(null);
    }
  }

  /** HẸN GỌI LẠI NGÀY… — chỗ đựng việc hệ thống chưa suy được.
   *
   *  Nó vốn nằm trong khối "Ghi một tương tác khác" đã bỏ. Giữ lại vì đây là
   *  đường DUY NHẤT sinh ra việc `hen_goi_lai`, tức trạng thái "Hẹn gọi lại
   *  sau" trên timeline. Bỏ theo luôn là lặng lẽ gỡ một trạng thái trong đặc
   *  tả của chị Thu. */
  async function henGoiLai() {
    setDangLuu("hen");
    setLoi(null);
    try {
      const res = await fetch("/api/cskh/hen-goi-lai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          clinic_patient_id: clinicPatientId,
          ngay_goi: ngayHen,
          // Chuỗi rỗng KHÔNG được gửi thành "" — backend khai `time | None`,
          // và "" không parse ra giờ. null nói đúng "chỉ hẹn tới ngày".
          gio_goi: gioHen || null,
          ly_do: lyDoHen.trim(),
        }),
      });
      if (!res.ok) {
        const d = (await res.json().catch(() => null)) as {
          error?: string;
          message?: string;
        } | null;
        setLoi(nhanLoi(d, "Không hẹn được."));
        return;
      }
      router.refresh();
      setDaHen(true);
      setMoHen(false);
      setLyDoHen("");
    } finally {
      setDangLuu(null);
    }
  }

  const soDienThoai = phone ? (
    // "hiện số của khách ở đây luôn" — CSKH không phải quay về cột hồ sơ để
    // đọc số rồi quay lại đây bấm.
    <a
      href={`tel:${phone}`}
      className="block rounded-xl border border-brand-300 bg-white px-3 py-2 text-center font-mono text-sm font-bold text-brand-700 hover:bg-brand-50"
    >
      📞 {phone}
    </a>
  ) : (
    <p className="rounded-xl border border-line bg-surface-muted px-3 py-2 text-center text-xs text-ink-muted">
      Khách chưa có số điện thoại
    </p>
  );

  function NutChinh({
    ma,
    nhan,
    onClick,
    Icon = Check,
  }: {
    ma: string;
    nhan: string;
    onClick: () => void;
    Icon?: typeof Check;
  }) {
    return (
      <button
        type="button"
        onClick={onClick}
        disabled={dangLuu !== null}
        className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl bg-brand-600 py-2 px-3 text-xs font-bold text-white hover:bg-brand-700 disabled:opacity-50"
      >
        <Icon size={14} />
        {dangLuu === ma ? "Đang ghi…" : nhan}
      </button>
    );
  }

  function NutPhu({
    ma,
    nhan,
    onClick,
    Icon,
  }: {
    ma: string;
    nhan: string;
    onClick: () => void;
    Icon?: typeof Check;
  }) {
    return (
      <button
        type="button"
        onClick={onClick}
        disabled={dangLuu !== null}
        className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-line bg-surface py-2 px-3 text-xs font-semibold text-ink-soft hover:bg-surface-muted disabled:opacity-50"
      >
        {Icon ? <Icon size={13} /> : null}
        {dangLuu === ma ? "Đang ghi…" : nhan}
      </button>
    );
  }

  const oGhiChu = (
    <input
      value={ghiChu}
      onChange={(e) => onGhiChu(e.target.value)}
      placeholder="Ghi chú (không bắt buộc)"
      className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-label text-ink"
    />
  );

  /** Dòng nói rõ nút ghi nằm ở đâu, cho những trạng thái đã một-chạm.
   *
   *  Không có nó thì khối bên phải chỉ còn số điện thoại và một ô gõ, và người
   *  mới vào ca sẽ đứng đó tìm nút "lưu". */
  const nhacBamCotGiua = (
    <p className="rounded-lg bg-surface-muted px-2 py-1.5 text-label leading-snug text-ink-soft">
      Gọi xong thì bấm nút của trạng thái này ở <b>cột giữa</b> — bấm là ghi
      luôn. Ghi chú gõ ở trên sẽ đi kèm.
    </p>
  );

  /** `loai` tương tác của trạng thái đang mở, lấy từ CHÍNH bảng sinh ra tiêu
   *  đề. Gõ cứng `loai` trong từng case là cách hai thứ trôi khỏi nhau: tiêu đề
   *  nói "Gọi mời tái khám" mà sổ ghi loại "nhắc hẹn". */
  const loaiCuaTrangThai =
    (trangThai && (HANH_DONG[trangThai] ?? HANH_DONG_THEM[trangThai])?.loai) ||
    "NHAC_HEN";

  function than() {
    switch (trangThai) {
      // ── TRƯỚC KHÁM ────────────────────────────────────────────────────────
      // HAI TRẠNG THÁI NÀY KHÔNG CÒN NÚT GHI Ở ĐÂY.
      //
      // Quang 10/08/2026: *"ấn vào 1 trong 2 trạng thái chờ xác nhận lịch trước
      // 7 ngày và cần nhắc hẹn thì bên ô action bỏ ô đã xác nhận cuộc gọi vì
      // bên kia ấn là được rồi mà"*. Đúng: nút ở cột giữa nay CHÍNH LÀ hành
      // động (xem `MOT_CHAM`), nên để thêm một nút ghi ở đây là mời người trực
      // ghi hai dòng sổ cho một cuộc gọi.
      //
      // CÒN LẠI ĐÚNG HAI THỨ, và cả hai đều KHÔNG có ở cột giữa:
      //   · số điện thoại để bấm gọi
      //   · ô ghi chú — nó đi THEO cú bấm ở cột giữa (`ghiChu` do
      //     `CustomersView` giữ và truyền cho cả hai cột), nên gõ ở đây rồi bấm
      //     bên kia là ghi chú vào đúng dòng ấy. Bỏ luôn ô này thì không còn
      //     đường nào ghi lại "khách nói đang họp, gọi lại sau 5h".
      case "CHO_XAC_NHAN":
      case "NHAC_HEN_MAI":
        return (
          <>
            {soDienThoai}
            {oGhiChu}
            {nhacBamCotGiua}
          </>
        );

      // ── SAU KHÁM ──────────────────────────────────────────────────────────
      // KHỐI NÀY CHỈ CÒN SỐ ĐIỆN THOẠI.
      //
      // Quang 10/08/2026: *"bỏ nút checkin đi vì đã tích hợp bên trạng thái
      // rồi, chỉ hiện số điện thoại của khách thôi, bỏ các nút trả kết quả
      // khám, tái khám đi vì đã có bên kia rồi"*.
      //
      // Ba nút vừa bỏ, và vì sao bỏ là đúng:
      //
      //   "Check-in cho khách"      trùng node "Đã check-in" ở cột giữa — nay
      //                             node ấy ghi thẳng `CHECK_IN` (`MOT_CHAM`),
      //                             đi đúng máy trạng thái y như nút này.
      //   "Trả kết quả xét nghiệm"  và
      //   "Đặt lịch tái khám"       cả hai gửi `CHECK_OUT`, tức ĐÓNG LƯỢT KHÁM
      //                             — cùng việc với nút "Checkout" ở khối "Kết
      //                             thúc lượt khám", nhưng mang hai cái tên
      //                             nghe như hai bước khác nhau. Ba nút, một
      //                             hành vi, ba tên: đó là cách người trực đóng
      //                             lượt mà không biết mình vừa đóng.
      //
      // Việc "sau khám thì làm gì tiếp" nay đọc ở đúng chỗ của nó: sơ đồ nhánh
      // SAU KHÁM ở cột giữa, và ba nút Kết thúc lượt khám ở cuối cột ấy.
      case "DA_CHECKIN":
        return (
          <>
            {soDienThoai}
            {oGhiChu}
            {nhacBamCotGiua}
          </>
        );

      case "CHO_KQ_XN":
        return (
          <>
            <p className="text-label font-semibold leading-snug text-ink">
              Check với đơn vị xét nghiệm: đã có kết quả hay chưa?
            </p>
            {oGhiChu}
            <div className="flex gap-2">
              <NutPhu
                ma="co"
                nhan="Có rồi"
                Icon={Check}
                onClick={() =>
                  void ghi(
                    "co",
                    "CHECK_XN",
                    "DA_LIEN_HE",
                    ghiChu.trim() || "Đơn vị XN báo ĐÃ có kết quả",
                  )
                }
              />
              <NutPhu
                ma="chua"
                nhan="Chưa có"
                Icon={X}
                onClick={() =>
                  void ghi(
                    "chua",
                    "CHECK_XN",
                    "DA_LIEN_HE",
                    ghiChu.trim() || "Đơn vị XN báo CHƯA có kết quả",
                  )
                }
              />
            </div>
            <p className="text-label leading-snug text-ink-faint">
              Cả hai đều ghi lại kèm thời điểm — “chưa có” cũng là một lần đã
              hỏi, và ca sau cần biết đã hỏi lúc nào.
            </p>
          </>
        );

      // BA MÃ NÀY VIEW SINH RA NHƯNG `than()` KHÔNG CÓ CASE — tới 10/08/2026
      // chúng rơi thẳng vào `default:` ("Chọn một trạng thái ở cột giữa…"),
      // trong khi `HANH_DONG` vẫn cho chúng một tiêu đề đàng hoàng. Tiêu đề nói
      // "Đã hẹn gọi lại hôm nay", thân màn không có một cái nút nào.
      //
      //   HEN_GOI_LAI  — CSKH tự hẹn với mình, tới ngày thì gọi
      //   MOI_TAI_KHAM — lượt gọi 1 của `nhac_tai_kham`
      //   NHAC_DI_KHAM — lượt gọi 2
      //
      // Cả ba đều là "gọi khách rồi ghi kết quả", đúng bộ nút của `GOI_LAI`.
      // `loai` lấy từ chính `HANH_DONG` để hai bảng không nói hai kiểu.
      case "HEN_GOI_LAI":
      case "MOI_TAI_KHAM":
      case "NHAC_DI_KHAM":
      case "GOI_LAI":
        // BA KẾT QUẢ NÀY TRƯỚC ĐÂY KHÔNG GHI ĐƯỢC TỪ MÀN NÀY.
        //
        // `CHUA_NGHE_MAY`, `KHONG_LIEN_LAC_DUOC`, `HEN_GOI_LAI` có trong bộ từ
        // của backend từ lâu, và chính cái node trên timeline mang tên "KNM /
        // KLLD / Hẹn GLS" — nhưng mọi nút ở đây chỉ gửi `DA_LIEN_HE`, nên sổ
        // chăm sóc ghi "đã liên hệ được" cho cả những lần khách không bắt máy.
        //
        // Hàng gộp bên cột giữa ghi thẳng ba kết quả này chỉ bằng một cú bấm.
        // Ở ĐÂY GIỮ LẠI CHÚNG vì đây là chỗ DUY NHẤT có ô ghi chú: "khách nói
        // đang họp, gọi lại sau 5h" là thứ chỉ ghi được từ khối này.
        return (
          <>
            <p className="text-label leading-snug text-ink-soft">
              Gọi xong thì bấm đúng chuyện đã xảy ra. Cần ghi thêm nội dung thì
              gõ vào ô dưới trước khi bấm.
            </p>
            {soDienThoai}
            {oGhiChu}
            <NutChinh
              ma="gl"
              nhan="Đã liên hệ được"
              Icon={Phone}
              onClick={() => void ghi("gl", loaiCuaTrangThai, "DA_LIEN_HE")}
            />
            <div className="flex flex-wrap gap-2">
              <NutPhu
                ma="knm"
                nhan="Không nghe máy"
                onClick={() => void ghi("knm", loaiCuaTrangThai, "CHUA_NGHE_MAY")}
              />
              <NutPhu
                ma="klld"
                nhan="Không liên lạc được"
                onClick={() =>
                  void ghi("klld", loaiCuaTrangThai, "KHONG_LIEN_LAC_DUOC")
                }
              />
              <NutPhu
                ma="hgl"
                nhan="Hẹn gọi lại sau"
                onClick={() => void ghi("hgl", loaiCuaTrangThai, "HEN_GOI_LAI")}
              />
            </div>
          </>
        );

      case "CHO_BAC_SI":
      case "KQ_CHUA_GUI":
        return (
          <>
            <div className="rounded-xl border border-line bg-surface-muted/60 p-2">
              <div className="mb-1 flex items-center gap-1.5 text-label font-bold text-ink">
                <Upload size={13} /> Kết quả siêu âm / xét nghiệm
              </div>
              <TepKetQua
                clinicPatientId={clinicPatientId}
                appointmentId={appointmentId}
                items={tepKetQua}
              />
            </div>

            {trangThai === "CHO_BAC_SI" ? (
              <>
                <p className="text-label leading-snug text-warning">
                  Kết quả đang chờ BÁC SĨ duyệt. Hỏi bác sĩ trước, chưa gọi
                  khách ở bước này.
                </p>
                {oGhiChu}
                <NutChinh
                  ma="bs"
                  nhan="Đã hỏi bác sĩ"
                  onClick={() =>
                    void ghi(
                      "bs",
                      "KHAC",
                      "DA_LIEN_HE",
                      ghiChu.trim() || "Đã hỏi bác sĩ về kết quả",
                    )
                  }
                />
              </>
            ) : (
              <>
                {oGhiChu}
                <NutChinh
                  ma="gui"
                  nhan="Đã gửi kết quả cho bệnh nhân"
                  Icon={Send}
                  onClick={() =>
                    void ghi(
                      "gui",
                      "TRA_KQ",
                      "DA_LIEN_HE",
                      ghiChu.trim() || "Đã gửi kết quả cho bệnh nhân",
                    )
                  }
                />
                {/* NÓI THẬT VỀ THỨ CHƯA XÂY. Tải lên đã chạy được; GỬI TỰ ĐỘNG
                    thì chưa: Zalo ZNS chỉ gửi được template CHỮ đã duyệt, không
                    đính kèm được tệp hay video. Nên nút trên ghi nhận rằng CSKH
                    đã gửi (qua Zalo cá nhân/Messenger), chứ hệ thống không tự
                    gửi. Nhập nhèm chỗ này là để người trực tin rằng khách đã
                    nhận video trong khi chưa ai gửi. */}
                <p className="rounded-lg border border-dashed border-line px-2 py-1.5 text-label leading-snug text-ink-muted">
                  <b>Đang xây dựng:</b> hệ thống chưa TỰ gửi được ảnh/video cho
                  khách — Zalo ZNS chỉ gửi template chữ. Hiện CSKH gửi bằng kênh
                  của mình rồi bấm nút trên để ghi nhận.
                </p>
              </>
            )}
          </>
        );

      case "DA_TRA_KQ":
        return (
          <>
            {/* HAI NÚT NÀY TỪNG GHI `loai = "KHAC"`, VÀ ĐÓ LÀ LỖI.
                `dangO("DA_TRA_KQ")` ở VungLamViecKhach dò đúng một thứ: có
                tương tác `loai='TRA_KQ'` với `ket_qua='DA_LIEN_HE'` hay không.
                Ghi "KHAC" nên bấm xong node vẫn không sáng lên "đang ở đây" —
                nó chỉ tích xanh nhờ `trang_thai_ma`, tức là đúng một nửa.
                Nhánh KQ_CHUA_GUI của view cũng đóng theo `loai='TRA_KQ'`, nên
                ghi sai loại còn để trạng thái "đã có kết quả, chưa gửi" treo
                lại dù kết quả đã trả xong. */}
            <p className="text-label leading-snug text-ink-soft">
              Kết quả đã trả. Còn một việc: có hẹn tái khám hay không.
            </p>
            <div className="flex gap-2">
              <NutPhu
                ma="cotk"
                nhan="Cần tái khám"
                Icon={CalendarPlus}
                onClick={() =>
                  void ghi(
                    "cotk",
                    "TRA_KQ",
                    "DA_LIEN_HE",
                    "Sau trả kết quả: CẦN hẹn tái khám",
                  )
                }
              />
              <NutPhu
                ma="khongtk"
                nhan="Không cần tái khám"
                Icon={X}
                onClick={() =>
                  void ghi(
                    "khongtk",
                    "TRA_KQ",
                    "DA_LIEN_HE",
                    "Sau trả kết quả: KHÔNG cần tái khám",
                  )
                }
              />
            </div>
            <p className="text-label leading-snug text-ink-faint">
              Chọn “cần tái khám” xong thì bấm <b>Hẹn ngày tái khám…</b> ở dưới{" "}
              để hệ thống tự sinh hai mốc gọi.
            </p>
          </>
        );

      case "HOI_LY_DO_HUY":
        return (
          <>
            <p className="text-label leading-snug text-ink-soft">
              Gọi lại hỏi lý do huỷ (trong vòng 1–14 ngày kể từ lúc huỷ).
            </p>
            {soDienThoai}
            <div className="space-y-1">
              <textarea
                rows={2}
                value={lyDo}
                onChange={(e) => setLyDo(e.target.value)}
                placeholder="Lý do khách huỷ lịch…"
                className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-label text-ink"
              />
              {/* Ô ĐIỀN + TOGGLE BA LÝ DO SẴN, đúng hình dạng đặc tả: người gõ
                  được câu riêng, mà ba trường hợp hay gặp thì bấm một cái là
                  xong — và ba câu ấy giống nhau giữa mọi người, nên về sau đếm
                  được. */}
              <button
                type="button"
                onClick={() => setMoLyDoSan((v) => !v)}
                aria-expanded={moLyDoSan}
                className="text-label font-semibold text-brand-700 hover:underline"
              >
                {moLyDoSan ? "▾ Ẩn lý do có sẵn" : "▸ Chọn lý do có sẵn"}
              </button>
              {moLyDoSan && (
                <ul className="space-y-1">
                  {LY_DO_HUY_SAN.map((l) => (
                    <li key={l}>
                      <button
                        type="button"
                        onClick={() => {
                          setLyDo(l);
                          setMoLyDoSan(false);
                        }}
                        className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-left text-label leading-snug text-ink-soft hover:border-brand-400 hover:bg-brand-50"
                      >
                        {l}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <NutChinh
              ma="huy"
              nhan="Ghi lý do huỷ"
              onClick={() =>
                void ghi("huy", "HOI_LY_DO_HUY", "DA_LIEN_HE", lyDo)
              }
            />
          </>
        );

      case "KHONG_FOLLOW_UP":
        return (
          <>
            <p className="text-label leading-snug text-ink-soft">
              Không cần gọi vào ngày hôm sau. Ghi lại để ca sau khỏi gọi thừa.
            </p>
            {oGhiChu}
            <NutChinh
              ma="kfu"
              nhan="Ghi nhận: không cần gọi"
              onClick={() =>
                void ghi(
                  "kfu",
                  "KHAC",
                  "BO_QUA",
                  ghiChu.trim() || "Không cần follow up sau thủ thuật",
                )
              }
            />
          </>
        );

      case "SAU_SINH_1_THANG":
        return (
          <>
            <p className="text-label leading-snug text-ink-soft">
              Chúc mừng đầy tháng, mời khám lại sau sinh.
            </p>
            {soDienThoai}
            {oGhiChu}
            <NutChinh
              ma="ss"
              nhan="Đã gọi chúc mừng đầy tháng"
              Icon={Phone}
              onClick={() => void ghi("ss", "HOI_THAM", "DA_LIEN_HE")}
            />
          </>
        );

      case "SAU_THU_THUAT_1_NGAY":
        return (
          <>
            <p className="text-label leading-snug text-ink-soft">
              Gọi hỏi thăm tình trạng sau thủ thuật.
            </p>
            {soDienThoai}
            {oGhiChu}
            <NutChinh
              ma="stt"
              nhan="Đã gọi hỏi thăm"
              Icon={Phone}
              onClick={() => void ghi("stt", "HOI_THAM", "DA_LIEN_HE")}
            />
          </>
        );

      default:
        // MÃ LẠ PHẢI NÓI RA TÊN NÓ.
        //
        // `trangThai` là chữ tự do đi từ `v_trang_thai_cskh` (và từ `?viec=`
        // trên đường dẫn). Khi một mã có ở view mà chưa có case ở đây, màn hiện
        // câu "Chọn một trạng thái ở cột giữa" — nghe như người dùng chưa bấm
        // gì, trong khi họ vừa bấm xong. Đó là cách ba mã HEN_GOI_LAI /
        // MOI_TAI_KHAM / NHAC_DI_KHAM nằm chết ở đây suốt mà không ai báo lỗi.
        return trangThai ? (
          <p className="text-label leading-snug text-warning">
            Chưa có bộ nút cho trạng thái <b>{trangThai}</b>. Ghi lại mã này rồi
            báo — không phải lỗi thao tác của bạn.
          </p>
        ) : (
          <p className="text-label leading-snug text-ink-muted">
            Chọn một trạng thái ở cột giữa để thấy việc phải làm và các nút
            tương ứng.
          </p>
        );
    }
  }

  return (
    <div className="space-y-2">
      {(xong || daXong) && (
        <p className="flex items-center gap-1.5 rounded-lg bg-success-bg px-2 py-1.5 text-label font-semibold text-success">
          <Check size={13} /> Đã ghi nhận — trạng thái này đã tích xanh ở cột
          giữa. Bấm lại nếu cần làm thêm lần nữa.
        </p>
      )}
      {than()}
      {loi && <p className="text-label text-danger">{loi}</p>}

      {/* HẸN NGÀY TÁI KHÁM — luôn có, cùng lý do với khối hẹn gọi lại bên dưới:
          đây là việc người trực tự đặt, không trạng thái nào suy ra được. */}
      <div className="border-t border-line pt-2">
        {daHenTaiKham ? (
          <p className="rounded-lg bg-success-bg px-2 py-1.5 text-label text-success">
            Đã hẹn ngày tái khám. Hệ thống tự sinh hai mốc gọi: trước 7 ngày mời
            đặt lịch, trước 1 ngày nhắc đi khám — chúng hiện ở khối “Nhắc tái
            khám” cột giữa khi tới hạn.
          </p>
        ) : moTaiKham ? (
          <div className="space-y-1.5">
            <input
              type="date"
              value={ngayTaiKham}
              onChange={(e) => setNgayTaiKham(e.target.value)}
              aria-label="Ngày khách quay lại khám"
              className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-label text-ink"
            />
            <input
              value={lyDoTaiKham}
              onChange={(e) => setLyDoTaiKham(e.target.value)}
              placeholder="Bác sĩ dặn gì (không bắt buộc)"
              className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-label text-ink"
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => void henTaiKham()}
                disabled={dangLuu !== null || !ngayTaiKham}
                className="flex-1 rounded-lg bg-brand-600 py-1.5 text-label font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
              >
                {dangLuu === "taikham" ? "Đang hẹn…" : "Hẹn ngày tái khám"}
              </button>
              <button
                type="button"
                onClick={() => setMoTaiKham(false)}
                className="rounded-lg border border-line px-3 py-1.5 text-label font-medium text-ink-soft hover:bg-surface-muted"
              >
                Thôi
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setMoTaiKham(true)}
            className="w-full rounded-lg border border-line py-1.5 text-label font-semibold text-ink-soft hover:bg-surface-muted"
          >
            Hẹn ngày tái khám…
          </button>
        )}
      </div>

      {/* Hẹn gọi lại — luôn có, không phụ thuộc trạng thái đang chọn. */}
      <div className="border-t border-line pt-2">
        {daHen ? (
          <p className="rounded-lg bg-success-bg px-2 py-1.5 text-label text-success">
            Đã hẹn gọi lại. Khách hiện ở danh sách vào đúng ngày đó, và lời hẹn
            nằm sẵn trong chuông thông báo tới khi có người xử lý.
          </p>
        ) : moHen ? (
          <div className="space-y-1.5">
            {/* NGÀY VÀ GIỜ, không chỉ ngày (Quang 10/08/2026: *"khách nói đang
                họp, gọi lại sau 5h… thêm 1 nút là gọi lại vào lúc ... giờ"*).
                Với một lời hẹn như thế thì cả-ngày-hôm-nay là câu trả lời sai:
                gọi lúc 9h sáng vẫn đúng "ngày", và vẫn làm phiền đúng người
                mình vừa hứa sẽ không làm phiền.

                Giờ để TRỐNG được — nghĩa là chỉ hẹn tới ngày. Ép chọn giờ thì
                người ta gõ bừa một con số, và con số bừa đó đi thẳng vào việc
                của ca sau. */}
            <div className="flex gap-1.5">
              <input
                type="date"
                value={ngayHen}
                onChange={(e) => setNgayHen(e.target.value)}
                aria-label="Ngày gọi lại"
                className="min-w-0 flex-1 rounded-lg border border-line bg-surface px-2 py-1.5 text-label text-ink"
              />
              <input
                type="time"
                value={gioHen}
                onChange={(e) => setGioHen(e.target.value)}
                aria-label="Giờ gọi lại (bỏ trống nếu chỉ hẹn ngày)"
                title="Bỏ trống nếu chỉ hẹn tới ngày"
                className="w-23 shrink-0 rounded-lg border border-line bg-surface px-2 py-1.5 text-label text-ink"
              />
            </div>
            <input
              value={lyDoHen}
              onChange={(e) => setLyDoHen(e.target.value)}
              placeholder="Gọi lại để làm gì"
              className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-label text-ink"
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => void henGoiLai()}
                disabled={dangLuu !== null || !ngayHen || !lyDoHen.trim()}
                className="flex-1 rounded-lg bg-brand-600 py-1.5 text-label font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
              >
                {dangLuu === "hen" ? "Đang hẹn…" : "Hẹn"}
              </button>
              <button
                type="button"
                onClick={() => setMoHen(false)}
                className="rounded-lg border border-line px-3 py-1.5 text-label font-medium text-ink-soft hover:bg-surface-muted"
              >
                Thôi
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setMoHen(true)}
            className="w-full rounded-lg border border-line py-1.5 text-label font-semibold text-ink-soft hover:bg-surface-muted"
          >
            Hẹn gọi lại ngày…
          </button>
        )}
      </div>
    </div>
  );
}
