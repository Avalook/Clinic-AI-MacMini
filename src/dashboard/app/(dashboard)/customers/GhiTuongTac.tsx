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
};
const NHAN_KET_QUA: Record<string, string> = {
  ...Object.fromEntries(KET_QUA),
  BO_QUA: "Bỏ qua",
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
  moBanDau = false,
}: {
  clinicPatientId: string;
  appointmentId: string | null;
  phone: string | null;
  /** Loại việc mở sẵn khi timeline bấm vào một node. */
  loaiBanDau?: string | null;
  moBanDau?: boolean;
  /** Nạp SERVER-SIDE rồi truyền xuống — trình biên dịch React chặn setState
   *  đồng bộ trong effect, nên không nạp trong useEffect. */
  lichSuBanDau: DongLichSu[];
}) {
  const router = useRouter();
  const [lichSu, setLichSu] = useState(lichSuBanDau);
  // Hai state này khởi tạo TỪ PROP, và component được gắn `key` theo việc đang
  // ghi — nên bấm một node khác là remount, không cần effect đồng bộ. Trình
  // biên dịch React chặn setState đồng bộ trong effect, và cách này né hẳn nó.
  const [mo, setMo] = useState(moBanDau);
  const [loai, setLoai] = useState(loaiBanDau ?? "NHAC_HEN");
  const [ketQua, setKetQua] = useState("DA_LIEN_HE");
  const [xacNhan, setXacNhan] = useState(false);
  const [noiDung, setNoiDung] = useState("");
  const [dangLuu, setDangLuu] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
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
      <div className="grid grid-cols-2 gap-2">
        {phone ? (
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
        )}
        <button
          type="button"
          onClick={() => setMo((v) => !v)}
          className="inline-flex items-center justify-center rounded-xl border border-line bg-surface py-2 px-3 text-xs font-semibold text-ink-soft hover:bg-surface-muted"
        >
          Ghi kết quả gọi
        </button>
      </div>

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
