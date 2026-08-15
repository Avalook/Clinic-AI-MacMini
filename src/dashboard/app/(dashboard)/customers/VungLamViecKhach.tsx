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
import { nhanLoi } from "@/lib/loi-api";
import { khoaThaoTac, xongThaoTac, dinhDanhThaoTac } from "./khoa-mot-lan";
import { useRouter } from "next/navigation";
import { Check, Phone, CircleDashed, Undo2 } from "lucide-react";
import { nhanLyDoHuy } from "@/lib/ly-do-huy";
import { MOT_CHAM, kenhCho } from "./mot-cham";
import type { DongLichSu } from "./so-tuong-tac";
import type { HenGoiLai } from "./CustomersView";
import type { MocTaiKham } from "./NhacTaiKham";

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
  // Dáng pill GIỮ NGUYÊN — Quang chốt hình nút này ("giống mấy cái nút làm
  // bước này"), và lời người dùng đứng trên DESIGN.md. Chỉ đổi cách vẽ viền:
  // ring-inset thay border để góc cong không nhạt hơn cạnh (DESIGN.md §5).
  const nen = "rounded-full px-2.5 py-0.5 text-label";
  if (chon) return `${nen} bg-brand-700 font-semibold text-white`;
  if (xong)
    return `${nen} ring-1 ring-inset ring-line font-medium text-ink-soft hover:bg-surface-muted`;
  if (dang)
    return `${nen} bg-brand-600 font-semibold text-white hover:bg-brand-700`;
  return `${nen} ring-1 ring-inset ring-brand-300 font-medium text-brand-700 hover:bg-brand-50`;
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
  ghiChuThem,
  onHoanTac,
  dangHoanTac,
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
  /** Chuyện đã ghi ở NƠI KHÁC mà hàng này phải nói ra — ví dụ lý do huỷ, thứ
   *  `booking_service` lưu trên chính `appointment` chứ không lưu vào sổ. */
  ghiChuThem?: React.ReactNode;
  /** Rút lại dòng đã ghi của hàng này. Không truyền = không hoàn tác được. */
  onHoanTac?: (id: string) => void;
  dangHoanTac?: string | null;
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
      <VongTron
        xong={xong}
        dang={dang}
        hoanTacDuoc={Boolean(lan?.id && onHoanTac)}
        dangHoanTac={dangHoanTac === lan?.id}
        onHoanTac={() => lan?.id && onHoanTac?.(lan.id)}
      />

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
            <span className="rounded-chip bg-surface-sunken px-1.5 py-0.5 text-label font-medium text-ink-muted">
              {ten}
            </span>
          )}
          {dang && !xong && (
            <span className="rounded-chip bg-brand-100 px-2 py-0.5 text-label font-bold text-brand-800">
              đang ở đây
            </span>
          )}
        </div>

        <p className="mt-0.5 text-label leading-snug text-ink-muted">{viec}</p>

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
        {loi && <p className="mt-1 text-label text-danger">{loi}</p>}

        {lan && (
          <p className="mt-1 text-label leading-snug text-ink-soft">
            <span className="font-mono text-ink-muted">
              {gio(lan.xay_ra_luc)}
            </span>
            {lan.ket_qua && ` · ${NHAN_KET_QUA[lan.ket_qua] ?? lan.ket_qua}`}
            {lan.nhan_vien && ` · ${lan.nhan_vien}`}
            {/* CHỮ NGƯỜI TRỰC GÕ PHẢI HIỆN LẠI.
                `Node` vẽ `noi_dung` từ lâu; `HangGop` — component anh em, cùng
                nhận `lan` — thì không. Nên mọi ghi chú gõ trong panel phải của
                hai hàng gộp ("Gọi lại — không gặp được khách" và "Huỷ lịch")
                ghi vào sổ thật rồi biến mất khỏi màn hình. Lưu mà không hiện
                thì lần sau người ta gõ lại từ đầu, hoặc thôi không gõ nữa. */}
            {lan.noi_dung && (
              <span className="block italic text-ink-muted">
                “{lan.noi_dung}”
              </span>
            )}
          </p>
        )}
        {ghiChuThem}
      </div>
    </div>
  );
}

/** VÒNG TRÒN ĐẦU MỖI SỰ KIỆN — và là nút hoàn tác khi có gì để rút.
 *
 *  Hình dạng giữ nguyên như trước để không ai phải học lại màn hình: viền dày,
 *  tích xanh khi xong, điện thoại khi đang ở đây, vòng đứt khi chưa tới. Chỉ
 *  thêm một vòng ngoài mảnh và con trỏ tay khi bấm được — đủ để nhận ra, không
 *  đủ để lấn át. */
function VongTron({
  xong,
  dang,
  hoanTacDuoc,
  dangHoanTac,
  onHoanTac,
}: {
  xong: boolean;
  dang: boolean;
  hoanTacDuoc: boolean;
  dangHoanTac: boolean;
  onHoanTac: () => void;
}) {
  const lop = `flex size-7 shrink-0 items-center justify-center rounded-full border-2 ${
    xong
      ? "border-success bg-success-bg text-success"
      : dang
        ? "border-brand-600 bg-brand-50 text-brand-700"
        : "border-line bg-surface-muted text-ink-faint"
  }`;
  const ruot = dangHoanTac ? (
    <Undo2 className="size-3.5 animate-pulse" />
  ) : xong ? (
    <Check className="size-4" strokeWidth={3} />
  ) : dang ? (
    <Phone className="size-3.5" />
  ) : (
    <CircleDashed className="size-3.5" />
  );
  if (!hoanTacDuoc) return <span className={lop}>{ruot}</span>;
  return (
    <button
      type="button"
      onClick={onHoanTac}
      disabled={dangHoanTac}
      title="Bấm để hoàn tác thao tác này — dòng vẫn nằm trong sổ"
      aria-label="Hoàn tác thao tác này"
      className={`${lop} ring-1 ring-inset ring-brand-300 hover:ring-2 hover:ring-brand-500 disabled:opacity-50`}
    >
      {ruot}
    </button>
  );
}

/** Bốn kết quả của một cuộc gọi nhắc — cùng bộ từ với `RecallCallResult` ở
 *  backend và với CHECK ở database. Gửi mã ngoài bốn cái này là 422. */
// Trường tên `ketQua`, KHÔNG phải `ma`: đây là `ket_qua` của một cuộc gọi, không
// phải mã trạng thái. `cskh-trang-thai-drift` quét `ma:` để gom mã trạng thái ở
// cột giữa, nên đặt trùng tên là kéo bốn mã này vào một danh sách chúng không
// thuộc về — bài kiểm ấy đã bắt được đúng chuyện đó.
const KET_QUA_GOI_NHAC: LoiRa[] = [
  { ketQua: "DA_LIEN_HE", ten: "Đã liên hệ được" },
  { ketQua: "CHUA_NGHE_MAY", ten: "Không nghe máy" },
  { ketQua: "TU_CHOI", ten: "Khách từ chối" },
  { ketQua: "CAN_BAC_SI", ten: "Cần bác sĩ xem" },
];

/** MỘT VIỆC GỌI NHẮC — lượt 1 mời tái khám, lượt 2 nhắc đi khám.
 *
 *  Ở CẤP MODULE, không lồng trong `VungLamViecKhach`. */
function MotViecGoiNhac({
  viec,
  dang,
  loi,
  onGhi,
}: {
  viec: MocTaiKham;
  dang: string | null;
  loi: string | null;
  onGhi: (ketQua: string) => void;
}) {
  return (
    <div
      className={`flex gap-3 rounded-xl border p-2.5 ${
        viec.qua_han ? "border-danger/40 bg-danger-bg/30" : "border-line"
      }`}
    >
      <span
        className={`flex size-7 shrink-0 items-center justify-center rounded-full border-2 ${
          viec.qua_han
            ? "border-danger bg-danger-bg text-danger"
            : "border-brand-600 bg-brand-50 text-brand-700"
        }`}
      >
        <Phone className="size-3.5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-ink">
            {viec.luot_goi === 1 ? "Gọi mời tái khám" : "Gọi nhắc đi khám"}
          </span>
          {viec.qua_han && (
            <span className="rounded-chip bg-danger-bg px-2 py-0.5 text-label font-bold text-danger">
              quá hạn
            </span>
          )}
        </div>
        <p className="mt-0.5 text-label leading-snug text-ink-muted">
          Hẹn quay lại {ngayVn(viec.ngay_hen)} · phải gọi trước{" "}
          {ngayVn(viec.han_goi)}
          {viec.ly_do ? ` · ${viec.ly_do}` : ""}
        </p>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {KET_QUA_GOI_NHAC.map((k) => (
            <button
              key={k.ketQua}
              type="button"
              disabled={Boolean(dang)}
              onClick={() => onGhi(k.ketQua)}
              className="rounded-full px-2.5 py-0.5 text-label font-medium text-brand-700 ring-1 ring-inset ring-brand-300 hover:bg-brand-50 disabled:opacity-50"
            >
              {dang === viec.id + k.ketQua ? "Đang ghi…" : k.ten}
            </button>
          ))}
        </div>
        {loi && <p className="mt-1 text-label text-danger">{loi}</p>}
      </div>
    </div>
  );
}

/** MỘT LỜI HẸN GỌI LẠI — ngày, giờ, lý do, và một nút đóng nó.
 *
 *  Ở CẤP MODULE, không lồng trong `VungLamViecKhach`: component tạo ra trong
 *  lúc render thì React dựng lại từ đầu mỗi lần vẽ. */
function MotLoiHen({
  hen,
  dangDong,
  loi,
  onDong,
}: {
  hen: HenGoiLai;
  dangDong: boolean;
  loi: string | null;
  onDong: () => void;
}) {
  const homNay = new Date().toLocaleDateString("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
  });
  const toiHan = hen.ngay_goi <= homNay;
  return (
    <div
      className={`flex gap-3 rounded-xl border p-2.5 ${
        toiHan ? "border-brand-300 bg-brand-50/50" : "border-line"
      }`}
    >
      <span
        className={`flex size-7 shrink-0 items-center justify-center rounded-full border-2 ${
          toiHan
            ? "border-brand-600 bg-brand-50 text-brand-700"
            : "border-line bg-surface-muted text-ink-faint"
        }`}
      >
        <Phone className="size-3.5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-ink">
            {/* GIỜ CHỈ HIỆN KHI CÓ. `gio_goi` null nghĩa là "chỉ hẹn tới ngày";
                in 00:00 vào đấy là bịa một mốc mà người trực sẽ tin. */}
            Gọi lại {hen.gio_goi ? `${hen.gio_goi.slice(0, 5)} ` : ""}ngày{" "}
            {ngayVn(hen.ngay_goi)}
          </span>
          {toiHan && (
            <span className="rounded-chip bg-brand-100 px-2 py-0.5 text-label font-bold text-brand-800">
              tới hạn
            </span>
          )}
        </div>
        <p className="mt-0.5 text-label leading-snug text-ink-soft">
          {hen.ly_do}
        </p>
        {hen.tao_boi && (
          <p className="mt-0.5 text-label text-ink-muted">
            người hẹn: {hen.tao_boi}
          </p>
        )}
        <button
          type="button"
          onClick={onDong}
          disabled={dangDong}
          className="mt-1.5 rounded-full px-2.5 py-0.5 text-label font-medium text-brand-700 ring-1 ring-inset ring-brand-300 hover:bg-brand-50 disabled:opacity-50"
        >
          {dangDong ? "Đang đóng…" : "Đã gọi xong — đóng việc"}
        </button>
        {loi && <p className="mt-1 text-label text-danger">{loi}</p>}
      </div>
    </div>
  );
}

/** Ngày dạng yyyy-mm-dd → dd/mm. */
function ngayVn(d: string): string {
  const [y, m, ngay] = d.split("-");
  return ngay && m ? `${ngay}/${m}${y ? `/${y}` : ""}` : d;
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

/** LƯỢT KHÁM ĐANG XEM — đúng những gì cột giữa cần biết về một lượt.
 *
 *  ĐÂY KHÔNG CÒN LÀ "LỊCH ĐẠI DIỆN". Trước 10/08/2026 `id` và `status` của vật
 *  này đến từ HAI nguồn khác nhau ở `CustomersView` (`appt?.id` và `repr`), nên
 *  một lượt đã khám xong cho ra `status = COMPLETED` kèm `id = null`. Nay nó
 *  luôn là MỘT lượt có thật, do người dùng chọn hoặc do `luotMacDinh` chọn. */
export interface MocLich {
  id: string | null;
  status: string | null;
  slot_start: string | null;
  created_at: string | null;
  cancelled_at: string | null;
  /** Lý do huỷ CỦA LƯỢT NÀY — mã chọn sẵn, và chữ người huỷ tự viết. */
  ly_do_huy_ma: string | null;
  cancellation_reason: string | null;
  /** Dịch vụ của lượt — nút "Tái khám" khoá theo nó. */
  service_type_id: string | null;
  service_name: string | null;
  /** Bác sĩ của lượt này không còn ca KHÁM vào ngày khám. Tính ở page.tsx từ
   *  `work_roster` (station = LICH_KHAM), theo TỪNG LƯỢT. */
  mat_bac_si?: boolean;
  /** Bác sĩ bị gỡ đã có ca khám trở lại hôm đó. */
  bs_go_co_ca_lai?: boolean;
}

export default function VungLamViecKhach({
  tenKhach,
  clinicPatientId,
  lich,
  lichSu,
  viecCuaLuot = [],
  dangChon,
  onLamViec,
  onDatLich,
  henGoiLai = [],
  taiKham = [],
  ghiChu = "",
  onGhiChuXong,
  children,
}: {
  tenKhach: string;
  clinicPatientId: string;
  lich: MocLich;
  lichSu: DongLichSu[];
  /** VIỆC ĐANG MỞ CỦA CHÍNH LƯỢT NÀY, gấp nhất trước (`v_viec_cskh`).
   *
   *  Thay cho `trangThaiHienTai` — một chuỗi duy nhất suy từ `v_trang_thai_cskh`,
   *  tức việc gấp nhất của CẢ KHÁCH. Khách có nhiều lượt thì nó nói về lượt
   *  khác: ca Cường 10/08/2026, lượt hôm qua đang CHECKED_IN nên node "Đã
   *  check-in" sáng "đang ở đây" ngay trên lượt tái khám ngày mai, và cột phải
   *  mời "Check-in cho khách" cho một người chưa từng đến.
   *
   *  Danh sách nên NHIỀU node cùng sáng được — khách có thể vừa chờ kết quả xét
   *  nghiệm vừa tới hạn nhắc hẹn, và view vẫn luôn biết cả hai. */
  viecCuaLuot?: { trang_thai: string; appointment_id: string | null }[];
  /** Trạng thái CSKH đang chọn làm việc (null = chưa chọn). */
  dangChon?: string | null;
  /** Bấm một trạng thái → khối hành động bên phải đổi theo nó. `ketQua` chỉ
   *  truyền khi bấm một lối ra cụ thể trong hàng gộp — hôm nay không hàng nào
   *  dùng tới, vì lối ra ghi thẳng. Giữ tham số cho nhóm sau. */
  onLamViec: (maTrangThai: string, ketQua?: string) => void;
  /** Mở form đặt lịch. "tai-kham" = khoá dịch vụ + nối chuỗi; "kham-moi" =
   *  chọn dịch vụ tự do, không nối chuỗi. */
  onDatLich?: (kieu: "tai-kham" | "kham-moi") => void;
  /** Lời hẹn gọi lại CHƯA ĐÓNG của khách này. */
  henGoiLai?: HenGoiLai[];
  /** Mốc gọi nhắc tái khám CÒN PHẢI GỌI của khách này. */
  taiKham?: MocTaiKham[];
  /** Ghi chú người dùng đang gõ ở CỘT PHẢI — đi kèm cú bấm một-chạm ở đây. */
  ghiChu?: string;
  /** Gọi sau khi ghi xong, để cột phải xoá ô gõ. */
  onGhiChuXong?: () => void;
  /** Khối gắn thêm bên dưới — nay chỉ còn "Phản hồi của khách". */
  children?: React.ReactNode;
}) {

  const router = useRouter();
  const [dangGhiLoiRa, setDangGhiLoiRa] = useState<string | null>(null);
  // LỖI PHẢI BIẾT NÓ THUỘC VỀ BƯỚC NÀO.
  //
  // Bản trước chỉ giữ câu chữ. Node vẽ nó với điều kiện `motCham && loiGhiLoiRa`
  // — không hỏi bước nào — nên MỘT bước hỏng là MỌI bước cùng hiện y câu ấy.
  // Tuyền gặp đúng thế 14/08/2026: chốt "chưa gửi tệp kết quả" chỉ áp cho bước
  // trả kết quả (tuong_tac_cskh_service.py, `if loai == "TRA_KQ"`), nhưng câu
  // ấy hiện dưới cả "Đã check-in", "Gọi nhắc hẹn", "Huỷ lịch", "Không cần
  // follow up" — những bước không liên quan gì tới tệp kết quả.
  //
  // Một dòng đỏ nói sai chỗ tệ hơn không có dòng nào: nó bảo người trực rằng
  // mọi bước đều đang hỏng, nên họ ngừng tin mọi dòng đỏ, kể cả dòng đúng.
  // Cùng bài học với lỗi "một bước hỏng tô đỏ cả chuỗi" hồi trước.
  const [loiGhiLoiRa, setLoiGhiLoiRa] = useState<
    { ma: string; cau: string } | null
  >(null);
  const [dangDongHen, setDangDongHen] = useState<string | null>(null);
  const [loiDongHen, setLoiDongHen] = useState<string | null>(null);
  const [loiDongHenChu, setLoiDongHenChu] = useState<string | null>(null);

  /** ĐÓNG MỘT LỜI HẸN GỌI LẠI.
   *
   *  `PATCH /api/cskh/hen-goi-lai` đã có sẵn ở BFF (route.ts) và ở backend
   *  (`HenGoiLaiService.dong`) từ 09/08 — nhưng không một màn nào gọi nó. Đó là
   *  lý do trạng thái `HEN_GOI_LAI` không có đường ra: sinh ra được, hiện ra
   *  được, và ở lại mãi mãi. */
  async function dongHen(id: string) {
    setDangDongHen(id);
    setLoiDongHen(null);
    setLoiDongHenChu(null);
    const res = await fetch("/api/cskh/hen-goi-lai", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    setDangDongHen(null);
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as {
        error?: string;
        message?: string;
      } | null;
      setLoiDongHen(id);
      setLoiDongHenChu(
        nhanLoi(d, `Không đóng được (lỗi ${res.status}).`),
      );
      return;
    }
    router.refresh();
  }

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
    v: {
      loai: string;
      ketQua: string;
      noiDung: string;
      khoa: string;
      khachXacNhan?: boolean;
    },
  ) {
    // NĂM LOẠI BẮT BUỘC GẮN LỊCH HẸN (CAN_LICH_HEN ở backend). Chặn tại đây
    // bằng một dòng đọc được, thay vì để backend trả 422 mà màn hình nuốt mất.
    const canLich = ["XAC_NHAN_LICH", "NHAC_HEN", "HOI_LY_DO_HUY", "CHECK_IN", "CHECK_OUT"];
    if (canLich.includes(v.loai) && !lich.id) {
      setLoiGhiLoiRa({
        ma: v.khoa,
        cau: "Khách chưa có lịch hẹn nào để gắn thao tác này.",
      });
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
    // Khoá theo thao tác — xem khoa-mot-lan.ts.
    const ttLoiRa = dinhDanhThaoTac(clinicPatientId, lich.id, v.loai, v.ketQua, v.khoa);
    const res = await fetch("/api/cskh/tuong-tac", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": khoaThaoTac(ttLoiRa),
      },
      body: JSON.stringify({
        clinic_patient_id: clinicPatientId,
        appointment_id: lich.id ?? null,
        loai: v.loai,
        // BA LUẬT CHÉO của backend gom vào `kenhCho` — gửi sai là 422, và
        // `BO_QUA` (nút "Không cần follow up") là cái từng gửi sai suốt.
        kenh: kenhCho(v.ketQua),
        ket_qua: v.ketQua,
        khach_xac_nhan: v.khachXacNhan ?? null,
        // GHI CHÚ NGƯỜI DÙNG GÕ THẮNG nội dung mặc định. Mặc định chỉ là câu
        // mô tả việc ("Đã gọi xác nhận lịch"); thứ người trực gõ tay bao giờ
        // cũng nói được nhiều hơn ("khách đang họp, gọi lại sau 5h").
        noi_dung: ghiChu.trim() || v.noiDung.trim() || null,
        trang_thai_ma: ma,
      }),
    });
    setDangGhiLoiRa(null);
    if (res.ok) onGhiChuXong?.();
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as {
        error?: string;
        message?: string;
      } | null;
      // MÁY CHỦ TỪ CHỐI (4xx) ⇒ BỎ KHOÁ THAO TÁC.
      //
      // 4xx nghĩa là chắc chắn chưa ghi gì, và lần bấm lại sau khi sửa là một
      // thao tác MỚI. Giữ khoá thì lần ấy đâm vào chính hàng đang PROCESSING
      // trong bảng idempotency_key và nhận 409 "Yêu cầu với Idempotency-Key này
      // đang được xử lý" — kẹt đủ 5 phút, và câu giải thích THẬT ("chưa gửi tệp
      // kết quả cho khách") biến mất sau nó.
      //
      // 5xx / lỗi mạng thì GIỮ khoá: lúc đó không ai biết máy chủ đã ghi tới
      // đâu, và bỏ khoá là mở đường cho một bản ghi thứ hai.
      if (res.status >= 400 && res.status < 500) xongThaoTac(ttLoiRa);
      setLoiGhiLoiRa({
        ma: v.khoa,
        cau: nhanLoi(d, `Không ghi được (lỗi ${res.status}).`),
      });
      return;
    }
    xongThaoTac(ttLoiRa); // xong ⇒ lần bấm sau là thao tác mới
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
   *  UI).
   *
   *  KHÔNG CÓ LỊCH THÌ SỔ RỖNG, VÀ NÓI RA. Bản 10/08 sáng viết `: lichSu` —
   *  "thà tích thừa còn hơn một màn trắng không giải thích được". Nhưng nó tích
   *  thừa TRONG IM LẶNG, và đúng lúc `lich.id` hay bị null nhất: ngay sau
   *  checkout. Người trực mở một lượt vừa sinh ra đã thấy đủ tám bước xanh —
   *  không còn gì để làm theo màn hình, mà chẳng có gì báo là màn đang nói về
   *  lượt khác. Rỗng KÈM MỘT DÒNG CHỮ thì người đọc biết mình đang thiếu gì. */
  // DÒNG ĐÃ HOÀN TÁC KHÔNG ĐƯỢC TÍNH — nhưng vẫn nằm trong sổ.
  //
  // Quang 10/08/2026 muốn bấm nhầm thì rút lại được, và log thì không được xoá.
  // Nên `huy_luc` là lá cờ: dòng ở lại cho "Lịch sử các lần khám" đọc, còn mọi
  // phép suy trạng thái ở đây bỏ qua nó — đúng như `v_viec_cskh` làm ở server.
  // Hai bên phải cùng luật, nếu không node tích xanh mà chip bên trái mở lại.
  const lichSuLuotNay = (
    lich.id ? lichSu.filter((d) => d.appointment_id === lich.id) : []
  ).filter((d) => !d.huy_luc);
  const khongGanDuocLuot = !lich.id && lichSu.length > 0;

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
  async function ghiCheckout(): Promise<boolean> {
    if (!lich.id) {
      setLoiCheckout("Khách chưa có lịch hẹn nào để đóng.");
      return false;
    }
    // ĐÃ ĐÓNG RỒI THÌ THÔI, coi như xong. `apply_action("complete")` chỉ nhận
    // từ CHECKED_IN, nên bấm lần hai trên một lượt COMPLETED sẽ báo lỗi cho một
    // việc đã hoàn thành — thứ khiến người dùng tưởng mình vừa làm hỏng gì đó.
    if (lich.status === "COMPLETED") return true;
    setDangCheckout(true);
    setLoiCheckout(null);
    // Checkout là thao tác ĐẮT nhất ở màn này — nó đóng cả lượt khám. Bấm trùng
    // vì mạng rớt mà ghi hai lần thì lịch sử khách có hai lần "đã khám xong".
    const ttCheckout = dinhDanhThaoTac(clinicPatientId, lich.id, "CHECK_OUT");
    const res = await fetch("/api/cskh/tuong-tac", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": khoaThaoTac(ttCheckout),
      },
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
      // Máy chủ TỪ CHỐI (4xx) ⇒ bỏ khoá: chắc chắn chưa ghi gì, và lần bấm lại
      // sau khi sửa là thao tác MỚI. Giữ khoá thì lần ấy nhận 409 "đang được xử
      // lý" và câu giải thích thật biến mất. 5xx/lỗi mạng thì GIỮ — lúc đó không
      // ai biết máy chủ đã ghi tới đâu.
      if (res.status >= 400 && res.status < 500) xongThaoTac(ttCheckout);
      setLoiCheckout(
        nhanLoi(d, `Không đóng được (lỗi ${res.status}).`),
      );
      return false;
    }
    xongThaoTac(ttCheckout);
    router.refresh();
    return true;
  }

  const [dangHoanTac, setDangHoanTac] = useState<string | null>(null);
  const [loiHoanTac, setLoiHoanTac] = useState<string | null>(null);

  /** RÚT LẠI MỘT LẦN CHẠM BẤM NHẦM.
   *
   *  Quang 10/08/2026: *"nhấn vào nút tròn của các sự kiện để hoàn tác… tất
   *  nhiên là log không được xoá, mà là hoàn tác lại tác vụ đó"*.
   *
   *  Backend đặt `huy_luc` trên chính dòng ấy — dòng Ở LẠI, chỉ thôi được tính.
   *  Với `CHECK_IN` nó còn gọi `undo_checkin` để đưa lịch hẹn về CONFIRMED;
   *  `CHECK_OUT` thì từ chối, vì máy trạng thái không có đường ra khỏi
   *  COMPLETED. Xem `TuongTacCskhService.hoan_tac`.
   *
   *  KHÔNG HỎI LẠI (Quang chốt 10/08/2026: *"click vào nút tròn là tự back lại,
   *  không cần xác nhận kiểu vậy"*).
   *
   *  Bản đầu tôi chèn một `window.confirm` vì nút tròn nằm ngay cạnh "Làm lại"
   *  và cả hai đều nhỏ. Nhưng cái giá của một cú rút nhầm THẤP: bấm "Làm bước
   *  này" là ghi lại ngay, và dòng cũ vẫn nằm nguyên trong sổ. Một hộp thoại
   *  chặn đường cho một việc rẻ như thế thì người ta bấm OK theo phản xạ —
   *  tức nó không bảo vệ được gì, chỉ thêm một cú bấm cho MỌI lần dùng đúng.
   *
   *  Hộp thoại xứng đáng ở chỗ mất mát KHÔNG lấy lại được. Đây không phải chỗ
   *  đó — chỗ đó là `CHECK_OUT`, và ở đấy backend từ chối hẳn. */
  async function hoanTac(id: string) {
    setDangHoanTac(id);
    setLoiHoanTac(null);
    const res = await fetch(`/api/cskh/tuong-tac/${id}/hoan-tac`, {
      method: "POST",
    });
    setDangHoanTac(null);
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as {
        error?: string;
        message?: string;
      } | null;
      setLoiHoanTac(nhanLoi(d, `Không hoàn tác được (lỗi ${res.status}).`));
      return;
    }
    router.refresh();
  }

  const [dangGoiNhac, setDangGoiNhac] = useState<string | null>(null);
  const [loiGoiNhac, setLoiGoiNhac] = useState<string | null>(null);

  /** GHI KẾT QUẢ MỘT CUỘC GỌI NHẮC TÁI KHÁM — và đóng việc ấy.
   *
   *  ĐƯỜNG NÀY VẪN MỞ CHO CSKH SUỐT THỜI GIAN QUA, chỉ là không nút nào gọi
   *  tới. Khối "Nhắc tái khám" bị gỡ khỏi màn 09/08/2026 vì nó trùng với ô
   *  "GỌI NHẮC ĐI KHÁM" ở cột phải — nhưng ô ấy chỉ đổi tiêu đề, không đóng
   *  được `nhac_tai_kham`. Hệ quả: chip "Nhắc đi khám hôm nay · quá giờ hẹn"
   *  đỏ vĩnh viễn ở danh sách, và CSKH không có cách nào tắt.
   *
   *  Đo trên staging 10/08/2026: Bùi Lan Hương và Nguyễn Thị Lan đều đang kẹt
   *  đúng như vậy, cả hai đã quá hạn.
   *
   *  Kết quả BẮT BUỘC, và bốn kết quả khác nhau thật: "chuông đổ không ai bắt"
   *  cũng là một việc đã làm, và nó phải khác "đã nói chuyện được" — không phân
   *  biệt thì hôm sau người khác mở lên thấy "đã gọi" rồi bỏ qua một người chưa
   *  ai nói chuyện với. */
  async function ghiGoiNhac(viecId: string, ketQua: string) {
    setDangGoiNhac(viecId + ketQua);
    setLoiGoiNhac(null);
    const res = await fetch(`/api/recall-jobs/${viecId}/ket-qua`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ket_qua: ketQua, ghi_chu: ghiChu.trim() || null }),
    });
    setDangGoiNhac(null);
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as {
        error?: string;
        message?: string;
      } | null;
      setLoiGoiNhac(nhanLoi(d, `Không ghi được (lỗi ${res.status}).`));
      return;
    }
    onGhiChuXong?.();
    router.refresh();
  }

  /** BA NÚT, MỘT SỰ THẬT: lượt khám này ĐÃ XONG.
   *
   *  QUANG 10/08/2026: *"khi ấn tái khám hay checkout hay đặt lịch mới thì bản
   *  chất chúng nó đều là khám xong rồi"*. Khác nhau ở việc LÀM GÌ TIẾP:
   *
   *    Checkout            đóng lượt, hết.
   *    Tái khám            đóng lượt, rồi đặt lịch cho CHÍNH dịch vụ vừa khám —
   *                        "bác sĩ bảo hôm sau khám lại xem con có khoẻ không".
   *                        Lịch mới nối vào lượt này bằng `lich_truoc_id`.
   *    Đặt lịch khám mới   đóng lượt, rồi đặt một lịch cho chuyện KHÁC, ngày
   *                        khác, dịch vụ tự chọn. Không nối chuỗi.
   *
   *  Trước 10/08 chỉ nút đầu đóng lượt; hai nút kia mở thẳng form đặt lịch và
   *  để lượt cũ treo mãi ở CHECKED_IN. Nên khách "đã khám xong" theo lời người
   *  trực mà hệ thống vẫn coi là đang khám — bảng điều phối còn tên họ, và lịch
   *  đặt cho hôm sau bị đọc là chồng lấn với lượt chưa đóng.
   *
   *  CHỈ ĐÓNG KHI ĐANG CHECKED_IN. Lượt còn ở SCHEDULED/CONFIRMED thì khách
   *  chưa từng tới — "khám xong" không đúng với họ, và backend cũng từ chối
   *  (`apply_action("complete")` chỉ nhận từ CHECKED_IN). Lúc ấy đặt lịch vẫn
   *  chạy bình thường, chỉ là không đóng gì cả.
   *
   *  ĐÓNG HỎNG THÌ KHÔNG MỞ FORM. Mở ra rồi đặt xong mà lượt cũ vẫn treo là
   *  đúng cái mớ này sinh ra để dọn. */
  async function ketThucRoiDatLich(kieu: "tai-kham" | "kham-moi") {
    if (lich.status === "CHECKED_IN") {
      const xong = await ghiCheckout();
      if (!xong) return;
    }
    onDatLich?.(kieu);
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
    if (viecCuaLuot.some((v) => v.trang_thai === ma)) return true;
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
          {/* NÚT TRÒN LÀ NÚT HOÀN TÁC — khi và chỉ khi có một dòng để rút.
              Quang 10/08/2026: *"nhấn vào nút tròn của các sự kiện để hoàn tác…
              để phòng trường hợp người ta ấn nhầm"*.
              Không có `lan` thì nó vẫn là một biểu tượng như cũ: rút một thứ
              chưa từng ghi là một cái nút không làm gì, và người dùng sẽ tưởng
              mình vừa làm hỏng cái gì đó. */}
          <VongTron
            xong={xong}
            dang={dang}
            hoanTacDuoc={Boolean(lan?.id)}
            dangHoanTac={dangHoanTac === lan?.id}
            onHoanTac={() => lan?.id && void hoanTac(lan.id)}
          />
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
              <span className="rounded-chip bg-brand-100 px-2 py-0.5 text-label font-bold text-brand-800">
                đang ở đây
              </span>
            )}
            {tt.tuChon && !dang && !xong && (
              <span
                className="rounded-chip bg-surface-sunken px-1.5 py-0.5 text-label font-medium text-ink-muted"
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
              // Cùng vỏ với các lối ra của HangGop — bốn trạng thái này từng
              // là một bản chép tay của nutLoiRa và đã kịp lệch cách vẽ viền.
              className={`${nutLoiRa(chon, xong, dang)} disabled:opacity-50`}
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
            {motCham &&
              loiGhiLoiRa?.ma === tt.ma &&
              dangGhiLoiRa === null && (
                <span className="text-label text-danger">
                  {loiGhiLoiRa.cau}
                </span>
              )}
          </div>

          {/* Việc phải làm — phần sau mũi tên trong đặc tả. */}
          <p className="mt-0.5 text-label leading-snug text-ink-muted">
            {tt.viec}
          </p>

          {lan && (
            <p className="mt-1 text-label leading-snug text-ink-soft">
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
          {/* LƯỢT ĐANG XEM, NÓI RA BẰNG CHỮ.
              Khách có nhiều lượt thì ba cột phải cùng nói về MỘT lượt, và người
              trực phải đọc được mình đang đứng ở lượt nào — bấm sang lượt khác
              trong ô "Lịch sử các lần khám" bên dưới. */}
          {lich.slot_start && (
            <p className="mt-0.5 text-label text-ink-muted">
              Lượt đang xem:{" "}
              <span className="font-medium text-ink-soft">
                {lich.service_name ?? "chưa chọn dịch vụ"} ·{" "}
                {gio(lich.slot_start)}
              </span>
            </p>
          )}
          {/* Sổ chăm sóc không gắn được vào lượt nào — nói ra thay vì lặng lẽ
              tích xanh bằng dữ liệu của lượt khác. Xem `lichSuLuotNay`. */}
          {loiHoanTac && (
            <p className="rounded-md bg-danger-bg px-2 py-1 text-label text-danger">
              {loiHoanTac}
            </p>
          )}
          {khongGanDuocLuot && (
            <p className="mt-1 rounded-md bg-warning-bg px-2 py-1 text-label font-medium text-warning">
              Khách có {lichSu.length} thao tác chăm sóc nhưng màn chưa gắn được
              vào lượt khám nào — chọn một lượt ở “Lịch sử các lần khám” bên
              dưới.
            </p>
          )}
        </div>

        <div className="space-y-3 px-4 py-3">
          {/* Hai cột ở phần trên: chuỗi "trước khám" bên trái, và khối gộp bên
              phải — chỗ trước đây bỏ trống. */}
          <div className="grid gap-x-6 gap-y-3 md:grid-cols-2">
            <div>
              <span className="text-label font-bold uppercase tracking-wide text-ink-faint">
                Trước khám
              </span>
              <ol className="mt-1.5">
                {TRUOC_KHAM.map((tt, i) => (
                  <Node key={tt.ma} tt={tt} cuoi={i === TRUOC_KHAM.length - 1} />
                ))}
              </ol>
            </div>

            <div>
              <span className="text-label font-bold uppercase tracking-wide text-ink-faint">
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
                  onHoanTac={(id) => void hoanTac(id)}
                  dangHoanTac={dangHoanTac}
                  onGhi={(ma, kq) => void ghiLoiRa(ma, kq)}
                  dangGhi={dangGhiLoiRa}
                  loi={loiGhiLoiRa?.ma === "GOI_LAI" ? loiGhiLoiRa.cau : null}
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
                  onHoanTac={(id) => void hoanTac(id)}
                  dangHoanTac={dangHoanTac}
                  // LÝ DO HUỶ LÚC BẤM HUỶ — khác với lý do hỏi được lúc gọi lại.
                  //
                  // Người huỷ lịch đã chọn một mã và có thể đã gõ thêm chữ; cả
                  // hai nằm trên `appointment`, KHÔNG nằm trong sổ chăm sóc,
                  // nên `lan` không bao giờ chứa chúng. Không hiện ở đây thì
                  // người sắp gọi lại đi hỏi đúng câu khách vừa trả lời.
                  ghiChuThem={
                    daHuy &&
                    (lich.ly_do_huy_ma || lich.cancellation_reason) ? (
                      <p className="mt-1 rounded-lg bg-surface-sunken px-2 py-1 text-label leading-snug text-ink-soft">
                        <span className="font-semibold text-ink-muted">
                          Lý do huỷ đã ghi:{" "}
                        </span>
                        {nhanLyDoHuy(lich.ly_do_huy_ma)}
                        {lich.cancellation_reason && (
                          <span className="block italic">
                            “{lich.cancellation_reason}”
                          </span>
                        )}
                        {lich.cancelled_at && (
                          <span className="block font-mono text-ink-muted">
                            huỷ lúc {gio(lich.cancelled_at)}
                          </span>
                        )}
                      </p>
                    ) : null
                  }
                />
              </div>
            </div>
          </div>

          {/* NHẮC TÁI KHÁM — hàng đợi `nhac_tai_kham`, nay bấm được từ đây.
              Xem `ghiGoiNhac` để biết vì sao nó từng không có chỗ nào đóng. */}
          {taiKham.length > 0 && (
            <div>
              <span className="text-label font-bold uppercase tracking-wide text-ink-faint">
                Nhắc tái khám
              </span>
              <div className="mt-1.5 space-y-2">
                {taiKham.map((v) => (
                  <MotViecGoiNhac
                    key={v.id}
                    viec={v}
                    dang={dangGoiNhac}
                    loi={loiGoiNhac}
                    onGhi={(kq) => void ghiGoiNhac(v.id, kq)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* HẸN GỌI LẠI — LỜI HẸN CỦA CHÍNH NGƯỜI TRỰC, HIỆN RA ĐƯỢC.
              Chuông thông báo bắn "Hẹn gọi lại 23:30 ngày 10/08 — Huy" rồi dẫn
              về màn này, và tới 10/08/2026 màn KHÔNG có chỗ nào nói lời hẹn ấy
              là gì: ngày, giờ, lý do đều nằm trong `hen_goi_lai` mà chưa ai
              đọc. Cũng chưa nút nào gọi `PATCH /api/cskh/hen-goi-lai/{id}` nên
              `dong_luc` mãi NULL — việc không bao giờ đóng được. */}
          {henGoiLai.length > 0 && (
            <div id="hen-goi-lai">
              <span className="text-label font-bold uppercase tracking-wide text-ink-faint">
                Đã hẹn gọi lại
              </span>
              <div className="mt-1.5 space-y-2">
                {henGoiLai.map((h) => (
                  <MotLoiHen
                    key={h.id}
                    hen={h}
                    dangDong={dangDongHen === h.id}
                    loi={loiDongHen === h.id ? loiDongHenChu : null}
                    onDong={() => void dongHen(h.id)}
                  />
                ))}
              </div>
            </div>
          )}

          <div>
            <span className="text-label font-bold uppercase tracking-wide text-ink-faint">
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

          {/* KẾT THÚC LƯỢT KHÁM — BA LỐI RA, CÙNG MỘT SỰ THẬT.

              Quang 10/08/2026: *"khi ấn tái khám hay checkout hay đặt lịch mới
              thì bản chất chúng nó đều là khám xong rồi"*. Nay cả ba đều ĐÓNG
              lượt đang xem trước (khi nó đang CHECKED_IN); khác nhau ở việc làm
              gì tiếp — xem `ketThucRoiDatLich`.

              Ghi chú cũ giữ nguyên bên dưới vì phần phân biệt vẫn đúng.
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
            <span className="text-label font-bold uppercase tracking-wide text-ink-faint">
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
                className="inline-flex items-center gap-1.5 rounded-control bg-surface px-2.5 py-1.5 text-label font-semibold text-brand-700 ring-1 ring-inset ring-brand-600 hover:bg-brand-50 disabled:opacity-50"
              >
                <Check className="size-3.5" />
                {daKhamXong
                  ? "Đã checkout"
                  : dangCheckout
                    ? "Đang đóng…"
                    : "Checkout"}
              </button>
              {/* TÁI KHÁM MỞ THEO LƯỢT ĐANG XEM, không theo "khách này từng
                  khám xong lần nào chưa".

                  QUANG 10/08/2026: *"nút tái khám phải ấn được đang bị ẩn hay
                  sao"*. Nó `disabled` thật, và điều kiện cũ (`!lanKhamGanNhat`)
                  sai ở hai mặt cùng lúc:

                    · SAI CẤP. Khối này tên là "Kết thúc lượt khám" — một câu
                      hỏi về LƯỢT — nhưng `lanKhamGanNhat` là sự thật về KHÁCH
                      ("đã từng khám xong lần nào chưa"). Nên nó khoá nút ở
                      chính lượt người trực đang mở, và mở nút ở một lượt đã
                      khám xong từ tháng trước.
                    · SAI VAI. `lanKhamGanNhat` lọc `a.id`, mà `id` xưa nay chỉ
                      được nạp cho vai quản-lý-được-lịch. Với Lễ tân và ba vai
                      Thu ngân nó LUÔN null ⇒ nút mờ vĩnh viễn, kèm một câu
                      title đổ lỗi cho khách ("chưa có lượt khám nào đã xong")
                      ngay khi khách vừa khám xong.

                  Nay chỉ cần có một lượt đang xem: lịch mới nối vào chính lượt
                  ấy bằng `lich_truoc_id`, đúng cái người trực đang nhìn. */}
              <button
                type="button"
                onClick={() => void ketThucRoiDatLich("tai-kham")}
                disabled={!lich.id}
                title={
                  !lich.id
                    ? "Khách chưa có lượt khám nào để nối tiếp"
                    : lich.status === "CHECKED_IN"
                      ? `Đóng lượt này rồi đặt lịch tái khám${
                          lich.service_name
                            ? ` — giữ dịch vụ ${lich.service_name}`
                            : ""
                        }`
                      : `Đặt lịch tái khám nối tiếp lượt đang xem${
                          lich.service_name
                            ? ` — giữ dịch vụ ${lich.service_name}`
                            : ""
                        }`
                }
                className="rounded-control px-2.5 py-1.5 text-label font-medium text-brand-700 ring-1 ring-inset ring-brand-300 hover:bg-brand-50 disabled:opacity-40"
              >
                Tái khám
              </button>
              <button
                type="button"
                onClick={() => void ketThucRoiDatLich("kham-moi")}
                disabled={dangCheckout}
                title={
                  lich.status === "CHECKED_IN"
                    ? "Đóng lượt này rồi đặt một lịch mới cho chuyện khác, ngày khác"
                    : "Đặt một lịch mới cho chuyện khác, ngày khác — không nối chuỗi"
                }
                className="rounded-control px-2.5 py-1.5 text-label font-medium text-ink-soft ring-1 ring-inset ring-line hover:bg-surface-muted disabled:opacity-50"
              >
                Đặt lịch khám mới
              </button>
            </div>
            {/* NÓI RA RẰNG CẢ BA ĐỀU ĐÓNG LƯỢT. Nhìn ba cái nút thì không đoán
                được, và một nút đóng lượt mà không báo là cách người trực đóng
                nhầm rồi không hiểu vì sao khách biến khỏi hàng đợi. */}
            {lich.status === "CHECKED_IN" && (
              <p className="text-label leading-snug text-ink-muted">
                Cả ba nút đều đóng lượt khám đang xem. “Tái khám” đặt tiếp cho
                chính dịch vụ này; “Đặt lịch khám mới” là chuyện khác, ngày khác.
              </p>
            )}
            {loiCheckout && (
              <p className="text-label text-danger">{loiCheckout}</p>
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
