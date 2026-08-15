"use client";

// Luật đặt lịch của phòng khám — chỉ Trưởng ca + Quản lý sửa được (C.3 write path).
// Hiển thị 3 con số hiện tại (từ BookingPolicyContext, đọc một lần ở layout) và
// cho phép đổi chúng. Sau khi lưu → router.refresh() để layout đọc lại policy mới
// và mọi lưới khung giờ phía dưới vẽ theo luật mới.

// Nhập hook useState từ React để quản lý state
import { useState } from "react";
// Nhập hook useRouter từ Next.js để điều hướng và refresh
import { useRouter } from "next/navigation";
// Nhập kiểu dữ liệu BookingPolicy từ file booking-policy
import type { BookingPolicy } from "../../../lib/booking-policy";
// Nhập các hằng số style INPUT, LABEL, BTN từ file form-ui
import { INPUT, LABEL, BTN } from "../form-ui";

// Danh sách các lựa chọn độ dài khung giờ (phút)
const SLOT_OPTIONS = [5, 10, 15, 20, 30, 60];

// Component chính BookingPolicyCard — hiển thị và chỉnh sửa luật đặt lịch
export default function BookingPolicyCard({
  policy, // Luật đặt lịch hiện tại, có thể null
}: {
  policy: BookingPolicy | null;
}) {
  // Hook useRouter để refresh trang sau khi lưu
  const router = useRouter();
  // State: độ dài khung giờ (mặc định 15 phút)
  const [slotMinutes, setSlotMinutes] = useState(policy?.slotMinutes ?? 15);
  // State: số chỗ đặt hẹn mỗi khung (mặc định 2)
  const [regularCap, setRegularCap] = useState(policy?.regularCap ?? 2);
  // State: số chỗ vãng lai mỗi khung (mặc định 1)
  const [walkinCap, setWalkinCap] = useState(policy?.walkinCap ?? 1);
  // State: trạng thái đang lưu
  const [busy, setBusy] = useState(false);
  // State: thông báo kết quả (thành công hoặc lỗi)
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(
    null,
  );

  // Nếu chưa có dữ liệu policy
  if (!policy) {
    return (
      // Hiển thị thông báo chưa đọc được luật
      <div className="rounded-card border border-line bg-surface p-5 shadow-card">
        <h2 className="text-base font-semibold text-ink">Luật đặt lịch</h2>
        <p className="mt-2 text-sm text-ink-muted">
          Chưa đọc được luật đặt lịch của phòng khám — tải lại trang rồi thử lại.
        </p>
      </div>
    );
  }

  // Hàm lưu luật đặt lịch mới
  async function save() {
    setBusy(true); // Bật trạng thái đang lưu
    setMsg(null); // Xóa thông báo cũ
    // Gửi PATCH request đến API để cập nhật luật
    const res = await fetch("/api/booking-policy", {
      method: "PATCH", // Phương thức PATCH
      headers: { "content-type": "application/json" }, // Định dạng JSON
      body: JSON.stringify({ // Body chứa 3 con số mới
        slot_minutes: slotMinutes, // Độ dài khung giờ
        regular_cap: regularCap, // Số chỗ đặt hẹn
        walkin_cap: walkinCap, // Số chỗ vãng lai
      }),
    });
    // Parse response JSON
    const data = (await res.json()) as { ok?: boolean; error?: string };
    setBusy(false); // Tắt trạng thái đang lưu
    // Nếu request thất bại hoặc backend trả lỗi
    if (!res.ok || !data.ok) {
      // Hiển thị thông báo lỗi
      setMsg({ kind: "err", text: data.error ?? `Lỗi máy chủ (${res.status})` });
      return; // Dừng
    }
    // Hiển thị thông báo thành công
    setMsg({ kind: "ok", text: "Đã lưu luật đặt lịch mới." });
    router.refresh(); // Refresh trang để layout đọc lại policy mới
  }

  return (
    // Card chính hiển thị luật đặt lịch
    <div className="rounded-card border border-line bg-surface p-5 shadow-card">
      {/* Tiêu đề */}
      <h2 className="text-base font-semibold text-ink">Luật đặt lịch</h2>
      {/* Mô tả */}
      <p className="mt-1 text-sm text-ink-muted">
        Áp dụng cho phòng khám này. Thay đổi có hiệu lực ngay — mọi lưới khung
        giờ và trigger chống quá tải đọc cùng một cấu hình.
      </p>

      {/* Lưới 3 cột cho 3 trường nhập liệu */}
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
        {/* Trường: độ dài khung giờ */}
        <div>
          <label className={LABEL}>Độ dài khung giờ</label>
          {/* Dropdown chọn độ dài khung giờ */}
          <select
            value={slotMinutes} // Giá trị hiện tại
            onChange={(e) => setSlotMinutes(Number(e.target.value))} // Cập nhật khi đổi
            className={INPUT}
          >
            {/* Lặp qua các lựa chọn */}
            {SLOT_OPTIONS.map((m) => (
              <option key={m} value={m}>
                {m} phút
              </option>
            ))}
          </select>
          {/* Ghi chú */}
          <p className="mt-1 text-label text-ink-faint">
            Phải chia hết 60 (5/10/15/20/30/60).
          </p>
        </div>
        {/* Trường: số chỗ đặt hẹn */}
        <div>
          <label className={LABEL}>Số chỗ đặt hẹn / khung</label>
          {/* Input số */}
          <input
            type="number" // Kiểu số
            min={1} // Tối thiểu 1
            max={100} // Tối đa 100
            value={regularCap} // Giá trị hiện tại
            onChange={(e) => setRegularCap(Number(e.target.value))} // Cập nhật khi đổi
            className={INPUT}
          />
          {/* Ghi chú */}
          <p className="mt-1 text-label text-ink-faint">
            BN1 + BN2 cho CSKH/Lễ tân đặt trước.
          </p>
        </div>
        {/* Trường: số chỗ vãng lai */}
        <div>
          <label className={LABEL}>Số chỗ vãng lai / khung</label>
          {/* Input số */}
          <input
            type="number" // Kiểu số
            min={0} // Tối thiểu 0
            max={100} // Tối đa 100
            value={walkinCap} // Giá trị hiện tại
            onChange={(e) => setWalkinCap(Number(e.target.value))} // Cập nhật khi đổi
            className={INPUT}
          />
          {/* Ghi chú */}
          <p className="mt-1 text-label text-ink-faint">
            Chỗ dành riêng khách tới trực tiếp.
          </p>
        </div>
      </div>

      {/* Phần nút lưu và thông báo */}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        {/* Nút lưu */}
        <button onClick={save} disabled={busy} className={BTN}>
          {busy ? "Đang lưu..." : "Lưu luật đặt lịch"} {/* Hiển thị trạng thái */}
        </button>
        {/* Thông báo kết quả */}
        {msg && (
          <p
            className={
              msg.kind === "ok" ? "text-sm text-success" : "text-sm text-danger" // Màu theo loại
            }
          >
            {msg.text} {/* Nội dung thông báo */}
          </p>
        )}
      </div>
    </div>
  );
}