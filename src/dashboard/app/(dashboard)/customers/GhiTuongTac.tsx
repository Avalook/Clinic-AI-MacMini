"use client";

// Gọi xong thì ghi lại — và xem đã gọi mấy lần rồi.
//
// Trước đây nút "📞 Gọi nhắc hẹn" là một thẻ `<a href="tel:…">`: máy quay số,
// rồi thôi. Gọi xong không ai biết đã gọi; gọi lần hai không ai biết là lần
// hai; và cột "Tương tác gần nhất" hiện "—" cho mọi khách.
//
// GIỮ NGUYÊN THẺ tel: — nó là thứ làm cho điện thoại quay số, và bỏ đi thì
// CSKH phải tự bấm 10 chữ số. Chỉ thêm: bấm xong thì mở ô ghi kết quả.

import { useState } from "react";
import { useRouter } from "next/navigation";

// Ba dòng giữa là KNM / KLLD / Hẹn GLS trong DoD — Quang giải nghĩa 08/08:
// không nghe máy, không liên lạc được, hẹn gọi lại sau. Cả ba sinh ra việc
// "cần gọi lại", nhưng chúng KHÁC nhau và gộp lại là mất thông tin: KLLD thì
// phải đi tìm số khác, còn Hẹn GLS là khách chủ động hẹn giờ.
const KET_QUA: [string, string][] = [
  ["DA_LIEN_HE", "Đã liên hệ được"],
  ["CHUA_NGHE_MAY", "Không nghe máy (KNM)"],
  ["KHONG_LIEN_LAC_DUOC", "Không liên lạc được (KLLD)"],
  ["HEN_GOI_LAI", "Khách hẹn gọi lại sau"],
  ["CAN_BAC_SI", "Cần hỏi bác sĩ"],
  ["TU_CHOI", "Khách từ chối"],
];

const LOAI: [string, string][] = [
  ["XAC_NHAN_LICH", "Gọi xác nhận lịch"],
  ["NHAC_HEN", "Gọi nhắc hẹn"],
  ["TRA_KQ", "Gọi trả kết quả"],
  ["CHECK_XN", "Hỏi đơn vị xét nghiệm"],
  ["HOI_LY_DO_HUY", "Hỏi lý do huỷ"],
  ["HOI_THAM", "Gọi hỏi thăm"],
  ["KHAC", "Việc khác"],
];

// Ba loại này luôn nói về MỘT lịch cụ thể — khớp CHECK trong 20260809000003.
// Không có lịch thì không cho chọn, thay vì để backend trả lỗi sau khi gõ xong.
const CAN_LICH = new Set(["XAC_NHAN_LICH", "NHAC_HEN", "HOI_LY_DO_HUY"]);

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
    oKhoiKhac: "Nhắc tái khám",
  },
  NHAC_DI_KHAM: {
    tieuDe: "Gọi nhắc đi khám",
    loai: "HOI_THAM",
    goiKhach: true,
    zalo: null,
    oKhoiKhac: "Nhắc tái khám",
  },
};

const MAC_DINH: HanhDongViec = {
  tieuDe: "Gọi khách & ghi tương tác",
  loai: "NHAC_HEN",
  goiKhach: true,
  zalo: "NHAC_HEN",
};

export interface DongLichSu {
  xay_ra_luc: string;
  loai: string;
  kenh: string;
  ket_qua: string | null;
  khach_xac_nhan: boolean | null;
  noi_dung: string | null;
  nhan_vien: string | null;
  nguon: string;
}

const NHAN_LOAI: Record<string, string> = {
  ...Object.fromEntries(LOAI),
  MOI_TAI_KHAM: "Mời tái khám",
  NHAC_DI_KHAM: "Nhắc đi khám",
  CHECK_IN: "Check-in",
  CHECK_OUT: "Check-out",
  THANH_TOAN: "Thanh toán",
  MUA_THUOC: "Mua thuốc",
};
const NHAN_KET_QUA: Record<string, string> = {
  ...Object.fromEntries(KET_QUA),
  BO_QUA: "Bỏ qua",
  GHI_NHAN: "Đã ghi nhận",
};

function gio(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

export default function GhiTuongTac({
  clinicPatientId,
  appointmentId,
  phone,
  lichSuBanDau,
  loaiBanDau,
  viecHienTai,
  moBanDau = false,
  zaloBat = false,
  zaloThieu = [],
}: {
  clinicPatientId: string;
  appointmentId: string | null;
  phone: string | null;
  /** Việc gấp nhất đang mở của khách (`v_trang_thai_cskh.trang_thai`). Quyết
   *  định khối này bày ra những nút nào. */
  viecHienTai?: string | null;
  /** Loại việc mở sẵn khi timeline bấm vào một node. */
  loaiBanDau?: string | null;
  moBanDau?: boolean;
  /** Zalo đã đủ cấu hình chưa — hỏi backend, không đoán ở đây. */
  zaloBat?: boolean;
  zaloThieu?: string[];
  /** Nạp SERVER-SIDE rồi truyền xuống — trình biên dịch React chặn setState
   *  đồng bộ trong effect, nên không nạp trong useEffect. */
  lichSuBanDau: DongLichSu[];
}) {
  const router = useRouter();
  const [lichSu, setLichSu] = useState(lichSuBanDau);
  // Hai state này khởi tạo TỪ PROP, và component được gắn `key` theo việc đang
  // ghi — nên bấm một node khác là remount, không cần effect đồng bộ. Trình
  // biên dịch React chặn setState đồng bộ trong effect, và cách này né hẳn nó.
  // Bước trên chuỗi mà người dùng vừa bấm THẮNG việc gấp nhất do view suy ra:
  // họ vừa nói ra mình muốn làm gì.
  const hanhDong =
    (loaiBanDau ? null : viecHienTai ? HANH_DONG[viecHienTai] : null) ??
    MAC_DINH;

  const [mo, setMo] = useState(moBanDau);
  const [loai, setLoai] = useState(loaiBanDau ?? hanhDong.loai);
  const [ketQua, setKetQua] = useState("DA_LIEN_HE");
  const [xacNhan, setXacNhan] = useState(false);
  const [noiDung, setNoiDung] = useState("");
  const [dangLuu, setDangLuu] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangGuiZalo, setDangGuiZalo] = useState<string | null>(null);
  const [ketQuaZalo, setKetQuaZalo] = useState<string | null>(null);
  const [moHen, setMoHen] = useState(false);
  const [ngayHen, setNgayHen] = useState("");
  const [lyDoHen, setLyDoHen] = useState("");
  const [daHen, setDaHen] = useState(false);

  const thieuLich = CAN_LICH.has(loai) && !appointmentId;

  async function luu() {
    setDangLuu(true);
    setLoi(null);
    const res = await fetch("/api/cskh/tuong-tac", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clinic_patient_id: clinicPatientId,
        appointment_id: CAN_LICH.has(loai) ? appointmentId : null,
        loai,
        kenh: "GOI",
        ket_qua: ketQua,
        khach_xac_nhan:
          loai === "XAC_NHAN_LICH" || loai === "NHAC_HEN" ? xacNhan : null,
        noi_dung: noiDung.trim() || null,
      }),
    });
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as
        | { error?: string; message?: string }
        | null;
      setLoi(d?.message ?? d?.error ?? "Không ghi được.");
      setDangLuu(false);
      return;
    }
    // Đọc lại từ server thay vì tự dựng dòng mới ở đây: giờ giấc và tên người
    // ghi do database quyết, và bịa chúng ở trình duyệt là cách để hai bên
    // hiển thị hai thứ khác nhau.
    const ls = await fetch(
      `/api/cskh/tuong-tac?clinic_patient_id=${encodeURIComponent(clinicPatientId)}`,
    );
    if (ls.ok) {
      const d = (await ls.json()) as { items?: DongLichSu[] };
      setLichSu(d.items ?? []);
    }
    // NẠP LẠI CẢ TRANG, không chỉ danh sách trong ô này.
    //
    // Chuỗi bước bên trái đọc dữ liệu do máy chủ nạp, nên `setLichSu` ở đây chỉ
    // làm mới đúng cái danh sách nhỏ này: ghi xong một bước mà node vẫn sáng
    // "Làm bước này", và người dùng bấm lần nữa. Đo được đúng lỗi ấy trên bản
    // thật ngày 08/08 — dòng đã vào database mà màn không nhúc nhích.
    router.refresh();
    setDangLuu(false);
    setMo(false);
    setNoiDung("");
  }

  async function guiZalo(loaiTin: "NHAC_HEN" | "TRA_KET_QUA") {
    setDangGuiZalo(loaiTin);
    setKetQuaZalo(null);
    const res = await fetch("/api/cskh/zalo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clinic_patient_id: clinicPatientId,
        loai_tin: loaiTin,
        appointment_id: appointmentId,
      }),
    });
    setDangGuiZalo(null);
    const d = (await res.json().catch(() => null)) as
      | { da_gui?: boolean; chi_tiet?: string; error?: string; message?: string }
      | null;
    if (res.ok && d?.da_gui) {
      setKetQuaZalo("Đã gửi Zalo cho khách.");
      // Gửi xong sinh một dòng trong sổ tương tác — nạp lại để chuỗi bước tích lên.
      router.refresh();
      return;
    }
    // KHÔNG nói "đã gửi" khi chưa chắc. `chi_tiet` từ backend đã dịch sẵn mã
    // lỗi của Zalo sang tiếng Việt.
    setKetQuaZalo(
      d?.chi_tiet ?? d?.message ?? d?.error ?? "Không gửi được — hãy gọi điện.",
    );
  }

  async function henGoiLai() {
    setDangLuu(true);
    setLoi(null);
    const res = await fetch("/api/cskh/hen-goi-lai", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clinic_patient_id: clinicPatientId,
        ngay_goi: ngayHen,
        ly_do: lyDoHen.trim(),
      }),
    });
    setDangLuu(false);
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as
        | { error?: string; message?: string }
        | null;
      setLoi(d?.message ?? d?.error ?? "Không hẹn được.");
      return;
    }
    // Cờ tại chỗ để nút đổi NGAY. Trang chỉ nạp lại trạng thái ở lần tải sau,
    // và một nút bấm xong trông y như chưa bấm là một nút sẽ bị bấm hai lần.
    router.refresh();
    setDaHen(true);
    setMoHen(false);
    setLyDoHen("");
  }

  return (
    <div className="space-y-2">
      {/* Bước này chạm tới ai — hiện khi KHÔNG phải gọi khách. */}
      {hanhDong.nhacNho && (
        <p className="rounded-lg bg-warning-bg px-2 py-1.5 text-[11px] leading-snug text-warning">
          {hanhDong.nhacNho}
        </p>
      )}
      {hanhDong.oKhoiKhac && (
        <p className="rounded-lg bg-surface-muted px-2 py-1.5 text-[11px] leading-snug text-ink-soft">
          Việc này ghi ở khối <b>{hanhDong.oKhoiKhac}</b> trong vùng làm việc —
          ghi ở đó thì việc mới đóng lại.
        </p>
      )}

      <div className="grid grid-cols-2 gap-2">
        {/* Nút quay số CHỈ hiện ở bước thật sự gọi cho khách. */}
        {hanhDong.goiKhach ? (
          phone ? (
            <a
              href={`tel:${phone}`}
              onClick={() => setMo(true)}
              className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-brand-300 bg-white py-2 px-3 font-semibold text-brand-700 shadow-xs transition-colors hover:bg-brand-50"
            >
              📞 Gọi
            </a>
          ) : (
            <button
              disabled
              type="button"
              className="inline-flex cursor-not-allowed items-center justify-center gap-1.5 rounded-xl border border-line bg-surface-muted py-2 px-3 font-semibold text-ink-muted opacity-60"
            >
              📞 Chưa có SĐT
            </button>
          )
        ) : null}
        <button
          type="button"
          onClick={() => setMo((v) => !v)}
          className={`inline-flex items-center justify-center rounded-xl py-2 px-3 text-xs font-semibold ${
            hanhDong.goiKhach
              ? "border border-line bg-surface text-ink-soft hover:bg-surface-muted"
              : "col-span-2 bg-brand-600 text-white hover:bg-brand-700"
          }`}
        >
          {hanhDong.goiKhach ? "Ghi kết quả gọi" : `Ghi kết quả — ${hanhDong.tieuDe}`}
        </button>
      </div>

      {/* GỬI ZALO THẬT — và CHỈ mẫu tin hợp với bước đang làm.
          Nút LUÔN HIỆN khi bước này có mẫu, nhưng khoá lúc chưa cấu hình và nói
          thiếu gì: ẩn hẳn thì người dùng không biết tính năng tồn tại; hiện mà
          bấm vào báo lỗi thì họ tưởng hệ thống hỏng.
          Bỏ hẳn ở bước không có mẫu nào đúng — "Zalo báo có KQ" ở bước hỏi lý
          do huỷ là một tin nhắn sai gửi cho khách thật. */}
      {hanhDong.zalo === "NHAC_HEN" && (
        <button
          type="button"
          disabled={!zaloBat || dangGuiZalo !== null || !appointmentId}
          onClick={() => void guiZalo("NHAC_HEN")}
          title={!appointmentId ? "Khách chưa có lịch hẹn nào" : undefined}
          className="inline-flex w-full items-center justify-center rounded-xl border border-line bg-surface py-1.5 px-2 text-[11px] font-semibold text-ink-soft hover:bg-surface-muted disabled:opacity-50"
        >
          {dangGuiZalo === "NHAC_HEN" ? "Đang gửi…" : "💬 Zalo nhắc hẹn"}
        </button>
      )}
      {hanhDong.zalo === "TRA_KET_QUA" && (
        <button
          type="button"
          disabled={!zaloBat || dangGuiZalo !== null}
          onClick={() => void guiZalo("TRA_KET_QUA")}
          className="inline-flex w-full items-center justify-center rounded-xl border border-line bg-surface py-1.5 px-2 text-[11px] font-semibold text-ink-soft hover:bg-surface-muted disabled:opacity-50"
        >
          {dangGuiZalo === "TRA_KET_QUA" ? "Đang gửi…" : "💬 Zalo báo có KQ"}
        </button>
      )}
      {hanhDong.zalo && !zaloBat && (
        <p className="text-[11px] text-ink-faint">
          Zalo chưa nối{zaloThieu.length > 0 && ` — thiếu ${zaloThieu.join(", ")}`}.
          Gọi điện cho khách và ghi kết quả gọi.
        </p>
      )}
      {ketQuaZalo && (
        <p className="text-[11px] text-ink-soft">{ketQuaZalo}</p>
      )}

      {mo && (
        <div className="space-y-2 rounded-xl border border-line bg-surface-muted p-3">
          <label className="block text-[11px] font-medium text-ink-soft">
            Việc gì
            <select
              value={loai}
              onChange={(e) => setLoai(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-xs text-ink"
            >
              {LOAI.map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-[11px] font-medium text-ink-soft">
            Kết quả
            <select
              value={ketQua}
              onChange={(e) => setKetQua(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-xs text-ink"
            >
              {KET_QUA.map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>

          {(loai === "XAC_NHAN_LICH" || loai === "NHAC_HEN") && (
            <label className="flex items-center gap-2 text-[11px] text-ink-soft">
              <input
                type="checkbox"
                checked={xacNhan}
                onChange={(e) => setXacNhan(e.target.checked)}
                className="size-3.5 accent-[var(--color-brand-600)]"
              />
              Khách nói sẽ đến
            </label>
          )}

          <input
            value={noiDung}
            onChange={(e) => setNoiDung(e.target.value)}
            placeholder="Khách nói gì (không bắt buộc)"
            className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-xs text-ink"
          />

          {thieuLich && (
            <p className="text-[11px] text-warning">
              Việc này gắn với một lịch hẹn, mà khách đang không có lịch nào.
            </p>
          )}
          {loi && <p className="text-[11px] text-danger">{loi}</p>}

          <button
            type="button"
            onClick={() => void luu()}
            disabled={dangLuu || thieuLich}
            className="w-full rounded-lg bg-brand-600 py-1.5 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {dangLuu ? "Đang ghi…" : "Ghi lại"}
          </button>
        </div>
      )}

      {/* HẸN GỌI LẠI — chỗ đựng việc hệ thống chưa suy được.
          "Sau sinh 1 tháng" và "sau thủ thuật 1 ngày" trong DoD không có dữ
          liệu để tự sinh: không cột nào chứa ngày sinh con thật, và các dịch
          vụ thủ thuật đang tắt. Một nút để người gõ thì có việc THẬT; một tab
          tự sinh từ ngày dự sinh thì có việc SAI. */}
      {daHen ? (
        <p className="rounded-lg bg-success-bg px-2 py-1.5 text-[11px] text-success">
          Đã hẹn gọi lại. Khách sẽ hiện ở danh sách vào đúng ngày đó.
        </p>
      ) : moHen ? (
        <div className="space-y-2 rounded-xl border border-line bg-surface-muted p-3">
          <label className="block text-[11px] font-medium text-ink-soft">
            Gọi lại ngày
            <input
              type="date"
              value={ngayHen}
              onChange={(e) => setNgayHen(e.target.value)}
              className="mt-1 w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-xs text-ink"
            />
          </label>
          <input
            value={lyDoHen}
            onChange={(e) => setLyDoHen(e.target.value)}
            placeholder="Gọi lại để làm gì (VD: hỏi thăm sau thủ thuật)"
            className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-xs text-ink"
          />
          <button
            type="button"
            onClick={() => void henGoiLai()}
            disabled={dangLuu || !ngayHen || !lyDoHen.trim()}
            className="w-full rounded-lg bg-brand-600 py-1.5 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {dangLuu ? "Đang hẹn…" : "Hẹn"}
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setMoHen(true)}
          className="w-full rounded-xl border border-line bg-surface py-1.5 text-[11px] font-semibold text-ink-soft hover:bg-surface-muted"
        >
          Hẹn gọi lại ngày…
        </button>
      )}

      <div>
        <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">
          Đã tương tác {lichSu.length} lần
        </p>
        {lichSu.length === 0 ? (
          <p className="mt-1 text-[11px] text-ink-faint">
            Chưa có lần nào được ghi lại.
          </p>
        ) : (
          <ul className="mt-1 space-y-1">
            {lichSu.slice(0, 8).map((d, i) => (
              <li
                key={`${d.xay_ra_luc}-${i}`}
                className="border-l-2 border-line pl-2 text-[11px] leading-snug text-ink-soft"
              >
                <span className="font-mono text-ink-faint">
                  {gio(d.xay_ra_luc)}
                </span>{" "}
                <span className="text-ink">{NHAN_LOAI[d.loai] ?? d.loai}</span>
                {d.ket_qua && ` · ${NHAN_KET_QUA[d.ket_qua] ?? d.ket_qua}`}
                {d.khach_xac_nhan === true && " · khách sẽ đến"}
                {d.nhan_vien && ` · ${d.nhan_vien}`}
                {d.noi_dung && (
                  <span className="block text-ink-muted">{d.noi_dung}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
