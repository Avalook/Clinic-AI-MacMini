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

/** SAU KHÁM KHÔNG PHẢI MỘT HÀNG DỌC — nó là một sơ đồ nhánh.
 *
 *  Quang vẽ ra 10/08/2026: "Đã check-in" toả ra BA nhánh xét nghiệm chạy song
 *  song, ba nhánh ấy chụm về "Đã gọi trả kết quả", rồi node đó toả ra BA việc
 *  theo dõi sau, cũng song song.
 *
 *  Trước đây mảng này được vẽ thành một `<ol>` tám node nối nhau bằng một sợi
 *  kẻ dọc — hình dạng nói rằng khách đi qua tám bước theo thứ tự. Không khách
 *  nào đi như thế: ba nhánh xét nghiệm là BA TÌNH HUỐNG loại trừ nhau, còn ba
 *  việc cuối là ba lý do theo dõi chẳng liên quan gì nhau.
 *
 *  THỨ TỰ CŨ VỐN ĐÃ ĐÚNG TOPO — chỉ có cách vẽ là sai. Nên đây không phải đổi
 *  luồng nghiệp vụ, chỉ là vẽ ra đúng cái vẫn luôn có. */
/** MỘT CHẠM LÀ XONG — bấm "Làm bước này" ghi luôn, không qua khối bên phải.
 *
 *  Quang 10/08/2026: *"chọn nút làm bước này cái là tick xanh luôn, vì như vậy
 *  là action luôn… ý tôi là tích hợp action vào nút đó luôn"*.
 *
 *  Những bước này KHÔNG cần thêm thông tin gì để có nghĩa: "đã hỏi đơn vị xét
 *  nghiệm" là toàn bộ nội dung của lần chạm ấy. Bắt đi thêm một khối bên phải
 *  để bấm nút thứ hai là hai thao tác cho một sự thật — cùng lý do đã áp cho
 *  ba lối ra "gọi không gặp".
 *
 *  MỖI DÒNG PHẢI GHI ĐÚNG THỨ KHỐI BÊN PHẢI ĐANG GHI. Lệch một chữ `loai` là
 *  node tích xanh mà trạng thái không đóng — đúng lỗi vừa vá ở DA_TRA_KQ, nơi
 *  hai nút ghi "KHAC" trong khi `dangO` dò "TRA_KQ".
 *
 *  KHÔNG có ở đây = vẫn mở khối bên phải như cũ. Ba việc "tự chọn" cuối và
 *  "Huỷ lịch" cố ý không một-chạm: huỷ phải chọn lý do, còn ba việc kia là
 *  quyết định của người trực chứ không phải một cú bấm cho xong. */
const MOT_CHAM: Record<
  string,
  { loai: string; ketQua: string; noiDung: string }
> = {
  DA_CHECKIN: {
    loai: "CHECK_IN",
    ketQua: "GHI_NHAN",
    noiDung: "Khách đã tới quầy",
  },
  CHO_KQ_XN: {
    loai: "CHECK_XN",
    ketQua: "DA_LIEN_HE",
    noiDung: "Đã hỏi đơn vị xét nghiệm",
  },
  CHO_BAC_SI: {
    loai: "KHAC",
    ketQua: "DA_LIEN_HE",
    noiDung: "Đã hỏi bác sĩ về kết quả",
  },
  KQ_CHUA_GUI: {
    loai: "TRA_KQ",
    ketQua: "DA_LIEN_HE",
    noiDung: "Đã gửi kết quả cho bệnh nhân",
  },
  DA_TRA_KQ: {
    loai: "TRA_KQ",
    ketQua: "DA_LIEN_HE",
    noiDung: "Đã gọi trả kết quả xét nghiệm",
  },
};

interface TangSauKham {
  /** Nhiều hơn một phần tử = các nhánh song song, vẽ cạnh nhau. */
  nhanh: TrangThai[];
  /** Có nối xuống tầng dưới bằng sợi kẻ không. Tầng cuối thì không. */
  noiXuong: boolean;
}

const SAU_KHAM_TANG: TangSauKham[] = [
  {
    nhanh: [
      {
        ma: "DA_CHECKIN",
        ten: "Đã check-in",
        viec: "Xem tình trạng sau khám để biết việc tiếp: trả kết quả xét nghiệm hay đặt lịch tái khám",
      },
    ],
    noiXuong: true,
  },
  {
    // BA TÌNH HUỐNG XÉT NGHIỆM, loại trừ nhau. View suy cả ba từ `lab_result`
    // (kết quả về chưa / bác sĩ duyệt chưa / gửi khách chưa), nên chúng tự
    // sáng lên chứ CSKH không chọn.
    nhanh: [
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
    ],
    noiXuong: true,
  },
  {
    nhanh: [
      {
        ma: "DA_TRA_KQ",
        ten: "Đã gọi trả kết quả xét nghiệm",
        viec: "Cân nhắc có cần hẹn lịch tái khám sau đó không",
      },
    ],
    noiXuong: true,
  },
  {
    // BA VIỆC THEO DÕI SAU, không liên quan nhau và đều TỰ CHỌN: hệ thống không
    // có nguồn dữ liệu để tự biết (ngày sinh con thật, dịch vụ thủ thuật đang
    // tắt). Xem ghi chú đầu file — đây là chủ ý, không phải thiếu sót.
    nhanh: [
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
    ],
    noiXuong: false,
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
  lanKhamGanNhat,
  onDatLich,
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
  /** Lượt khám gần nhất đã xong — nguồn cho nút "Tái khám". */
  lanKhamGanNhat?: {
    id: string;
    slot_start: string;
    service_type_id: string | null;
    service_name: string | null;
  } | null;
  /** Mở form đặt lịch. "tai-kham" = khoá dịch vụ + nối chuỗi; "kham-moi" =
   *  chọn dịch vụ tự do, không nối chuỗi. */
  onDatLich?: (kieu: "tai-kham" | "kham-moi") => void;
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
    await ghiMotCham(ma, {
      loai: "NHAC_HEN",
      ketQua,
      noiDung: "",
      khoa: ketQua,
    });
  }

  /** Ghi một lần chạm vào sổ chăm sóc. Dùng chung cho lối ra của hàng gộp và
   *  cho nút "Làm bước này" một-chạm.
   *
   *  `khoa` chỉ để nút biết mình đang là cái đang quay — nó là `ket_qua` với
   *  hàng gộp (ba nút cùng hàng, phải phân biệt được cái nào) và là mã trạng
   *  thái với node timeline (mỗi node một nút). */
  async function ghiMotCham(
    ma: string,
    v: { loai: string; ketQua: string; noiDung: string; khoa: string },
  ) {
    // NĂM LOẠI BẮT BUỘC GẮN LỊCH HẸN (CAN_LICH_HEN ở backend). Chặn tại đây
    // bằng một dòng đọc được, thay vì để backend trả 422 mà màn hình nuốt mất.
    const canLich = ["XAC_NHAN_LICH", "NHAC_HEN", "HOI_LY_DO_HUY", "CHECK_IN", "CHECK_OUT"];
    if (canLich.includes(v.loai) && !lich.id) {
      setLoiGhiLoiRa("Khách chưa có lịch hẹn nào để gắn thao tác này.");
      return;
    }
    // LUÔN GẮN LỊCH HẸN KHI CÓ, không chỉ với năm loại bắt buộc.
    //
    // ĐÂY LÀ LỖI QUANG BẮT ĐƯỢC 10/08/2026: *"ở lượt khám mới ấn mấy nút dưới
    // nó chả động tĩnh gì"*. Bấm CÓ ghi vào sổ — nhưng `CHECK_XN`, `KHAC`,
    // `TRA_KQ`, `HOI_THAM` xưa nay ghi với `appointment_id = NULL` (đo trên
    // staging: 19/40 dòng), mà bản vá "tích xanh theo lượt" ngay trước đó lọc
    // sổ theo `appointment_id`. Nên dòng vừa ghi bị chính màn hình loại ra:
    // ghi thật, tích không lên, người dùng thấy nút chết.
    //
    // Backend chỉ ĐÒI `appointment_id` cho năm loại kia; nó nhận với mọi loại
    // và còn kiểm lịch ấy đúng của khách này. Gắn luôn là vừa sửa được cái nút,
    // vừa gom đúng bước vào đúng lượt ở ô Lịch sử các lần khám.
    setDangGhiLoiRa(v.khoa);
    setLoiGhiLoiRa(null);
    const res = await fetch("/api/cskh/tuong-tac", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clinic_patient_id: clinicPatientId,
        appointment_id: lich.id ?? null,
        loai: v.loai,
        // Mốc quầy đòi đúng cặp TRUC_TIEP + GHI_NHAN; còn lại là cuộc gọi.
        kenh: v.ketQua === "GHI_NHAN" ? "TRUC_TIEP" : "GOI",
        ket_qua: v.ketQua,
        noi_dung: v.noiDung.trim() || null,
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

  /** SỔ CHĂM SÓC CỦA RIÊNG LƯỢT ĐANG XEM.
   *
   *  LỖI QUANG TÌM RA 10/08/2026: khám xong cho Huyền rồi đặt lịch khám mới thì
   *  *"bên phải nó cũng chưa update cho lượt khám mới ấy"* — và cột giữa cũng
   *  vậy. Cả chuỗi trạng thái vẫn xanh nguyên từ lượt trước.
   *
   *  Vì `lichSu` là sổ của cả KHÁCH, không phải của một LƯỢT. `lanCuoi` dò
   *  `trang_thai_ma` trên toàn bộ sổ, nên mọi bước đã làm ở lượt tháng trước
   *  vẫn tích xanh ở lượt hôm nay — lượt mới sinh ra đã "hoàn thành" sẵn, và
   *  người trực không còn gì để làm theo màn hình.
   *
   *  Lọc theo `appointment_id` (cột có từ 20260809000003, vừa được mang xuống
   *  UI). Không có lịch đại diện thì giữ nguyên cả sổ: thà tích thừa còn hơn
   *  một màn trắng không giải thích được. */
  const lichSuLuotNay = lich.id
    ? lichSu.filter((d) => d.appointment_id === lich.id)
    : lichSu;

  const [dangCheckout, setDangCheckout] = useState(false);
  const [loiCheckout, setLoiCheckout] = useState<string | null>(null);
  const daKhamXong = lich.status === "COMPLETED";

  /** Đóng lượt khám hôm nay.
   *
   *  ĐI QUA `CHECK_OUT` CỦA SỔ CHĂM SÓC, không gọi thẳng endpoint checkout của
   *  Quầy tiếp nhận — và đó là một lựa chọn, không phải đường tắt:
   *
   *    · `/api/v1/dispatch/checkout` gác bằng `_RECEPTION_GUARD`, chỉ Lễ tân /
   *      Trưởng ca / Quản lý. CSKH đứng ở màn này KHÔNG có quyền gọi. Mở quyền
   *      ấy ra là cho CSKH đi qua cả những chốt nghiệp vụ của quầy (chưa thu
   *      tiền, chưa lấy thuốc) mà họ không có thông tin để phán.
   *    · `loai = "CHECK_OUT"` thì `tuong_tac_cskh_service` gọi
   *      `BookingService.apply_action("complete")` — đi ĐÚNG máy trạng thái,
   *      lịch hẹn sang COMPLETED, và CSKH có quyền làm việc đó
   *      (MANAGE_ROLES gồm CSKH). Đồng thời ghi một dòng vào sổ chăm sóc.
   *
   *  ĐIỀU NÀY KHÔNG ĐÓNG DÒNG `visit`. `visit.closed_at` chỉ do
   *  `checkout_service` ghi, và đó là việc của quầy. Nói ra ở đây để lần sau ai
   *  đọc "Checkout" trên màn này không tưởng nó đã đóng mọi thứ. */
  async function ghiCheckout() {
    if (!lich.id) {
      setLoiCheckout("Khách chưa có lịch hẹn nào để đóng.");
      return;
    }
    setDangCheckout(true);
    setLoiCheckout(null);
    const res = await fetch("/api/cskh/tuong-tac", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clinic_patient_id: clinicPatientId,
        appointment_id: lich.id,
        loai: "CHECK_OUT",
        // Mốc quầy: backend đòi đúng cặp TRUC_TIEP + GHI_NHAN, sai là 422.
        kenh: "TRUC_TIEP",
        ket_qua: "GHI_NHAN",
      }),
    });
    setDangCheckout(false);
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as {
        error?: string;
        message?: string;
      } | null;
      setLoiCheckout(
        d?.message ?? d?.error ?? `Không đóng được (lỗi ${res.status}).`,
      );
      return;
    }
    router.refresh();
  }

  const daHuy = lich.status === "CANCELLED";
  const daCheckin =
    lich.status === "CHECKED_IN" || lich.status === "COMPLETED";

  function cacLan(loai: string): DongLichSu[] {
    // Cũng chỉ trong lượt đang xem — xem ghi chú ở `lichSuLuotNay`. `dangO`
    // đọc hàm này, nên không lọc thì "đang ở đây" cũng kẹt lại ở lượt cũ.
    return lichSuLuotNay.filter((d) => d.loai === loai);
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
    const theoMa = lichSuLuotNay.find((d) => d.trang_thai_ma === ma);
    if (theoMa) return theoMa;
    const loai = SUY_THEO_LOAI_CU[ma];
    return loai ? lichSuLuotNay.find((d) => loai.includes(d.loai)) : undefined;
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
    const motCham = MOT_CHAM[tt.ma];

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

            {/* MỘT CHẠM LÀ XONG với những bước có trong `MOT_CHAM`: bấm ghi
                thẳng vào sổ và node tích xanh ngay, không mở khối bên phải.
                Bước không có trong bảng ấy thì giữ nguyên hành vi cũ. */}
            <button
              type="button"
              disabled={Boolean(motCham && dangGhiLoiRa)}
              onClick={() =>
                motCham
                  ? void ghiMotCham(tt.ma, { ...motCham, khoa: tt.ma })
                  : onLamViec(tt.ma)
              }
              aria-pressed={chon}
              className={`${
                chon
                  ? "rounded-full bg-brand-700 px-2.5 py-0.5 text-[11px] font-semibold text-white"
                  : xong
                    ? "rounded-full border border-line px-2.5 py-0.5 text-[11px] font-medium text-ink-soft hover:bg-surface-muted"
                    : dang
                      ? "rounded-full bg-brand-600 px-2.5 py-0.5 text-[11px] font-semibold text-white hover:bg-brand-700"
                      : "rounded-full border border-brand-300 px-2.5 py-0.5 text-[11px] font-medium text-brand-700 hover:bg-brand-50"
              } disabled:opacity-50`}
            >
              {dangGhiLoiRa === tt.ma
                ? "Đang ghi…"
                : chon
                  ? "Đang làm"
                  : xong
                    ? "Làm lại"
                    : "Làm bước này"}
            </button>

            {/* LỖI PHẢI HIỆN NGAY TẠI NÚT VỪA BẤM.
                `Node` chưa từng vẽ `loiGhiLoiRa`, nên một cú ghi hỏng trông y
                hệt một cú bấm không ăn — và đó chính là "chả động tĩnh gì" mà
                Quang gặp. Một nút im lặng dạy người dùng bấm lại nhiều lần rồi
                bỏ cuộc; một dòng đỏ nói được chuyện gì đã xảy ra. */}
            {motCham && loiGhiLoiRa && dangGhiLoiRa === null && (
              <span className="text-[11px] text-danger">{loiGhiLoiRa}</span>
            )}
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
            {/* Vẽ theo TẦNG. Tầng một nhánh là một node như cũ; tầng nhiều
                nhánh xếp cạnh nhau trên lưới, mỗi nhánh là một node độc lập
                không nối sợi dọc — vì chúng không nối tiếp nhau. Giữa hai tầng
                là một sợi kẻ ngắn nói "xong tầng trên thì tới tầng dưới". */}
            <div className="mt-1.5 space-y-0">
              {SAU_KHAM_TANG.map((tang, i) => (
                <div key={i}>
                  {tang.nhanh.length === 1 ? (
                    <ol>
                      <Node tt={tang.nhanh[0]!} cuoi />
                    </ol>
                  ) : (
                    <ol className="grid gap-x-3 sm:grid-cols-3">
                      {tang.nhanh.map((tt) => (
                        <Node key={tt.ma} tt={tt} cuoi />
                      ))}
                    </ol>
                  )}
                  {tang.noiXuong && (
                    <div
                      aria-hidden="true"
                      className="ml-3 w-0.5 bg-line"
                      style={{ height: 14 }}
                    />
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* KẾT THÚC LƯỢT KHÁM — ba lối ra, và chúng KHÁC NHAU về nghĩa.
              Quang 10/08/2026 vạch rõ ranh giới, chép lại vì nhìn nút thì
              không đoán ra:

                Checkout   đóng lượt khám hôm nay. *"không thể để thời gian
                           khám cứ trôi mãi mà không có điểm dừng"* — và đóng
                           rồi thì hôm sau đặt lịch cho chính khách ấy không bị
                           coi là chồng lấn.
                Tái khám   khám lại ĐÚNG DỊCH VỤ của lượt này. Lịch mới nối vào
                           lượt này bằng `lich_truoc_id`.
                Khám mới   khám xong, về rồi, lần sau khám dịch vụ KHÁC — hoặc
                           cùng dịch vụ nhưng là chuyện mới. Không nối chuỗi.

              ĐẶT Ở CUỐI, CĂN GIỮA (Quang chốt 10/08/2026). Ba nút này là chỗ
              lượt khám KẾT THÚC, nên chúng phải nằm sau chuỗi trạng thái chứ
              không cắt ngang giữa "trước khám" và "sau khám" — đứng ở giữa thì
              chúng trông như một bước nữa trong quy trình, mà chúng là dấu chấm
              hết. Căn giữa để tách hẳn khỏi các node xếp trái bên trên. */}
          <div className="space-y-1.5 border-t border-line pt-3 text-center">
            <span className="text-[11px] font-bold uppercase tracking-wide text-ink-faint">
              Kết thúc lượt khám
            </span>
            <div className="flex flex-wrap justify-center gap-1.5">
              <button
                type="button"
                onClick={() => void ghiCheckout()}
                disabled={dangCheckout || daKhamXong}
                title={
                  daKhamXong
                    ? "Lượt khám này đã đóng"
                    : "Đóng lượt khám hôm nay"
                }
                className="inline-flex items-center gap-1.5 rounded-xl border border-brand-600 bg-surface px-2.5 py-1.5 text-[11px] font-semibold text-brand-700 hover:bg-brand-50 disabled:opacity-50"
              >
                <Check className="size-3.5" />
                {daKhamXong
                  ? "Đã checkout"
                  : dangCheckout
                    ? "Đang đóng…"
                    : "Checkout"}
              </button>
              <button
                type="button"
                onClick={() => onDatLich?.("tai-kham")}
                disabled={!lanKhamGanNhat}
                title={
                  lanKhamGanNhat
                    ? `Tái khám dịch vụ ${lanKhamGanNhat.service_name ?? "của lượt trước"}`
                    : "Khách chưa có lượt khám nào đã xong để tái khám"
                }
                className="rounded-xl border border-brand-300 px-2.5 py-1.5 text-[11px] font-medium text-brand-700 hover:bg-brand-50 disabled:opacity-40"
              >
                Tái khám
              </button>
              <button
                type="button"
                onClick={() => onDatLich?.("kham-moi")}
                className="rounded-xl border border-line px-2.5 py-1.5 text-[11px] font-medium text-ink-soft hover:bg-surface-muted"
              >
                Đặt lịch khám mới
              </button>
            </div>
            {loiCheckout && (
              <p className="text-[11px] text-danger">{loiCheckout}</p>
            )}
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
