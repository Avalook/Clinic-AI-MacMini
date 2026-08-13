"use client";

// Chức danh nào được xếp vào vị trí nào.
//
// Ô này siết màn "Sửa lịch làm việc": chọn một lễ tân thì ô Vị trí chỉ còn
// những chỗ lễ tân làm được, và backend từ chối phần còn lại (Quang, 08/08:
// *"lễ tân chỉ chọn được vị trí của lễ tân, không vào bác sĩ được"*).
//
// VÌ SAO PHẢI CÓ MÀN NÀY. Ma trận khởi đầu gieo từ chính lịch trực sáu tháng
// của phòng khám — nghĩa là nó đúng với những gì họ ĐÃ làm, và không biết gì về
// những gì họ SẮP làm. Siết mà không có đường gỡ thì lần đầu phân công một
// người sang việc mới là cả màn xếp lịch đứng lại, và không ai tự mở được.

import { useState } from "react";
import { STATIONS } from "../../../lib/roster";
import { ROLE_LABEL, type ClinicRole } from "../../../lib/roles";
import { LABEL } from "../form-ui";

export interface OViTri {
  tram_ma: string;
  vai: string;
  is_active: boolean;
  ghi_chu: string | null;
}

// Chỉ những chức danh THẬT SỰ đứng ca. Thu ngân thuốc / thu ngân dịch vụ là hai
// vai cũ còn trong kiểu để đọc lại nhật ký (xem roles.ts), gán cho người mới thì
// không; màn hình phòng chờ là cái tivi.
const VAI_XEP_CA: ClinicRole[] = [
  "DOCTOR",
  "ULTRASOUND_DOCTOR",
  "NURSE_ULTRASOUND",
  "TKYK",
  "RECEPTION",
  "CASHIER",
  "CSKH",
  "PHARMACIST",
  "TRUONG_CA",
  "MANAGEMENT",
];

export default function PhamViViTriCard({ items }: { items: OViTri[] }) {
  const [bang, setBang] = useState(() => {
    const m = new Map<string, boolean>();
    for (const it of items) m.set(`${it.tram_ma}|${it.vai}`, it.is_active);
    return m;
  });
  const [dangLuu, setDangLuu] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  async function doi(tram: string, vai: ClinicRole) {
    const key = `${tram}|${vai}`;
    const moi = !(bang.get(key) ?? false);
    setDangLuu(key);
    setLoi(null);
    const res = await fetch("/api/roster/pham-vi", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tram_ma: tram, vai, cho_phep: moi }),
    });
    setDangLuu(null);
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as { error?: string } | null;
      setLoi(d?.error ?? "Không lưu được.");
      return;
    }
    // Chỉ đổi trên màn SAU KHI server nhận. Đổi trước rồi hoàn lại khi lỗi là
    // cách chắc chắn để người dùng tin một ô đã bật trong khi nó chưa.
    setBang((cu) => new Map(cu).set(key, moi));
  }

  // Vai nào KHÔNG có ô nào bật thì backend cho qua tất (fail-open) — nói ra,
  // đừng để quản lý nhìn một hàng trắng và tưởng người đó bị cấm hết.
  const vaiChuaKhai = VAI_XEP_CA.filter(
    (v) => !STATIONS.some((s) => bang.get(`${s.key}|${v}`)),
  );

  return (
    <section className="rounded-card border border-line bg-surface p-5 shadow-card">
      <h2 className="text-sm font-semibold text-ink">Phạm vi vị trí</h2>
      <p className="mt-1 text-xs text-ink-muted">
        Tích ô để cho phép chức danh đó được xếp vào vị trí ấy. Màn “Sửa lịch làm
        việc” chỉ hiện những vị trí đã tích, và máy chủ từ chối phần còn lại.
      </p>

      {loi && (
        <p className="mt-3 rounded bg-danger-bg px-3 py-2 text-sm text-danger">
          {loi}
        </p>
      )}

      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full border-separate border-spacing-0 text-xs">
          <thead>
            <tr>
              <th className={`${LABEL} sticky left-0 bg-surface px-2 py-2 text-left`}>
                Vị trí
              </th>
              {VAI_XEP_CA.map((v) => (
                <th
                  key={v}
                  className="px-2 py-2 text-center align-bottom font-medium text-ink-soft"
                >
                  <span className="inline-block whitespace-nowrap [writing-mode:vertical-rl] rotate-180">
                    {ROLE_LABEL[v]}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {STATIONS.map((s) => (
              <tr key={s.key} className="border-t border-line">
                <td className="sticky left-0 bg-surface px-2 py-1.5 text-ink">
                  {s.label}
                </td>
                {VAI_XEP_CA.map((v) => {
                  const key = `${s.key}|${v}`;
                  return (
                    <td key={v} className="px-2 py-1.5 text-center">
                      <input
                        type="checkbox"
                        checked={bang.get(key) ?? false}
                        disabled={dangLuu === key}
                        onChange={() => void doi(s.key, v)}
                        aria-label={`${ROLE_LABEL[v]} — ${s.label}`}
                        className="size-4 accent-[var(--color-brand-600)]"
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {vaiChuaKhai.length > 0 && (
        <p className="mt-3 text-[11px] text-ink-faint">
          Chưa khai vị trí nào cho: {vaiChuaKhai.map((v) => ROLE_LABEL[v]).join(", ")}.
          Những chức danh này tạm thời xếp được vào mọi vị trí.
        </p>
      )}
    </section>
  );
}
