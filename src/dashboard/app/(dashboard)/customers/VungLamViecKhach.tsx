"use client";

// TRẠNG THÁI KHÁCH HÀNG — và việc phải làm ứng với từng trạng thái.
//
// ĐÂY LÀ BẢN VIẾT LẠI THEO ĐẶC TẢ CỦA CHỊ THU (Quang họp 09/08/2026). Bản trước
// là một CHUỖI BƯỚC tuyến tính: đặt lịch → gọi xác nhận → nhắc hẹn → check-in →
// hỏi xét nghiệm → trả kết quả → check-out → thanh toán → mua thuốc. Nó sai mô
// hình chứ không sai chi tiết:
//
//   · Một khách KHÔNG đi qua chín bước theo thứ tự. Họ Ở TRONG một trạng thái,
//     và trạng thái ấy quyết định CSKH phải nhấc máy lên làm gì.
//   · Chuỗi tuyến tính không diễn tả được những nhánh có thật: huỷ lịch, không
//     nghe máy, kết quả về nhưng bác sĩ chưa duyệt, sau sinh, sau thủ thuật.
//   · Và nó không nói được "khách này đang ở đâu" — thứ duy nhất người trực ca
//     cần biết khi mở màn hình lên.
//
// Nay: một DANH SÁCH TRẠNG THÁI chia hai giai đoạn (trước khám / sau khám). Bấm
// vào một trạng thái thì khối hành động bên phải đổi tiêu đề VÀ đổi nút theo
// đúng việc của trạng thái ấy — xem HANH_DONG trong HanhDongTrangThai.tsx.
//
// TRẠNG THÁI NÀO MÁY TỰ BIẾT, TRẠNG THÁI NÀO NGƯỜI TỰ CHỌN.
//
// Bảy trạng thái đầu suy được từ dữ liệu thật (view `v_trang_thai_cskh`, trạng
// thái lịch hẹn, sổ tương tác) — chúng tự sáng lên. Ba trạng thái cuối (không
// follow-up sau thủ thuật, sau sinh 1 tháng, sau thủ thuật 1 ngày) KHÔNG có
// nguồn dữ liệu: hệ thống không có ngày sinh con thật (`edd_date` là ngày DỰ
// sinh, lệch hai tuần), và các dịch vụ thủ thuật đang tắt. Chúng vẫn có mặt để
// CSKH tự chọn và ghi lại — một nút người bấm thì có việc THẬT, một tab tự sinh
// từ ngày dự sinh thì có việc SAI mà không ai biết là sai cho tới lúc gọi nhầm.
//
// Mọi thao tác đều ghi sổ: `tuong_tac_cskh` + `event_log` (xem
// TuongTacCskhService.ghi).

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Phone, CircleDashed } from "lucide-react";
import type { DongLichSu } from "./so-tuong-tac";

/** Một trạng thái khách có thể đang ở, kèm việc CSKH phải làm khi ở đó. */
interface TrangThai {
  ma: string;
  /** Tên trạng thái — phần IN ĐẬM trong đặc tả. */
  ten: string;
  /** Việc phải làm — phần sau mũi tên trong đặc tả. */
  viec: string;
  /** Không suy được từ dữ liệu; CSKH tự chọn khi biết. */
  tuChon?: boolean;
}

const TRUOC_KHAM: TrangThai[] = [
  {
    ma: "CHO_XAC_NHAN",
    ten: "Chờ xác nhận lịch trước 7 ngày",
    viec: "Gọi điện xác nhận lịch với khách",
  },
  {
    ma: "NHAC_HEN_MAI",
    ten: "Cần nhắc hẹn",
    viec: "Gọi nhắc hẹn — khách đã xác nhận, có lịch khám ngày mai",
  },
];

/** Lớp CSS của một nút lối ra — cùng hình dạng với nút "Làm bước này" trên
 *  timeline, đúng yêu cầu của Quang ("giống mấy cái nút làm bước này"). Tách ra
 *  hàm để hai chỗ không trôi khỏi nhau. */
function nutLoiRa(chon: boolean, xong: boolean, dang: boolean): string {
  const nen = "rounded-full px-2.5 py-0.5 text-[11px]";
  if (chon) return `${nen} bg-brand-700 font-semibold text-white`;
  if (xong)
    return `${nen} border border-line font-medium text-ink-soft hover:bg-surface-muted`;
  if (dang)
    return `${nen} bg-brand-600 font-semibold text-white hover:bg-brand-700`;
  return `${nen} border border-brand-300 font-medium text-brand-700 hover:bg-brand-50`;
}

/** MỘT TRẠNG THÁI, NHIỀU LỐI RA — gom vào một hàng.
 *
 *  Quang 10/08/2026: *"loại trạng thái nào cùng 1 trạng thái to hơn thì ở cùng
 *  dòng, chọn 1 trong số chúng trong hàng thì coi như done trạng thái"*.
 *
 *  `GOI_LAI` là ví dụ rõ nhất và là lý do khối này ra đời. Nó vốn nằm giữa danh
 *  sách dọc dưới cái tên "KNM / KLLD / Hẹn GLS" — ba chữ viết tắt trong một
 *  dòng, và người đọc không có cách nào biết chúng là BA LỐI RA của cùng một
 *  cuộc gọi chứ không phải ba bước nối tiếp nhau.
 *
 *  VÀ CHÚNG CHƯA TỪNG GHI ĐƯỢC. Ba mã `CHUA_NGHE_MAY`, `KHONG_LIEN_LAC_DUOC`,
 *  `HEN_GOI_LAI` có trong bộ từ của backend từ lâu, nhưng không nút nào trên
 *  màn này gửi chúng — mọi nút đều ghi `DA_LIEN_HE` hoặc `GHI_NHAN`. Nên cái
 *  nhãn "KNM / KLLD / Hẹn GLS" mô tả một việc màn hình không làm được. */
interface LoiRa {
  /** `ket_qua` gửi lên backend. Phải nằm trong `KET_QUA_HOP_LE`. */
  ketQua: string;
  /** Tên đầy đủ — cũng chính là tên trạng thái sau khi bấm. */
  ten: string;
}

/** MỘT HÀNG GỘP: một dấu tick, nhiều lối ra.
 *
 *  Khác `Node` ở đúng một điểm, và đó là điểm Quang muốn: các lối ra nằm NGANG
 *  HÀNG nhau chứ không xếp dọc, vì chúng không nối tiếp nhau — chọn một cái là
 *  xong cả hàng.
 *
 *  `loiRa` rỗng thì hàng chỉ có một nút "Làm bước này", giống hệt `Node` — dùng
 *  cho những trạng thái chưa (hoặc không) tách nhánh, như "Huỷ lịch".
 *
 *  BẤM LÀ GHI THẬT (Quang chốt 10/08/2026: *"tôi muốn bạn viết code cho tôi để
 *  nó là sự kiện thật nhé, click vào 3 cái đó thì trạng thái của nó là tên nó
 *  luôn"*). Bản đầu tôi làm bấm-là-CHỌN để người dùng gõ ghi chú trước khi
 *  đóng; Quang bác, và lý do đúng: ba lối ra này không cần ghi chú để có nghĩa
 *  — "không nghe máy" đã là toàn bộ nội dung của lần chạm ấy. Bắt qua thêm một
 *  khối bên phải chỉ để bấm nút thứ hai là hai thao tác cho một sự thật.
 *
 *  Ghi chú vẫn thêm được sau, ở khối hành động bên phải.
 *
 *  Sau khi ghi, TÊN HÀNG đổi thành tên lối ra vừa bấm — "trạng thái của nó là
 *  tên nó luôn". Xem `tenHienTai`.
 *
 *  Ở CẤP MODULE, không lồng trong `VungLamViecKhach`: component tạo ra trong
 *  lúc render thì React coi mỗi lần vẽ là một loại component khác và dựng lại
 *  từ đầu, mất sạch state bên trong. Nên `dang`/`xong`/`chon`/`lan` tính sẵn ở
 *  chỗ gọi rồi truyền vào, thay vì đọc closure. */
function HangGop({
  ma,
  ten,
  viec,
  loiRa,
  dang,
  xong,
  chon,
  lan,
  onLamViec,
  onGhi,
  dangGhi,
  loi,
}: {
  ma: string;
  ten: string;
  viec: string;
  loiRa: LoiRa[];
  dang: boolean;
  xong: boolean;
  chon: boolean;
  lan?: DongLichSu;
  onLamViec: (ma: string, ketQua?: string) => void;
  /** Ghi THẲNG một lối ra. Không truyền = hàng chỉ chọn, không ghi. */
  onGhi?: (ma: string, ketQua: string) => void;
  /** `ket_qua` đang ghi dở — để nút nói "Đang ghi…" thay vì im lặng. */
  dangGhi?: string | null;
  loi?: string | null;
}) {
  // TÊN HÀNG THEO ĐÚNG CÁI VỪA BẤM.
  //
  // Ghi xong "Không nghe máy" thì hàng phải đọc là "Không nghe máy", không phải
  // cái tên nhóm "Gọi lại — không gặp được khách". Đó là điều Quang muốn: trạng
  // thái mang đúng tên của nó, để người đọc không phải suy ra từ tên nhóm cộng
  // với một dòng chữ nhỏ bên dưới.
  const daChon = lan?.ket_qua
    ? loiRa.find((lr) => lr.ketQua === lan.ket_qua)
    : undefined;
  const tenHienTai = daChon ? daChon.ten : ten;

  return (
    <div className="flex gap-3 rounded-xl border border-line p-2.5">
      <span
        className={`flex size-7 shrink-0 items-center justify-center rounded-full border-2 ${
          xong
            ? "border-success bg-success-bg text-success"
            : dang
              ? "border-brand-600 bg-brand-50 text-brand-700"
              : "border-line bg-surface-muted text-ink-faint"
        }`}
      >
        {xong ? (
          <Check className="size-4" strokeWidth={3} />
        ) : dang ? (
          <Phone className="size-3.5" />
        ) : (
          <CircleDashed className="size-3.5" />
        )}
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`text-sm ${
              xong
                ? "font-medium text-ink"
                : dang
                  ? "font-semibold text-brand-700"
                  : "text-ink-soft"
            }`}
          >
            {tenHienTai}
          </span>
          {daChon && (
            <span className="rounded-full bg-surface-sunken px-1.5 py-0.5 text-[10px] font-medium text-ink-muted">
              {ten}
            </span>
          )}
          {dang && !xong && (
            <span className="rounded-full bg-brand-100 px-2 py-0.5 text-[10px] font-bold text-brand-800">
              đang ở đây
            </span>
          )}
        </div>

        <p className="mt-0.5 text-[11px] leading-snug text-ink-muted">{viec}</p>

        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {loiRa.length === 0 ? (
            <button
              type="button"
              onClick={() => onLamViec(ma)}
              aria-pressed={chon}
              className={nutLoiRa(chon, xong, dang)}
            >
              {chon ? "Đang làm" : xong ? "Làm lại" : "Làm bước này"}
            </button>
          ) : (
            loiRa.map((lr) => {
              // "Đang bật" = lối ra ĐÃ GHI, không phải lối ra đang chọn. Sau
              // khi bấm, nút sáng lên vì nó là sự thật đã ghi vào sổ.
              const daGhiNay = lan?.ket_qua === lr.ketQua;
              return (
                <button
                  key={lr.ketQua}
                  type="button"
                  disabled={Boolean(dangGhi)}
                  onClick={() =>
                    onGhi ? onGhi(ma, lr.ketQua) : onLamViec(ma, lr.ketQua)
                  }
                  aria-pressed={daGhiNay}
                  className={`${nutLoiRa(daGhiNay, xong && !daGhiNay, dang)} disabled:opacity-50`}
                >
                  {dangGhi === lr.ketQua ? "Đang ghi…" : lr.ten}
                </button>
              );
            })
          )}
        </div>
        {loi && <p className="mt-1 text-[11px] text-danger">{loi}</p>}

        {lan && (
          <p className="mt-1 text-[11px] leading-snug text-ink-soft">
            <span className="font-mono text-ink-muted">
              {gio(lan.xay_ra_luc)}
            </span>
            {lan.ket_qua && ` · ${NHAN_KET_QUA[lan.ket_qua] ?? lan.ket_qua}`}
            {lan.nhan_vien && ` · ${lan.nhan_vien}`}
          </p>
        )}
      </div>
    </div>
  );
}

/** VIẾT ĐẦY ĐỦ, KHÔNG VIẾT TẮT (Quang 10/08/2026).
 *
 *  "KNM / KLLD / Hẹn GLS" là tiếng lóng của người đã biết. Người mới vào ca đọc
 *  ba chữ ấy không ra nghĩa, và cái tooltip giải nghĩa chỉ hiện khi rê chuột —
 *  tức là chỉ giúp người đã nghi ngờ mình không hiểu. Tên đầy đủ thì ai đọc
 *  cũng hiểu, kể cả khi nó nằm trong sổ chăm sóc sáu tháng sau. */
const KHONG_GAP_DUOC: LoiRa[] = [
  { ketQua: "CHUA_NGHE_MAY", ten: "Không nghe máy" },
  { ketQua: "KHONG_LIEN_LAC_DUOC", ten: "Không liên lạc được" },
  { ketQua: "HEN_GOI_LAI", ten: "Hẹn gọi lại sau" },
];

const SAU_KHAM: TrangThai[] = [
  {
    ma: "DA_CHECKIN",
    ten: "Đã check-in",
    viec: "Xem tình trạng sau khám để biết việc tiếp: trả kết quả xét nghiệm hay đặt lịch tái khám",
  },
  {
    ma: "CHO_KQ_XN",
    ten: "Chờ kết quả xét nghiệm",
    viec: "Hỏi đơn vị xét nghiệm xem kết quả về chưa",
  },
  {
    ma: "CHO_BAC_SI",
    ten: "Có kết quả, chờ phản hồi chuyên môn",
    viec: "Hỏi bác sĩ trước khi trả kết quả cho khách",
  },
  {
    ma: "KQ_CHUA_GUI",
    ten: "Đã có kết quả, chưa gửi",
    viec: "Tải kết quả lên rồi gửi cho khách (ảnh siêu âm, phiếu xét nghiệm — video đang xây dựng)",
  },
  {
    ma: "DA_TRA_KQ",
    ten: "Đã gọi trả kết quả xét nghiệm",
    viec: "Cân nhắc có cần hẹn lịch tái khám sau đó không",
  },
  {
    ma: "KHONG_FOLLOW_UP",
    ten: "Không cần follow up sau thủ thuật",
    viec: "Không gọi vào ngày hôm sau — ghi lại để ca sau khỏi gọi",
    tuChon: true,
  },
  {
    ma: "SAU_SINH_1_THANG",
    ten: "Sau sinh 1 tháng",
    viec: "Chúc mừng đầy tháng, mời khám lại sau sinh",
    tuChon: true,
  },
  {
    ma: "SAU_THU_THUAT_1_NGAY",
    ten: "Sau thủ thuật 1 ngày",
    viec: "Gọi hỏi thăm tình trạng",
    tuChon: true,
  },
];

/* KHỐI "MỐC TẠI QUẦY" ĐÃ BỎ — Quang chốt 09/08/2026, giữ lại đúng "Phản hồi
 * của khách" trong vùng dưới.
 *
 * NGƯỢC VỚI YÊU CẦU 08/08 (*"khách checkout, khách đã thanh toán, khách đã mua
 * thuốc… tất cả là các nút và thao tác được thật"*), nên ghi lại ở đây thay vì
 * xoá lặng lẽ. Bốn nút ấy KHÔNG phải trang trí: chúng POST
 * `/api/cskh/tuong-tac` và check-in mở lượt khám vào hàng đợi tiếp nhận thật.
 *
 * Đường khác vẫn còn: node "Đã check-in" trên timeline, và màn Quầy tiếp nhận.
 */

function gio(iso: string): string {
  return new Date(iso).toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

const NHAN_KET_QUA: Record<string, string> = {
  DA_LIEN_HE: "đã liên hệ được",
  CHUA_NGHE_MAY: "không nghe máy",
  KHONG_LIEN_LAC_DUOC: "không liên lạc được",
  HEN_GOI_LAI: "khách hẹn gọi lại",
  CAN_BAC_SI: "cần bác sĩ xem xét",
  TU_CHOI: "khách từ chối",
  BO_QUA: "bỏ qua",
  GHI_NHAN: "đã ghi nhận",
};

/** ĐƯỜNG LÙI cho những dòng ghi TRƯỚC migration 20260810000002 — hồi ấy chưa
 *  có cột `trang_thai_ma`, nên chỉ suy được theo `loai`. Bảng này cố ý KHÔNG
 *  liệt kê các trạng thái dùng chung loại `KHAC`: đoán ở đó là tích xanh nhầm
 *  node, tệ hơn là không tích. */
const SUY_THEO_LOAI_CU: Record<string, string[]> = {
  CHO_XAC_NHAN: ["XAC_NHAN_LICH"],
  CHO_KQ_XN: ["CHECK_XN"],
  HOI_LY_DO_HUY: ["HOI_LY_DO_HUY"],
};

export interface MocLich {
  /** Lịch hẹn đại diện đang xem. */
  id: string | null;
  status: string | null;
  slot_start: string | null;
  created_at: string | null;
  cancelled_at: string | null;
}

export default function VungLamViecKhach({
  tenKhach,
  clinicPatientId,
  lich,
  lichSu,
  trangThaiHienTai,
  dangChon,
  onLamViec,
  children,
}: {
  tenKhach: string;
  clinicPatientId: string;
  lich: MocLich;
  lichSu: DongLichSu[];
  /** Trạng thái gấp nhất do `v_trang_thai_cskh` suy ra. */
  trangThaiHienTai?: string | null;
  /** Trạng thái CSKH đang chọn làm việc (null = chưa chọn). */
  dangChon?: string | null;
  /** Bấm một trạng thái → khối hành động bên phải đổi theo nó. `ketQua` chỉ
   *  truyền khi bấm một lối ra cụ thể trong hàng gộp — hôm nay không hàng nào
   *  dùng tới, vì lối ra ghi thẳng. Giữ tham số cho nhóm sau. */
  onLamViec: (maTrangThai: string, ketQua?: string) => void;
  /** Khối gắn thêm bên dưới — nay chỉ còn "Phản hồi của khách". */
  children?: React.ReactNode;
}) {

  const router = useRouter();
  const [dangGhiLoiRa, setDangGhiLoiRa] = useState<string | null>(null);
  const [loiGhiLoiRa, setLoiGhiLoiRa] = useState<string | null>(null);

  /** Ghi THẲNG một lối ra vào sổ chăm sóc — không qua khối bên phải.
   *
   *  `loai: "NHAC_HEN"` khớp `HANH_DONG.GOI_LAI` ở HanhDongTrangThai, để hai
   *  đường ghi cùng một loại tương tác. NHAC_HEN nằm trong `CAN_LICH_HEN` ở
   *  backend nên `appointment_id` là BẮT BUỘC; thiếu nó thì backend trả 422
   *  "Việc này phải gắn với một lịch hẹn cụ thể".
   *
   *  `trang_thai_ma` là thứ timeline dò để tích xanh — không dò theo `loai`,
   *  vì nhiều trạng thái dùng chung một loại (migration 20260810000002). */
  async function ghiLoiRa(ma: string, ketQua: string) {
    if (!lich.id) {
      setLoiGhiLoiRa("Khách chưa có lịch hẹn nào để gắn lần gọi này.");
      return;
    }
    setDangGhiLoiRa(ketQua);
    setLoiGhiLoiRa(null);
    const res = await fetch("/api/cskh/tuong-tac", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clinic_patient_id: clinicPatientId,
        appointment_id: lich.id,
        loai: "NHAC_HEN",
        kenh: "GOI",
        ket_qua: ketQua,
        trang_thai_ma: ma,
      }),
    });
    setDangGhiLoiRa(null);
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as {
        error?: string;
        message?: string;
      } | null;
      setLoiGhiLoiRa(d?.message ?? d?.error ?? `Không ghi được (lỗi ${res.status}).`);
      return;
    }
    router.refresh();
  }

  const daHuy = lich.status === "CANCELLED";
  const daCheckin =
    lich.status === "CHECKED_IN" || lich.status === "COMPLETED";

  function cacLan(loai: string): DongLichSu[] {
    return lichSu.filter((d) => d.loai === loai);
  }

  /** Trạng thái này đã xong chưa, kể cả khi chưa có dòng sổ nào.
   *
   *  "Đã check-in" xong khi lịch hẹn đã COMPLETED — lễ tân có thể đóng lượt
   *  khám từ màn khác, và node ở đây phải nói đúng chuyện đó. */
  function xongTheoLich(ma: string): boolean {
    if (ma === "DA_CHECKIN") return lich.status === "COMPLETED";
    return false;
  }

  /** Trạng thái này có ĐANG đúng với khách không — suy từ dữ liệu thật. */
  function dangO(ma: string): boolean {
    if (ma === trangThaiHienTai) return true;
    if (ma === "DA_CHECKIN") return daCheckin;
    if (ma === "HOI_LY_DO_HUY") return daHuy;
    if (ma === "DA_TRA_KQ") {
      return cacLan("TRA_KQ").some((d) => d.ket_qua === "DA_LIEN_HE");
    }
    return false;
  }

  /** Lần chạm gần nhất ĐÓNG trạng thái này — cơ sở để node tích xanh.
   *
   *  Dò theo `trang_thai_ma`, cột ghi thẳng mã trạng thái mà thao tác xử lý.
   *  Trước đây dò theo `loai` và nó sai ở cả hai chiều: ba trạng thái cùng ghi
   *  loại `KHAC` nên bấm cái này tích xanh cái kia, còn "không cần follow up"
   *  thì không tích được cái nào. */
  function lanCuoi(ma: string): DongLichSu | undefined {
    const theoMa = lichSu.find((d) => d.trang_thai_ma === ma);
    if (theoMa) return theoMa;
    const loai = SUY_THEO_LOAI_CU[ma];
    return loai ? lichSu.find((d) => loai.includes(d.loai)) : undefined;
  }


  /** MỘT NODE TRÊN TIMELINE.
   *
   *  Quang 09/08/2026: *"tôi không muốn bạn làm dạng ô như này đâu, vẫn là
   *  timeline node như trước khi sửa cơ"*. Nên hình dạng quay lại đúng bản cũ —
   *  vòng tròn viền dày nối nhau bằng một sợi dọc — chỉ có NỘI DUNG là khác:
   *  node bây giờ là TRẠNG THÁI khách đang ở, không phải bước thứ mấy của một
   *  hành trình. */
  function Node({
    tt,
    cuoi,
  }: {
    tt: TrangThai;
    cuoi: boolean;
  }) {
    const dang = dangO(tt.ma);
    const chon = dangChon === tt.ma;
    const lan = lanCuoi(tt.ma);
    const xong = Boolean(lan) || xongTheoLich(tt.ma);

    return (
      <li className="flex gap-3">
        <div className="flex flex-col items-center">
          <span
            className={`flex size-7 shrink-0 items-center justify-center rounded-full border-2 ${
              xong
                ? "border-success bg-success-bg text-success"
                : dang
                  ? "border-brand-600 bg-brand-50 text-brand-700"
                  : "border-line bg-surface-muted text-ink-faint"
            }`}
          >
            {xong ? (
              <Check className="size-4" strokeWidth={3} />
            ) : dang ? (
              <Phone className="size-3.5" />
            ) : (
              <CircleDashed className="size-3.5" />
            )}
          </span>
          {!cuoi && (
            <span
              className={`w-0.5 flex-1 ${xong ? "bg-success" : "bg-line"}`}
              style={{ minHeight: 16 }}
            />
          )}
        </div>

        <div className={`min-w-0 flex-1 ${cuoi ? "pb-1" : "pb-3.5"}`}>
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`text-sm ${
                xong
                  ? "font-medium text-ink"
                  : dang
                    ? "font-semibold text-brand-700"
                    : "text-ink-soft"
              }`}
            >
              {tt.ten}
            </span>

            {dang && !xong && (
              <span className="rounded-full bg-brand-100 px-2 py-0.5 text-[10px] font-bold text-brand-800">
                đang ở đây
              </span>
            )}
            {tt.tuChon && !dang && !xong && (
              <span
                className="rounded-full bg-surface-sunken px-1.5 py-0.5 text-[10px] font-medium text-ink-muted"
                title="Hệ thống không có dữ liệu để tự biết — CSKH chọn khi biết."
              >
                tự chọn
              </span>
            )}

            <button
              type="button"
              onClick={() => onLamViec(tt.ma)}
              aria-pressed={chon}
              className={
                chon
                  ? "rounded-full bg-brand-700 px-2.5 py-0.5 text-[11px] font-semibold text-white"
                  : xong
                    ? "rounded-full border border-line px-2.5 py-0.5 text-[11px] font-medium text-ink-soft hover:bg-surface-muted"
                    : dang
                      ? "rounded-full bg-brand-600 px-2.5 py-0.5 text-[11px] font-semibold text-white hover:bg-brand-700"
                      : "rounded-full border border-brand-300 px-2.5 py-0.5 text-[11px] font-medium text-brand-700 hover:bg-brand-50"
              }
            >
              {chon ? "Đang làm" : xong ? "Làm lại" : "Làm bước này"}
            </button>
          </div>

          {/* Việc phải làm — phần sau mũi tên trong đặc tả. */}
          <p className="mt-0.5 text-[11px] leading-snug text-ink-muted">
            {tt.viec}
          </p>

          {lan && (
            <p className="mt-1 text-[11px] leading-snug text-ink-soft">
              <span className="font-mono text-ink-muted">
                {gio(lan.xay_ra_luc)}
              </span>
              {lan.ket_qua && ` · ${NHAN_KET_QUA[lan.ket_qua] ?? lan.ket_qua}`}
              {lan.nhan_vien && ` · ${lan.nhan_vien}`}
              {lan.noi_dung && (
                <span className="block italic text-ink-muted">
                  “{lan.noi_dung}”
                </span>
              )}
            </p>
          )}
        </div>
      </li>
    );
  }

  return (
    <div className="min-w-0 space-y-3">
      <section
        aria-label={`Trạng thái khách hàng — ${tenKhach}`}
        className="min-w-0 overflow-hidden rounded-2xl border border-line bg-surface shadow-card"
      >
        {/* TIÊU ĐỀ MỘT DÒNG. Dòng phụ "Bấm vào bước để làm…" đã bỏ theo yêu cầu
            09/08 — nó mô tả mô hình chuỗi bước không còn nữa. */}
        <div className="border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold text-ink">
            Trạng thái khách hàng — {tenKhach}
          </h2>
        </div>

        <div className="space-y-3 px-4 py-3">
          {/* Hai cột ở phần trên: chuỗi "trước khám" bên trái, và khối gộp bên
              phải — chỗ trước đây bỏ trống. */}
          <div className="grid gap-x-6 gap-y-3 md:grid-cols-2">
            <div>
              <span className="text-[11px] font-bold uppercase tracking-wide text-ink-faint">
                Trước khám
              </span>
              <ol className="mt-1.5">
                {TRUOC_KHAM.map((tt, i) => (
                  <Node key={tt.ma} tt={tt} cuoi={i === TRUOC_KHAM.length - 1} />
                ))}
              </ol>
            </div>

            <div>
              <span className="text-[11px] font-bold uppercase tracking-wide text-ink-faint">
                Gọi không gặp · huỷ lịch
              </span>
              <div className="mt-1.5 space-y-2">
                <HangGop
                  ma="GOI_LAI"
                  ten="Gọi lại — không gặp được khách"
                  viec="Chọn đúng chuyện đã xảy ra ở cuộc gọi vừa rồi"
                  loiRa={KHONG_GAP_DUOC}
                  dang={dangO("GOI_LAI")}
                  xong={
                    Boolean(lanCuoi("GOI_LAI")) || xongTheoLich("GOI_LAI")
                  }
                  chon={dangChon === "GOI_LAI"}
                  lan={lanCuoi("GOI_LAI")}
                  onLamViec={onLamViec}
                  onGhi={(ma, kq) => void ghiLoiRa(ma, kq)}
                  dangGhi={dangGhiLoiRa}
                  loi={loiGhiLoiRa}
                />
                <HangGop
                  ma="HOI_LY_DO_HUY"
                  ten="Huỷ lịch"
                  viec="Gọi lại hỏi lý do huỷ, sau 1–14 ngày"
                  loiRa={[]}
                  dang={dangO("HOI_LY_DO_HUY")}
                  xong={
                    Boolean(lanCuoi("HOI_LY_DO_HUY")) ||
                    xongTheoLich("HOI_LY_DO_HUY")
                  }
                  chon={dangChon === "HOI_LY_DO_HUY"}
                  lan={lanCuoi("HOI_LY_DO_HUY")}
                  onLamViec={onLamViec}
                />
              </div>
            </div>
          </div>

          <div>
            <span className="text-[11px] font-bold uppercase tracking-wide text-ink-faint">
              Sau khám
            </span>
            <ol className="mt-1.5">
              {SAU_KHAM.map((tt, i) => (
                <Node key={tt.ma} tt={tt} cuoi={i === SAU_KHAM.length - 1} />
              ))}
            </ol>
          </div>

        </div>

        {/* Khối "KẾT QUẢ SIÊU ÂM / XÉT NGHIỆM" và dòng "Giờ khám" cũng đã bỏ
            (Quang chốt 09/08/2026). `TepKetQua` KHÔNG chết theo — màn
            HanhDongTrangThai vẫn dựng nó ở bước "Đã có kết quả, chưa gửi", đúng
            chỗ người ta thật sự tải kết quả lên. */}
      </section>

      {children}
    </div>
  );
}
