"use client";

import { useState } from "react";
import Button from "@/components/ui/Button";

export interface ReportSettings {
  nhan_vien_theo_ca: boolean;
  truong_ca_theo_ngay: boolean;
  tai_chinh_day_du: boolean;
}

export default function ReportSettingsCard({ initial }: { initial: ReportSettings }) {
  const [value, setValue] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const save = async () => {
    setSaving(true); setMessage("");
    try {
      const res = await fetch("/api/reports/settings", {
        method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(value),
      });
      if (!res.ok) throw new Error("Không lưu được thiết lập báo cáo.");
      setMessage("Đã lưu thiết lập báo cáo.");
    } catch (e) { setMessage(e instanceof Error ? e.message : "Không lưu được."); }
    finally { setSaving(false); }
  };
  return <section className="space-y-3 rounded-card bg-surface p-4 ring-1 ring-hairline">
    <h2 className="text-title font-semibold">Thiết lập báo cáo</h2>
    <p className="text-body">Quyền xem theo lịch phân công đã duyệt: nhân viên xem ca mình làm; trưởng ca xem cả ngày mình trực tại cơ sở đó.</p>
    <label className="flex min-h-10 items-center gap-3 text-body">
      <input type="checkbox" checked={value.tai_chinh_day_du} disabled={saving}
        onChange={e => setValue({ ...value, tai_chinh_day_du: e.target.checked })} />
      Hiển thị đầy đủ doanh thu, hoàn tiền, nợ và giảm giá
    </label>
    <p className="text-meta text-ink-muted">Quản lý xem toàn bộ báo cáo. Phạm vi theo lịch trực luôn được áp dụng, kể cả khi mở bằng đường dẫn trực tiếp hoặc xuất Excel.</p>
    <Button size="lg" disabled={saving} onClick={() => void save()}>{saving ? "Đang lưu…" : "Lưu thiết lập"}</Button>
    {message ? <p role="status" className="text-body">{message}</p> : null}
  </section>;
}
