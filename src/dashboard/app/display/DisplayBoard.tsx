"use client";

// DisplayBoard — Màn hình TV phòng chờ (image_15 + 2 ảnh V2).
// Hiển thị số đang gọi theo khu vực. KHÔNG hiện tên bệnh nhân (riêng tư).
// Tự refresh mỗi 30s.

// Nhập các hook useEffect và useState từ React để quản lý state và vòng đời component
import { useEffect, useState } from "react";
// Nhập hằng số VN_TZ (múi giờ Việt Nam) từ file datetime
import { VN_TZ } from "../../lib/datetime";

// Định nghĩa interface cho dữ liệu bác sĩ hiển thị
interface DisplayDoctor {
  full_name: string | null; // Tên đầy đủ của bác sĩ, có thể null
}

// Định nghĩa interface cho dữ liệu dịch vụ hiển thị
interface DisplayService {
  name: string | null; // Tên dịch vụ, có thể null
}

// Định nghĩa interface cho dữ liệu lịch hẹn hiển thị
interface DisplayAppt {
  id: string; // ID của lịch hẹn
  slot_start: string; // Thời gian bắt đầu slot
  status: string; // Trạng thái lịch hẹn (CHECKED_IN, IN_PROGRESS...)
  queue_number: string | null; // Số thứ tự trong hàng đợi, có thể null
  booking_channel: string | null; // Kênh đặt lịch (online, trực tiếp...), có thể null
  doctor: DisplayDoctor | null; // Thông tin bác sĩ, có thể null
  service: DisplayService | null; // Thông tin dịch vụ, có thể null
}

// Định nghĩa interface cho props (dữ liệu truyền vào component)
interface Props {
  appts: DisplayAppt[]; // Danh sách lịch hẹn
}

// Định nghĩa danh sách các khu vực hiển thị trên màn hình TV
const ZONES = [
  { key: "kham", label: "Khám bác sĩ", prefix: "C" }, // Khu khám bác sĩ, tiền tố số C
  { key: "sa1", label: "SA1", prefix: "SA" }, // Khu siêu âm 1, tiền tố SA
  { key: "sa2", label: "SA2", prefix: "SA" }, // Khu siêu âm 2, tiền tố SA
  { key: "sa3", label: "SA3", prefix: "SA" }, // Khu siêu âm 3, tiền tố SA
  { key: "xn", label: "Xét nghiệm", prefix: "X" }, // Khu xét nghiệm, tiền tố X
  { key: "tt", label: "Thanh toán", prefix: "T" }, // Khu thanh toán, tiền tố T
] as const; // as const để giữ nguyên kiểu literal

// Hàm xác định khu vực của một lịch hẹn dựa trên tên dịch vụ
function zoneOf(a: DisplayAppt): string {
  // Lấy tên dịch vụ và chuyển thành chữ thường để so sánh
  const svc = (a.service?.name ?? "").toLowerCase();
  // Nếu tên dịch vụ chứa "siêu âm" hoặc "sieu am" (không dấu)
  if (svc.includes("siêu âm") || svc.includes("sieu am")) {
    return "sa"; // Trả về khu siêu âm
  }
  // Nếu tên dịch vụ chứa "xét nghiệm" hoặc "xet nghiem" (không dấu)
  if (svc.includes("xét nghiệm") || svc.includes("xet nghiem")) return "xn"; // Trả về khu xét nghiệm
  return "kham"; // Mặc định trả về khu khám bác sĩ
}

// Component chính DisplayBoard — hiển thị bảng gọi số trên màn hình TV
export default function DisplayBoard({ appts }: Props) {
  // State lưu thời gian hiện tại, khởi tạo với thời điểm render
  const [now, setNow] = useState(() => new Date());

  // useEffect chạy một lần khi component mount
  useEffect(() => {
    // Tạo interval cập nhật thời gian mỗi 30 giây (30_000 ms)
    const t = setInterval(() => setNow(new Date()), 30_000);
    // Cleanup: xóa interval khi component unmount để tránh rò rỉ bộ nhớ
    return () => clearInterval(t);
  }, []); // Mảng dependency rỗng — chỉ chạy một lần

  // Số đang gọi = lịch CHECKED_IN / IN_PROGRESS gần nhất theo giờ
  // Lọc các lịch hẹn có trạng thái CHECKED_IN (đã check-in) hoặc IN_PROGRESS (đang xử lý)
  const called = appts
    .filter((a) => a.status === "CHECKED_IN" || a.status === "IN_PROGRESS")
    // Sắp xếp theo thời gian bắt đầu tăng dần (lịch sớm nhất trước)
    .sort((a, b) => +new Date(a.slot_start) - +new Date(b.slot_start));

  // Hàm lọc danh sách đang gọi theo khu vực (dùng startsWith để khớp "sa1", "sa2"...)
  const byZone = (zone: string) =>
    called.filter((a) => zoneOf(a).startsWith(zone));

  // Định dạng thời gian hiện tại theo giờ Việt Nam (HH:mm)
  const timeStr = now.toLocaleTimeString("vi-VN", {
    hour: "2-digit", // Hiển thị giờ 2 chữ số
    minute: "2-digit", // Hiển thị phút 2 chữ số
    timeZone: VN_TZ, // Múi giờ Việt Nam
  });
  // Định dạng ngày hiện tại theo tiếng Việt (Thứ, ngày/tháng/năm)
  const dateStr = now.toLocaleDateString("vi-VN", {
    weekday: "long", // Hiển thị tên thứ đầy đủ (Thứ Hai, Thứ Ba...)
    day: "2-digit", // Ngày 2 chữ số
    month: "2-digit", // Tháng 2 chữ số
    year: "numeric", // Năm đầy đủ
    timeZone: VN_TZ, // Múi giờ Việt Nam
  });

  return (
    // Container chính: toàn màn hình, nền tối, chữ trắng, bố cục dọc
    <div className="flex h-screen flex-col bg-ink text-white">
      {/* Header */}
      {/* Phần đầu trang: logo + tên + thời gian */}
      <header className="flex items-center justify-between border-b border-white/10 px-8 py-4">
        {/* Phần logo và tên hệ thống */}
        <div className="flex items-center gap-3">
          {/* Logo hình tròn với chữ C */}
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-500 text-lg font-bold">
            C
          </div>
          <div>
            {/* Tên hệ thống */}
            <div className="text-lg font-semibold">ClinicAI</div>
            {/* Mô tả nhỏ */}
            <div className="text-xs text-white/60">CONNECTED CLINIC WORKFLOW</div>
          </div>
        </div>
        {/* Phần hiển thị thời gian và ngày */}
        <div className="text-right">
          {/* Giờ hiện tại, chữ to đậm */}
          <div className="text-3xl font-bold tabular-nums">{timeStr}</div>
          {/* Ngày hiện tại, chữ nhỏ mờ */}
          <div className="text-sm text-white/60">{dateStr}</div>
        </div>
      </header>

      {/* Main: 6 khu */}
      {/* Phần chính: lưới 6 cột hiển thị 6 khu vực */}
      <main className="grid flex-1 grid-cols-3 gap-4 p-6 lg:grid-cols-6">
        {/* Lặp qua từng khu vực trong ZONES */}
        {ZONES.map((z) => {
          // Lấy danh sách lịch đang gọi trong khu vực này
          const rows = byZone(z.key);
          // Lịch đang gọi hiện tại = lịch đầu tiên trong danh sách
          const current = rows[0] ?? null;
          // Danh sách tiếp theo = 3 lịch kế tiếp
          const next = rows.slice(1, 4);
          return (
            // Card của từng khu vực
            <section
              key={z.key} // Key duy nhất cho mỗi khu
              className="flex flex-col rounded-2xl border border-white/10 bg-white/5 p-4"
            >
              {/* Tên khu vực */}
              <h2 className="text-sm font-semibold uppercase tracking-wide text-white/60">
                {z.label}
              </h2>
              {/* Phần hiển thị số đang gọi */}
              <div className="mt-3 flex flex-1 flex-col items-center justify-center">
                {/* Nếu có lịch đang gọi */}
                {current ? (
                  <>
                    {/* Số thứ tự đang gọi, chữ rất to */}
                    <div className="text-5xl font-bold tabular-nums text-brand-300">
                      {current.queue_number ?? "—"}
                    </div>
                    {/* Nhãn "ĐANG GỌI" */}
                    <div className="mt-1 text-xs text-white/60">ĐANG GỌI</div>
                  </>
                ) : (
                  // Nếu không có lịch đang gọi, hiển thị dấu gạch ngang
                  <div className="text-3xl font-bold text-white/20">—</div>
                )}
              </div>
              {/* Phần hiển thị danh sách tiếp theo */}
              <div className="mt-3 border-t border-white/10 pt-2">
                {/* Nhãn "Tiếp theo" */}
                <div className="text-[11px] text-white/40">Tiếp theo</div>
                <div className="mt-1 space-y-0.5">
                  {/* Nếu không có lịch tiếp theo */}
                  {next.length === 0 ? (
                    // Hiển thị dấu gạch ngang
                    <div className="text-xs text-white/30">—</div>
                  ) : (
                    // Lặp qua danh sách tiếp theo và hiển thị số thứ tự
                    next.map((a) => (
                      <div
                        key={a.id} // Key duy nhất cho mỗi lịch
                        className="text-sm font-medium tabular-nums text-white/70"
                      >
                        {a.queue_number ?? "—"} {/* Số thứ tự hoặc dấu gạch ngang */}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </section>
          );
        })}
      </main>

      {/* Footer */}
      {/* Phần chân trang: thông báo và thông tin liên hệ */}
      <footer className="flex items-center justify-between border-t border-white/10 px-8 py-3 text-sm text-white/50">
        {/* Thông báo chờ đến lượt */}
        <div>Vui lòng chờ đến lượt số của mình</div>
        {/* Thông tin WiFi và hotline */}
        <div>WiFi: Dr4Women · Hotline: 1900 0000</div>
      </footer>
    </div>
  );
}