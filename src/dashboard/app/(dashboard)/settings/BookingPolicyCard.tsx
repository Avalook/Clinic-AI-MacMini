"use client";

// Luật đặt lịch của phòng khám — chỉ Trưởng ca + Quản lý sửa được (C.3 write path).
// Hiển thị 3 con số hiện tại (từ BookingPolicyContext, đọc một lần ở layout) và
// cho phép đổi chúng. Sau khi lưu → router.refresh() để layout đọc lại policy mới
// và mọi lưới khung giờ phía dưới vẽ theo luật mới.

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { BookingPolicy } from "../../../lib/booking-policy";
import { INPUT, LABEL, BTN } from "../form-ui";

const SLOT_OPTIONS = [5, 10, 15, 20, 30, 60];

export default function BookingPolicyCard({
  policy,
}: {
  policy: BookingPolicy | null;
}) {
  const router = useRouter();
  const [slotMinutes, setSlotMinutes] = useState(policy?.slotMinutes ?? 15);
  const [regularCap, setRegularCap] = useState(policy?.regularCap ?? 2);
  const [walkinCap, setWalkinCap] = useState(policy?.walkinCap ?? 1);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(
    null,
  );

  if (!policy) {
    return (
      <div className="rounded-card border border-line bg-surface p-5 shadow-card">
        <h2 className="text-base font-semibold text-ink">Luật đặt lịch</h2>
        <p className="mt-2 text-sm text-ink-muted">
          Chưa đọc được luật đặt lịch của phòng khám — tải lại trang rồi thử lại.
        </p>
      </div>
    );
  }

  async function save() {
    setBusy(true);
    setMsg(null);
    const res = await fetch("/api/booking-policy", {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        slot_minutes: slotMinutes,
        regular_cap: regularCap,
        walkin_cap: walkinCap,
      }),
    });
    const data = (await res.json()) as { ok?: boolean; error?: string };
    setBusy(false);
    if (!res.ok || !data.ok) {
      setMsg({ kind: "err", text: data.error ?? `Lỗi máy chủ (${res.status})` });
      return;
    }
    setMsg({ kind: "ok", text: "Đã lưu luật đặt lịch mới." });
    router.refresh();
  }

  return (
    <div className="rounded-card border border-line bg-surface p-5 shadow-card">
      <h2 className="text-base font-semibold text-ink">Luật đặt lịch</h2>
      <p className="mt-1 text-sm text-ink-muted">
        Áp dụng cho phòng khám này. Thay đổi có hiệu lực ngay — mọi lưới khung
        giờ và trigger chống quá tải đọc cùng một cấu hình.
      </p>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div>
          <label className={LABEL}>Độ dài khung giờ</label>
          <select
            value={slotMinutes}
            onChange={(e) => setSlotMinutes(Number(e.target.value))}
            className={INPUT}
          >
            {SLOT_OPTIONS.map((m) => (
              <option key={m} value={m}>
                {m} phút
              </option>
            ))}
          </select>
          <p className="mt-1 text-[11px] text-ink-faint">
            Phải chia hết 60 (5/10/15/20/30/60).
          </p>
        </div>
        <div>
          <label className={LABEL}>Số chỗ đặt hẹn / khung</label>
          <input
            type="number"
            min={1}
            max={100}
            value={regularCap}
            onChange={(e) => setRegularCap(Number(e.target.value))}
            className={INPUT}
          />
          <p className="mt-1 text-[11px] text-ink-faint">
            BN1 + BN2 cho CSKH/Lễ tân đặt trước.
          </p>
        </div>
        <div>
          <label className={LABEL}>Số chỗ vãng lai / khung</label>
          <input
            type="number"
            min={0}
            max={100}
            value={walkinCap}
            onChange={(e) => setWalkinCap(Number(e.target.value))}
            className={INPUT}
          />
          <p className="mt-1 text-[11px] text-ink-faint">
            Chỗ dành riêng khách tới trực tiếp.
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button onClick={save} disabled={busy} className={BTN}>
          {busy ? "Đang lưu..." : "Lưu luật đặt lịch"}
        </button>
        {msg && (
          <p
            className={
              msg.kind === "ok" ? "text-sm text-success" : "text-sm text-danger"
            }
          >
            {msg.text}
          </p>
        )}
      </div>
    </div>
  );
}