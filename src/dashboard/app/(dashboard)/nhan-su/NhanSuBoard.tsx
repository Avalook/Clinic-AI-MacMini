"use client";

import { useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { StaffRow } from "../../api/staff/route";

interface ConfigLocation {
  id: string;
  name: string;
}

/** Nhãn tiếng Việt cho vai trò. Cùng danh sách với PrimaryDepartment bên
 *  schemas/staff.py — thiếu một mục ở đây thì màn hiện mã thô, không nổ. */
const DEPARTMENTS: { value: string; label: string }[] = [
  { value: "DOCTOR", label: "Bác sĩ" },
  { value: "ULTRASOUND_DOCTOR", label: "Bác sĩ siêu âm" },
  { value: "NURSE_ULTRASOUND", label: "Điều dưỡng siêu âm" },
  { value: "TKYK", label: "Thư ký y khoa" },
  { value: "RECEPTION", label: "Lễ tân" },
  { value: "CSKH", label: "CSKH" },
  { value: "CASHIER", label: "Thu ngân" },
  { value: "CASHIER_THUOC", label: "Thu ngân thuốc" },
  { value: "CASHIER_DV", label: "Thu ngân dịch vụ" },
  { value: "PHARMACIST", label: "Dược sĩ" },
  { value: "TRUONG_CA", label: "Trưởng ca" },
  { value: "MANAGEMENT", label: "Quản lý" },
];

const EMPLOYMENT: { value: string; label: string }[] = [
  { value: "FULL_TIME", label: "Toàn thời gian" },
  { value: "PART_TIME", label: "Bán thời gian" },
  { value: "CONTRACT", label: "Hợp đồng" },
];

/** Trường mockup có mà database chưa có chỗ lưu. Hiện ra để người dùng biết
 *  hệ thống CHƯA làm, thay vì vẽ ô nhập gõ vào rồi mất. */
const CHUA_LUU_DUOC: { label: string; note: string }[] = [
  { label: "Ngày sinh", note: "cần thêm cột" },
  { label: "Giới tính", note: "cần thêm cột" },
  { label: "Số CCCD", note: "định danh công dân — cần quyết định về quyền đọc" },
  { label: "Số điện thoại", note: "cần thêm cột" },
  { label: "Email", note: "cần thêm cột" },
  { label: "Số CCHN + ngày cấp", note: "cần thêm cột" },
  { label: "Phạm vi hoạt động chuyên môn", note: "cần thêm cột" },
  { label: "Tài liệu đính kèm", note: "cần chỗ lưu tệp" },
];

const deptLabel = (value: string) =>
  DEPARTMENTS.find((d) => d.value === value)?.label ?? value;

const INPUT =
  "w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink " +
  "outline-none focus:border-brand-600 disabled:bg-surface-sunken";
const LABEL = "text-xs font-medium text-ink-muted";

export default function NhanSuBoard({
  initialStaff,
  locations,
}: {
  initialStaff: StaffRow[];
  locations: ConfigLocation[];
}) {
  const router = useRouter();
  const [staff, setStaff] = useState<StaffRow[]>(initialStaff);
  const [query, setQuery] = useState("");
  const [deptFilter, setDeptFilter] = useState<string>("");
  const [selectedId, setSelectedId] = useState<string | null>(
    initialStaff[0]?.id ?? null,
  );
  const [draft, setDraft] = useState<Partial<StaffRow>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  // Cùng lý do như nút đặt lịch: state chỉ đổi sau lần render kế tiếp, nên hai
  // cú click nhanh đều lọt. useRef đổi ngay.
  const savingRef = useRef(false);

  const counts = useMemo(() => {
    const map = new Map<string, number>();
    for (const s of staff) {
      map.set(s.primary_department, (map.get(s.primary_department) ?? 0) + 1);
    }
    return map;
  }, [staff]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return staff
      .filter((s) => !deptFilter || s.primary_department === deptFilter)
      .filter(
        (s) =>
          !q ||
          s.full_name.toLowerCase().includes(q) ||
          (s.short_name ?? "").toLowerCase().includes(q),
      )
      .sort((a, b) => a.full_name.localeCompare(b.full_name, "vi"));
  }, [staff, query, deptFilter]);

  const selected = staff.find((s) => s.id === selectedId) ?? null;
  const field = <K extends keyof StaffRow>(key: K): StaffRow[K] | undefined =>
    (draft[key] as StaffRow[K] | undefined) ?? selected?.[key];

  const dirty = Object.keys(draft).length > 0;

  function pick(row: StaffRow) {
    setSelectedId(row.id);
    setDraft({});
    setError(null);
    setSaved(false);
  }

  function edit<K extends keyof StaffRow>(key: K, value: StaffRow[K]) {
    setDraft((d) => ({ ...d, [key]: value }));
    setSaved(false);
  }

  async function save() {
    if (!selected || !dirty || savingRef.current) return;
    savingRef.current = true;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/staff", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: selected.id, ...draft }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.error || err.message || "Không lưu được hồ sơ.");
        return;
      }
      const updated = (await res.json()) as StaffRow;
      setStaff((list) =>
        list.map((s) => (s.id === updated.id ? { ...s, ...updated } : s)),
      );
      setDraft({});
      setSaved(true);
      router.refresh();
    } catch {
      setError("Mất kết nối tới máy chủ — hồ sơ chưa được lưu.");
    } finally {
      setSaving(false);
      savingRef.current = false;
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
      {/* ------------------------------------------------ danh sách bên trái */}
      <aside className="rounded-card border border-line bg-surface shadow-card">
        <div className="border-b border-line p-3">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Tìm theo tên hoặc tên gọi..."
            className={INPUT}
          />
          <div className="mt-2 flex flex-wrap gap-1.5">
            <button
              type="button"
              onClick={() => setDeptFilter("")}
              className={`rounded-full px-2.5 py-1 text-[11px] ${
                deptFilter === ""
                  ? "bg-brand-600 font-semibold text-white"
                  : "bg-surface-sunken text-ink-muted hover:bg-brand-100"
              }`}
            >
              Tất cả ({staff.length})
            </button>
            {DEPARTMENTS.filter((d) => counts.get(d.value)).map((d) => (
              <button
                key={d.value}
                type="button"
                onClick={() => setDeptFilter(d.value)}
                className={`rounded-full px-2.5 py-1 text-[11px] ${
                  deptFilter === d.value
                    ? "bg-brand-600 font-semibold text-white"
                    : "bg-surface-sunken text-ink-muted hover:bg-brand-100"
                }`}
              >
                {d.label} ({counts.get(d.value)})
              </button>
            ))}
          </div>
        </div>

        <ul className="max-h-[calc(100vh-16rem)] divide-y divide-line overflow-y-auto">
          {visible.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => pick(s)}
                className={`flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surface-sunken ${
                  s.id === selectedId ? "bg-brand-100" : ""
                }`}
              >
                <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-brand-600 text-xs font-semibold text-white">
                  {s.full_name.trim().slice(0, 1).toUpperCase()}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-ink">
                    {s.full_name}
                  </span>
                  <span className="block truncate text-xs text-ink-muted">
                    {deptLabel(s.primary_department)}
                    {s.is_training ? " · đang đào tạo" : ""}
                  </span>
                </span>
                {!s.is_active && (
                  <span className="shrink-0 rounded-full bg-surface-sunken px-2 py-0.5 text-[10px] text-ink-muted">
                    đã nghỉ
                  </span>
                )}
              </button>
            </li>
          ))}
          {visible.length === 0 && (
            <li className="px-4 py-6 text-center text-sm text-ink-muted">
              Không có ai khớp.
            </li>
          )}
        </ul>
      </aside>

      {/* -------------------------------------------------- hồ sơ bên phải */}
      {!selected ? (
        <section className="rounded-card border border-line bg-surface p-6 text-sm text-ink-muted shadow-card">
          Chưa có nhân sự nào để hiện.
        </section>
      ) : (
        <section className="space-y-4">
          <div className="rounded-card border border-line bg-surface p-4 shadow-card lg:p-5">
            <div className="mb-4 flex items-center gap-3">
              <span className="flex size-12 items-center justify-center rounded-full bg-brand-600 text-base font-semibold text-white">
                {selected.full_name.trim().slice(0, 1).toUpperCase()}
              </span>
              <div className="min-w-0">
                <h2 className="truncate text-base font-semibold text-ink">
                  {selected.full_name}
                </h2>
                <p className="text-xs text-ink-muted">
                  {deptLabel(selected.primary_department)} ·{" "}
                  {selected.is_active ? "đang làm việc" : "đã nghỉ"}
                </p>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-1">
                <span className={LABEL}>Họ và tên</span>
                <input
                  value={field("full_name") ?? ""}
                  onChange={(e) => edit("full_name", e.target.value)}
                  className={INPUT}
                />
              </label>
              <label className="space-y-1">
                <span className={LABEL}>Tên gọi trong phòng khám</span>
                <input
                  value={field("short_name") ?? ""}
                  onChange={(e) => edit("short_name", e.target.value)}
                  placeholder="ví dụ: BS Thành"
                  className={INPUT}
                />
              </label>
              <label className="space-y-1">
                <span className={LABEL}>Vai trò</span>
                <select
                  value={field("primary_department") ?? ""}
                  onChange={(e) => edit("primary_department", e.target.value)}
                  className={INPUT}
                >
                  {DEPARTMENTS.map((d) => (
                    <option key={d.value} value={d.value}>
                      {d.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                <span className={LABEL}>Cơ sở làm việc</span>
                <select
                  value={field("primary_location_id") ?? ""}
                  onChange={(e) =>
                    edit("primary_location_id", e.target.value || null)
                  }
                  className={INPUT}
                >
                  <option value="">— Chưa gán —</option>
                  {locations.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                <span className={LABEL}>Loại hợp đồng</span>
                <select
                  value={field("employment_type") ?? ""}
                  onChange={(e) => edit("employment_type", e.target.value)}
                  className={INPUT}
                >
                  {EMPLOYMENT.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="flex items-end gap-4 pb-1">
                <label className="flex items-center gap-2 text-sm text-ink">
                  <input
                    type="checkbox"
                    checked={field("is_active") ?? true}
                    onChange={(e) => edit("is_active", e.target.checked)}
                  />
                  Đang làm việc
                </label>
                <label className="flex items-center gap-2 text-sm text-ink">
                  <input
                    type="checkbox"
                    checked={field("is_training") ?? false}
                    onChange={(e) => edit("is_training", e.target.checked)}
                  />
                  Đang đào tạo
                </label>
              </div>
            </div>

            {error && (
              <p className="mt-3 rounded-card border border-danger bg-danger-bg px-3 py-2 text-sm text-danger">
                {error}
              </p>
            )}

            <div className="mt-4 flex items-center gap-3">
              <button
                type="button"
                onClick={save}
                disabled={!dirty || saving}
                className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white shadow-xs hover:bg-brand-700 disabled:opacity-50"
              >
                {saving ? "Đang lưu..." : "Lưu hồ sơ"}
              </button>
              {dirty && !saving && (
                <button
                  type="button"
                  onClick={() => setDraft({})}
                  className="text-sm text-ink-muted hover:text-ink"
                >
                  Hoàn tác
                </button>
              )}
              {saved && !dirty && (
                <span className="text-sm text-ink-muted">Đã lưu.</span>
              )}
            </div>
          </div>

          {/* ------------------------------------------ phần chưa dựng được */}
          <div className="rounded-card border border-line bg-surface-sunken p-4 lg:p-5">
            <h3 className="text-sm font-semibold text-ink">
              Chưa lưu được — bảng nhân sự chưa có những cột này
            </h3>
            <p className="mt-1 text-xs text-ink-muted">
              Bản thiết kế có các mục dưới đây, nhưng database chưa có chỗ lưu.
              Hiện ra để khỏi tưởng nhầm là đã nhập được — một ô gõ vào rồi mất
              còn tệ hơn một ô nói thẳng là chưa có.
            </p>
            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
              {CHUA_LUU_DUOC.map((f) => (
                <li
                  key={f.label}
                  className="rounded-lg border border-dashed border-line px-3 py-2"
                >
                  <span className="block text-sm text-ink-muted">{f.label}</span>
                  <span className="block text-[11px] text-ink-muted opacity-70">
                    {f.note}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}
    </div>
  );
}
