"use client";

// Cấu hình luật "dịch vụ X + khách mới → bắt buộc bác sĩ Y".
//
// Thay cho việc ghi cứng tên bác sĩ trong migration — cách ấy đã thử một lần và
// khớp 0 dòng ở mọi phòng khám, kể cả chính Dr4Women, vì tên trong database đã
// đổi giữa chừng.
//
// XEM THỬ TRƯỚC KHI LƯU. Ba cách tính "khách mới" cho ba con số khác nhau trên
// cùng một tập bệnh nhân, và không có đáp án đúng phổ quát. Quản lý cần THẤY
// hậu quả — "cách này coi 41/54 khách là mới" — chứ không phải lưu rồi chờ
// khách phàn nàn.

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck, Trash2, TriangleAlert } from "lucide-react";

export interface LuatBacSi {
  id: string;
  service_type_id: string;
  ten_dich_vu: string;
  ma_dich_vu: string;
  required_staff_id: string;
  ten_bac_si: string;
  cach_tinh: "CHUA_TUNG" | "DOT_MOI" | "QUA_N_THANG";
  so_thang: number | null;
  chan_han: boolean;
  is_active: boolean;
  ghi_chu: string | null;
}

export interface Opt {
  id: string;
  label: string;
}

const CACH_TINH: { ma: LuatBacSi["cach_tinh"]; nhan: string; giai_thich: string }[] = [
  {
    ma: "DOT_MOI",
    nhan: "Chưa có đợt chăm sóc đang mở",
    giai_thich:
      "Cùng dịch vụ nhưng vấn đề khác thì tính là khách mới. Hợp với cách phòng khám nghĩ.",
  },
  {
    ma: "CHUA_TUNG",
    nhan: "Chưa từng khám dịch vụ này",
    giai_thich: "Chặt nhất. Khám một lần rồi thì mãi mãi là khách cũ.",
  },
  {
    ma: "QUA_N_THANG",
    nhan: "Chưa khám trong N tháng gần đây",
    giai_thich: "Khách cũ lâu ngày quay lại vẫn phải qua bác sĩ bắt buộc.",
  },
];

export default function LuatBacSiCard({
  services,
  doctors,
  luat,
}: {
  services: Opt[];
  doctors: Opt[];
  /** Nạp sẵn từ trang (server component). Không fetch lúc gắn: trang này vốn
   *  đã chạy phía máy chủ, nên một lượt gọi nữa từ trình duyệt chỉ làm thẻ
   *  nhấp nháy "Đang đọc…" rồi mới có nội dung. Sau khi lưu/gỡ thì
   *  `router.refresh()` nạp lại từ chính máy chủ. */
  luat: LuatBacSi[];
}) {
  const router = useRouter();
  const [loi, setLoi] = useState<string | null>(null);
  const [dangLuu, setDangLuu] = useState(false);

  const [dichVu, setDichVu] = useState("");
  const [bacSi, setBacSi] = useState("");
  const [cachTinh, setCachTinh] = useState<LuatBacSi["cach_tinh"]>("DOT_MOI");
  const [soThang, setSoThang] = useState(12);
  const [chanHan, setChanHan] = useState(true);
  // Gắn kèm dịch vụ mà con số này thuộc về. Không có nó thì lúc đổi dịch vụ,
  // con số của dịch vụ CŨ vẫn nằm đó cho tới khi lượt đếm mới trả lời — và
  // quản lý sẽ quyết định dựa trên một con số của việc khác.
  const [xemThu, setXemThu] = useState<{
    svc: string;
    khach_moi: number;
    tong: number;
  } | null>(null);

  // Đếm lại mỗi khi đổi dịch vụ hoặc cách tính — đây là thứ giúp quản lý chọn.
  useEffect(() => {
    // Không `setXemThu(null)` ở đây: gán state đồng bộ trong thân effect bị
    // React compiler chặn (nó kéo theo một lượt render thừa). Con số cũ được
    // lọc ở chỗ hiển thị bằng cách so `svc`.
    if (!dichVu) return;
    let bo = false;
    const q = new URLSearchParams({
      xem_thu: "1",
      service_type_id: dichVu,
      cach_tinh: cachTinh,
    });
    if (cachTinh === "QUA_N_THANG") q.set("so_thang", String(soThang));
    fetch(`/api/booking-rules/doctor?${q.toString()}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { khach_moi: number; tong: number } | null) => {
        if (!bo && d) setXemThu({ svc: dichVu, ...d });
      })
      .catch(() => {});
    return () => {
      bo = true;
    };
  }, [dichVu, cachTinh, soThang]);

  async function luuLuat() {
    if (!dichVu || !bacSi) {
      setLoi("Chọn dịch vụ và bác sĩ bắt buộc.");
      return;
    }
    setDangLuu(true);
    setLoi(null);
    const res = await fetch("/api/booking-rules/doctor", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        service_type_id: dichVu,
        required_staff_id: bacSi,
        cach_tinh: cachTinh,
        so_thang: cachTinh === "QUA_N_THANG" ? soThang : null,
        chan_han: chanHan,
        is_active: true,
      }),
    });
    setDangLuu(false);
    if (!res.ok) {
      const chiTiet = await res
        .json()
        .then((d: { error?: string; detail?: string }) => d.error ?? d.detail)
        .catch(() => null);
      setLoi(chiTiet ?? `Không lưu được (lỗi ${res.status}).`);
      return;
    }
    setDichVu("");
    setBacSi("");
    router.refresh();
  }

  async function xoaLuat(id: string) {
    const res = await fetch("/api/booking-rules/doctor", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    if (!res.ok) {
      setLoi("Không gỡ được luật này.");
      return;
    }
    setLoi(null);
    router.refresh();
  }

  const moTa = CACH_TINH.find((c) => c.ma === cachTinh);

  return (
    <section className="space-y-4 rounded-card border border-line bg-surface p-4 shadow-card">
      <header>
        <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <ShieldCheck size={16} className="text-brand-600" aria-hidden="true" />
          Bắt buộc bác sĩ theo dịch vụ
        </h2>
        <p className="mt-1 text-xs text-ink-muted">
          Khách <strong>mới</strong> của dịch vụ này phải khám đúng bác sĩ được
          chọn. Luật áp <strong>ngay lúc đặt lịch</strong>, không phải khi khách
          đã tới nơi.
        </p>
      </header>

      {/* Danh sách luật đang có */}
      {luat.length === 0 ? (
        <p className="rounded-control bg-surface-muted px-3 py-2 text-xs text-ink-muted">
          Chưa có luật nào. Mọi dịch vụ đều đặt được với bất kỳ bác sĩ nào.
        </p>
      ) : (
        <ul className="divide-y divide-line-soft rounded-control border border-line-soft">
          {luat.map((l) => (
            <li key={l.id} className="flex flex-wrap items-center gap-2 px-3 py-2 text-xs">
              <span className="font-semibold text-ink">{l.ten_dich_vu}</span>
              <span className="text-ink-muted">→</span>
              <span className="text-ink">{l.ten_bac_si}</span>
              <span className="rounded-chip bg-surface-muted px-2 py-0.5 text-ink-soft">
                {CACH_TINH.find((c) => c.ma === l.cach_tinh)?.nhan ?? l.cach_tinh}
                {l.so_thang ? ` · ${l.so_thang} tháng` : ""}
              </span>
              {!l.chan_han && (
                <span className="rounded-chip bg-warning-bg px-2 py-0.5 text-warning">
                  chỉ cảnh báo
                </span>
              )}
              {!l.is_active && (
                <span className="rounded-chip bg-surface-sunken px-2 py-0.5 text-ink-muted">
                  đang tắt
                </span>
              )}
              <button
                type="button"
                onClick={() => xoaLuat(l.id)}
                aria-label={`Gỡ luật của ${l.ten_dich_vu}`}
                className="ml-auto rounded-control p-1 text-ink-muted transition-colors hover:bg-danger-bg hover:text-danger"
              >
                <Trash2 size={14} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}

      {/* Thêm / sửa */}
      <div className="grid gap-3 rounded-control border border-line-soft p-3 sm:grid-cols-2">
        <label className="grid gap-1 text-xs">
          <span className="text-ink-soft">Dịch vụ</span>
          <select
            value={dichVu}
            onChange={(e) => setDichVu(e.target.value)}
            className="h-9 rounded-control border border-line bg-surface px-2 text-sm text-ink outline-none focus:border-brand-600"
          >
            <option value="">— Chọn dịch vụ —</option>
            {services.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </label>

        <label className="grid gap-1 text-xs">
          <span className="text-ink-soft">Bắt buộc khám bác sĩ</span>
          <select
            value={bacSi}
            onChange={(e) => setBacSi(e.target.value)}
            className="h-9 rounded-control border border-line bg-surface px-2 text-sm text-ink outline-none focus:border-brand-600"
          >
            <option value="">— Chọn bác sĩ —</option>
            {doctors.map((d) => (
              <option key={d.id} value={d.id}>
                {d.label}
              </option>
            ))}
          </select>
        </label>

        <label className="grid gap-1 text-xs sm:col-span-2">
          <span className="text-ink-soft">Tính là “khách mới” khi</span>
          <select
            value={cachTinh}
            onChange={(e) =>
              setCachTinh(e.target.value as LuatBacSi["cach_tinh"])
            }
            className="h-9 rounded-control border border-line bg-surface px-2 text-sm text-ink outline-none focus:border-brand-600"
          >
            {CACH_TINH.map((c) => (
              <option key={c.ma} value={c.ma}>
                {c.nhan}
              </option>
            ))}
          </select>
          {moTa && <span className="text-ink-muted">{moTa.giai_thich}</span>}
        </label>

        {cachTinh === "QUA_N_THANG" && (
          <label className="grid gap-1 text-xs">
            <span className="text-ink-soft">Số tháng</span>
            <input
              type="number"
              min={1}
              max={120}
              value={soThang}
              onChange={(e) => setSoThang(Number(e.target.value) || 1)}
              className="h-9 w-28 rounded-control border border-line bg-surface px-2 text-sm text-ink outline-none focus:border-brand-600"
            />
          </label>
        )}

        <label className="flex items-center gap-2 text-xs text-ink-soft sm:col-span-2">
          <input
            type="checkbox"
            checked={chanHan}
            onChange={(e) => setChanHan(e.target.checked)}
            className="size-4 accent-brand-600"
          />
          Chặn hẳn khi đặt sai bác sĩ.{" "}
          <span className="text-ink-muted">
            Bỏ tick thì chỉ cảnh báo — dùng khi mới bật luật lần đầu, để xem nó
            bắt đúng không trước khi cho nó từ chối khách.
          </span>
        </label>

        {/* Hậu quả, trước khi lưu */}
        {xemThu && xemThu.svc === dichVu && (
          <p className="sm:col-span-2 rounded-control bg-brand-wash px-3 py-2 text-xs text-brand-ink">
            Với cách tính này, <strong>{xemThu.khach_moi}</strong> trên{" "}
            {xemThu.tong} hồ sơ hiện có được coi là khách mới của dịch vụ đã chọn.
          </p>
        )}

        {loi && (
          <p className="sm:col-span-2 flex items-start gap-1.5 rounded-control bg-danger-bg px-3 py-2 text-xs text-danger">
            <TriangleAlert size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
            {loi}
          </p>
        )}

        <div className="sm:col-span-2">
          <button
            type="button"
            onClick={luuLuat}
            disabled={dangLuu}
            className="rounded-control bg-brand-600 px-4 py-2 text-sm font-medium text-surface transition-colors hover:bg-brand-700 disabled:opacity-50"
          >
            {dangLuu ? "Đang lưu…" : "Lưu luật"}
          </button>
        </div>
      </div>
    </section>
  );
}
