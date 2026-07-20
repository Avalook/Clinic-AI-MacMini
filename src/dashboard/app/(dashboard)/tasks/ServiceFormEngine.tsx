"use client";

// ENGINE form khám chuyên khoa — đọc schema theo service_code rồi TỰ SINH form
// (KHÔNG hard-code từng form). Đọc/ghi form_data JSONB qua /api/clinical-form.
// READ-ONLY khi readOnly=true (vd visit FINALIZED) — route cũng chặn ghi (409).

import { useEffect, useMemo, useState } from "react";
import { INPUT, LABEL } from "../form-ui";
import { getFormSchema } from "../../../lib/form-schemas";
import type {
  FormData,
  FormField,
  FormSection,
  FieldValue,
} from "../../../lib/form-schemas/types";

function isVisible(field: FormField, values: FormData): boolean {
  if (!field.parent) return true;
  const pv = values[field.parent.key];
  if (Array.isArray(pv)) return pv.includes(field.parent.equals as string);
  return pv === field.parent.equals;
}

// 1 field coi như "đã điền" nếu có giá trị truthy / mảng có phần tử / số (kể cả 0).
function hasValue(v: FieldValue): boolean {
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === "number") return true;
  if (typeof v === "boolean") return v;
  return v != null && v !== "";
}

// Section có ≥1 field được điền → để gắn dấu ✓ tiến độ trên tab.
function sectionFilled(section: FormSection, values: FormData): boolean {
  return section.fields.some((f) => hasValue(values[f.key]));
}

// "Tất cả bình thường": nhận diện option mang nghĩa bình thường (generic, KHÔNG
// hard-code theo schema). Chỉ áp cho radio/checkbox_group có option khớp.
const NORMAL_LABELS = new Set(["bình thường", "bt", "không", "ko"]);
function normalOption(field: FormField): string | null {
  const opt = (field.options ?? []).find(
    (o) =>
      NORMAL_LABELS.has(o.label.trim().toLowerCase()) ||
      NORMAL_LABELS.has(o.value.trim().toLowerCase()),
  );
  return opt ? opt.value : null;
}

// ===== Tokens trình bày (giữ theme: hồng #9d2463 / accent #ec4899) =====
const TAB =
  "shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm transition-colors";
const TAB_ON = " bg-[#fce7f3] font-semibold text-[#9d2463]";
const TAB_OFF = " text-[#52525b] hover:bg-[#f4f4f5]";
const CHIP =
  "rounded-full border px-3 py-1 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50";
const CHIP_ON = " border-[#ec4899] bg-[#fce7f3] font-semibold text-[#9d2463]";
const CHIP_OFF = " border-[#e4e4e7] bg-white text-[#3f3f46] hover:bg-[#fdf2f8]";
const NAV_BTN =
  "min-h-9 shrink-0 rounded-lg border border-[#e4e4e7] bg-white px-3 text-sm font-medium text-[#52525b] transition-colors hover:bg-[#f4f4f5] disabled:opacity-40";

export default function ServiceFormEngine({
  visitId,
  serviceCode,
  readOnly = false,
}: {
  visitId: string | null;
  serviceCode: string | null;
  readOnly?: boolean;
}) {
  const schema = useMemo(() => getFormSchema(serviceCode), [serviceCode]);
  const [values, setValues] = useState<FormData>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);

  useEffect(() => {
    // Không có config / chưa có visit → component return null bên dưới; bỏ qua fetch.
    if (!schema || !visitId) return;
    let on = true;
    fetch(`/api/clinical-form?visitId=${visitId}&serviceCode=${schema.service_code}`)
      .then((r) => r.json())
      .then((d: { form_data?: FormData }) => {
        if (on) setValues(d.form_data ?? {});
      })
      .catch(() => on && setValues({}))
      .finally(() => on && setLoading(false));
    return () => {
      on = false;
    };
  }, [schema, visitId]);

  // Engine chỉ render khi có config + có visit. Không có → ẩn (không vỡ layout).
  if (!schema || !visitId) return null;

  const set = (key: string, v: FieldValue) => setValues((s) => ({ ...s, [key]: v }));
  const toggleGroup = (key: string, opt: string) =>
    setValues((s) => {
      const cur = Array.isArray(s[key]) ? (s[key] as string[]) : [];
      return {
        ...s,
        [key]: cur.includes(opt) ? cur.filter((x) => x !== opt) : [...cur, opt],
      };
    });

  async function save() {
    if (readOnly) return;
    setSaving(true);
    setMsg(null);
    const res = await fetch("/api/clinical-form", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        visitId,
        serviceCode: schema!.service_code,
        form_data: values,
      }),
    });
    setSaving(false);
    setMsg(
      res.ok
        ? "Đã lưu phiếu khám."
        : (await res.json().catch(() => ({}))).error ?? "Lỗi lưu phiếu.",
    );
  }

  const sections = schema.sections;
  const total = sections.length;
  const idx = Math.min(activeIdx, total - 1);
  const section = sections[idx];

  // "Tất cả bình thường" cho section đang mở: set field radio/checkbox_group có
  // option mang nghĩa bình thường về giá trị đó. Không đụng field khác.
  const sectionHasNormal =
    !!section &&
    section.fields.some(
      (f) =>
        (f.type === "radio" || f.type === "checkbox_group") &&
        normalOption(f) != null,
    );
  const setSectionNormal = () => {
    if (readOnly || !section) return;
    setValues((s) => {
      const next = { ...s };
      for (const f of section.fields) {
        if (f.type !== "radio" && f.type !== "checkbox_group") continue;
        const nv = normalOption(f);
        if (nv == null) continue;
        next[f.key] = f.type === "radio" ? nv : [nv];
      }
      return next;
    });
  };

  return (
    <div className="rounded-xl border border-[#e4e4e7] bg-white p-3 shadow-[0_1px_3px_rgba(0,0,0,0.06)]">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-sm font-semibold text-[#171717]">
          Phiếu {schema.title}
          <span className="ml-2 rounded bg-[#ede9fe] px-1.5 py-0.5 text-[10px] font-medium text-[#6d28d9]">
            form chuyên khoa
          </span>
        </h4>
        {readOnly && (
          <span className="text-xs text-[#dc2626]">🔒 chỉ xem</span>
        )}
      </div>

      {loading ? (
        <p className="text-sm text-[#a1a1aa]">Đang tải phiếu…</p>
      ) : (
        <>
          {/* Thanh TAB theo section — chỉ render section đang chọn → giảm cuộn. */}
          <div className="sticky top-0 z-10 -mx-3 flex gap-1 overflow-x-auto border-b border-[#f4f4f5] bg-white px-3 pb-2">
            {sections.map((s, i) => (
              <button
                key={s.title}
                type="button"
                onClick={() => setActiveIdx(i)}
                className={TAB + (i === idx ? TAB_ON : TAB_OFF)}
              >
                {s.title}
                {sectionFilled(s, values) && (
                  <span className="ml-1 text-[#ec4899]">✓</span>
                )}
              </button>
            ))}
          </div>

          {section && (
            <section className="pt-3">
              {!readOnly && sectionHasNormal && (
                <div className="mb-2 flex justify-end">
                  <button
                    type="button"
                    onClick={setSectionNormal}
                    className="rounded-lg border border-[#f3cfe0] bg-[#fdf2f8] px-2.5 py-1 text-xs font-medium text-[#9d2463] transition-colors hover:bg-[#fce7f3]"
                  >
                    Tất cả bình thường
                  </button>
                </div>
              )}
              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
                {section.fields
                  .filter((f) => isVisible(f, values))
                  .map((f) => (
                    <Field
                      key={f.key}
                      field={f}
                      value={values[f.key]}
                      disabled={readOnly}
                      onChange={(v) => set(f.key, v)}
                      onToggleGroup={(opt) => toggleGroup(f.key, opt)}
                    />
                  ))}
              </div>
            </section>
          )}

          {/* Thanh điều hướng dưới — LUÔN hiện: prev/next + nút Lưu (khỏi cuộn đáy). */}
          <div className="mt-3 flex items-center justify-between gap-2 border-t border-[#f4f4f5] pt-3">
            <button
              type="button"
              onClick={() => setActiveIdx(Math.max(0, idx - 1))}
              disabled={idx === 0}
              className={NAV_BTN}
            >
              ← Mục trước
            </button>
            <span className="min-w-0 truncate text-center text-xs text-[#71717a]">
              Mục {idx + 1}/{total}
              {section ? ` · ${section.title}` : ""}
            </span>
            <div className="flex shrink-0 items-center gap-2">
              <button
                type="button"
                onClick={() => setActiveIdx(Math.min(total - 1, idx + 1))}
                disabled={idx === total - 1}
                className={NAV_BTN}
              >
                Mục sau →
              </button>
              {!readOnly && (
                <button
                  onClick={save}
                  disabled={saving}
                  className="min-h-9 shrink-0 rounded-lg bg-[#7c3aed] px-4 text-sm font-semibold text-white hover:brightness-95 disabled:opacity-50"
                >
                  {saving ? "Đang lưu…" : "Lưu phiếu"}
                </button>
              )}
            </div>
          </div>

          {!readOnly && msg && (
            <p
              className={
                "mt-2 text-right text-xs " +
                (msg.startsWith("Đã lưu") ? "text-[#15803d]" : "text-[#dc2626]")
              }
            >
              {msg}
            </p>
          )}
        </>
      )}
    </div>
  );
}

function Field({
  field,
  value,
  disabled,
  onChange,
  onToggleGroup,
}: {
  field: FormField;
  value: FieldValue;
  disabled: boolean;
  onChange: (v: FieldValue) => void;
  onToggleGroup: (opt: string) => void;
}) {
  const full = field.fullWidth || field.type === "textarea" || field.type === "conditional";
  const sv = typeof value === "string" ? value : value == null ? "" : String(value);

  let control: React.ReactNode;
  switch (field.type) {
    case "textarea":
    case "conditional":
      control = (
        <textarea
          className={INPUT}
          rows={2}
          value={sv}
          disabled={disabled}
          placeholder={field.placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      );
      break;
    case "number":
      control = (
        <div className="flex items-center gap-1.5">
          <input
            type="number"
            inputMode="decimal"
            className={INPUT}
            value={sv}
            disabled={disabled}
            placeholder={field.placeholder}
            onChange={(e) => onChange(e.target.value)}
          />
          {field.unit && (
            <span className="shrink-0 text-xs text-[#a1a1aa]">{field.unit}</span>
          )}
        </div>
      );
      break;
    case "date":
      control = (
        <input
          type="date"
          className={INPUT}
          value={sv}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
        />
      );
      break;
    case "radio":
      // CHIP chọn-1: bấm chip = set value (cắt chiều cao so với list dọc).
      control = (
        <div className="flex flex-wrap gap-1.5">
          {(field.options ?? []).map((o) => (
            <button
              key={o.value}
              type="button"
              disabled={disabled}
              onClick={() => onChange(o.value)}
              className={CHIP + (value === o.value ? CHIP_ON : CHIP_OFF)}
            >
              {o.label}
            </button>
          ))}
        </div>
      );
      break;
    case "checkbox":
      control = (
        <label className="inline-flex items-center gap-1.5 text-sm text-[#3f3f46]">
          <input
            type="checkbox"
            className="h-4 w-4 accent-[#ec4899]"
            checked={value === true}
            disabled={disabled}
            onChange={(e) => onChange(e.target.checked)}
          />
          {field.label}
        </label>
      );
      break;
    case "checkbox_group": {
      // CHIP chọn-nhiều: toggle qua onToggleGroup sẵn có (value vẫn là string[]).
      const arr = Array.isArray(value) ? (value as string[]) : [];
      control = (
        <div className="flex flex-wrap gap-1.5">
          {(field.options ?? []).map((o) => (
            <button
              key={o.value}
              type="button"
              disabled={disabled}
              onClick={() => onToggleGroup(o.value)}
              className={CHIP + (arr.includes(o.value) ? CHIP_ON : CHIP_OFF)}
            >
              {o.label}
            </button>
          ))}
        </div>
      );
      break;
    }
    default: // text
      control = (
        <input
          className={INPUT}
          value={sv}
          disabled={disabled}
          placeholder={field.placeholder}
          onChange={(e) => onChange(e.target.value)}
        />
      );
  }

  // Field full-width chiếm trọn hàng theo SỐ CỘT mới (2 ở sm, 3 ở lg).
  const span = full ? "sm:col-span-2 lg:col-span-3" : "";
  // checkbox tự gói nhãn → không lặp label phía trên.
  if (field.type === "checkbox") {
    return <div className={span}>{control}</div>;
  }
  return (
    <div className={span}>
      <label className={LABEL}>{field.label}</label>
      {control}
    </div>
  );
}
