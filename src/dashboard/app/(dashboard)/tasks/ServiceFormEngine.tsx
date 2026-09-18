"use client";

// ENGINE form khám chuyên khoa — đọc schema theo service_code rồi TỰ SINH form
// (KHÔNG hard-code từng form). Đọc/ghi form_data JSONB qua /api/clinical-form.
// READ-ONLY khi readOnly=true (vd visit FINALIZED) — route cũng chặn ghi (409).

import { useEffect, useMemo, useRef, useState } from "react";
import { INPUT, LABEL } from "../form-ui";
import { getFormSchema } from "../../../lib/form-schemas";
import AndrologyReview from "./AndrologyReview";
import type { ONhanSinhHieu } from "../../../lib/sinh-hieu-dong-bo";
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

// ===== Tokens trình bày ClinicAI dùng chung với workspace lâm sàng =====
// TAB / TAB_ON / TAB_OFF / NAV_BTN đã bỏ cùng thanh tab và nút "Mục trước /
// Mục sau" (07/08/2026): cả phiếu nay nằm trên một mạch cuộn hai cột.
/** Khối sinh hiệu API trả RIÊNG với form_data (S0-3): chỉ xem, không lưu vào phiếu. */
interface KhoiSinhHieu {
  nguon: "do" | "phieu_cu";
  luc: string | null;
  o: ONhanSinhHieu[];
}
type PhieuTraVe = { form_data?: FormData; sinh_hieu?: KhoiSinhHieu };

const CHIP =
  "rounded-full border px-3 py-1 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50";
const CHIP_ON = " border-brand-600 bg-brand-100 font-semibold text-brand-800";
const CHIP_OFF = " border-line bg-surface text-ink-soft hover:bg-brand-50";

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
  const [sinhHieu, setSinhHieu] = useState<KhoiSinhHieu | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  /** Bản phiếu đã khớp máy chủ (chuỗi JSON) — mốc để biết màn này có chữ chưa lưu. */
  const daLuuRef = useRef<string>("");
  // Mục Cận lâm sàng THU GỌN MẶC ĐỊNH (Quang chốt 07/08). Chúng là phần dài
  // nhất của mọi phiếu — riêng Hiếm muộn có ba mục Cận lâm sàng cộng lại 32
  // trường — và thường bác sĩ chỉ mở khi đã có kết quả trong tay.
  const [moThem, setMoThem] = useState<Record<string, boolean>>({});

  useEffect(() => {
    // Không có config / chưa có visit → component return null bên dưới; bỏ qua fetch.
    if (!schema || !visitId) return;
    let on = true;
    fetch(`/api/clinical-form?visitId=${visitId}&serviceCode=${schema.service_code}`)
      .then((r) => r.json())
      .then((d: PhieuTraVe) => {
        if (!on) return;
        daLuuRef.current = JSON.stringify(d.form_data ?? {});
        setValues(d.form_data ?? {});
        setSinhHieu(d.sinh_hieu ?? null);
      })
      .catch(() => on && setValues({}))
      .finally(() => on && setLoading(false));
    return () => {
      on = false;
    };
  }, [schema, visitId]);

  // TỰ LƯU (Tuyền 17/09/2026): ngừng gõ ~1,2 giây là ghi lên máy chủ — thư ký
  // nhập thì màn bác sĩ thấy, chuyển màn không mất chữ.
  useEffect(() => {
    if (readOnly || loading || !schema || !visitId) return;
    if (JSON.stringify(values) === daLuuRef.current) return;
    const t = setTimeout(() => void luu(values, true), 1200);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `luu` đọc đúng values truyền vào
  }, [values, readOnly, loading, schema, visitId]);

  // ĐỌC LẠI MỖI 4 GIÂY khi màn này KHÔNG có chữ chưa lưu: bác sĩ ngồi xem thấy
  // thư ký nhập, thư ký thấy bác sĩ sửa, và sinh hiệu điều dưỡng vừa đo hiện vào.
  useEffect(() => {
    if (!schema || !visitId) return;
    const id = setInterval(() => {
      if (document.visibilityState === "hidden") return;
      void fetch(`/api/clinical-form?visitId=${visitId}&serviceCode=${schema.service_code}`, {
        cache: "no-store",
      })
        .then((r) => (r.ok ? r.json() : null))
        .then((d: PhieuTraVe | null) => {
          if (!d) return;
          setSinhHieu(d.sinh_hieu ?? null);
          const moi = d.form_data ?? {};
          const chuoiMoi = JSON.stringify(moi);
          setValues((cur) => {
            // Đang có chữ chưa lưu ở màn này → giữ nguyên, lần tự lưu sẽ gửi đi.
            if (JSON.stringify(cur) !== daLuuRef.current) return cur;
            if (chuoiMoi === daLuuRef.current) return cur;
            daLuuRef.current = chuoiMoi;
            return moi;
          });
        })
        .catch(() => {});
    }, 4000);
    return () => clearInterval(id);
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

  async function luu(guiDi: FormData, tuDong: boolean) {
    if (readOnly || !schema || !visitId) return;
    const chuoi = JSON.stringify(guiDi);
    // GỬI ĐÚNG CÁC Ô VỪA ĐỔI so với bản đã khớp máy chủ (17/09/2026). Gửi cả
    // phiếu thì hai người gõ cùng lúc hai ô khác nhau, người lưu sau xoá chữ
    // của người lưu trước — đã thấy thật khi thư ký và bác sĩ cùng mở phiếu.
    let goc: FormData = {};
    try {
      goc = daLuuRef.current ? (JSON.parse(daLuuRef.current) as FormData) : {};
    } catch {
      goc = {};
    }
    const thayDoi: FormData = {};
    for (const [k, v] of Object.entries(guiDi)) {
      if (JSON.stringify(v) !== JSON.stringify(goc[k])) thayDoi[k] = v;
    }
    const boTruong = Object.keys(goc).filter((k) => !(k in guiDi));
    if (Object.keys(thayDoi).length === 0 && boTruong.length === 0) {
      daLuuRef.current = chuoi;
      return;
    }
    setSaving(true);
    if (!tuDong) setMsg(null);
    const res = await fetch("/api/clinical-form", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        visitId,
        serviceCode: schema.service_code,
        form_data: thayDoi,
        ghep: true,
        bo_truong: boTruong,
      }),
    }).catch(() => null);
    setSaving(false);
    if (res?.ok) {
      daLuuRef.current = chuoi;
      setMsg(
        tuDong
          ? `Đã tự lưu lúc ${new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "Asia/Ho_Chi_Minh" })}.`
          : "Đã lưu phiếu khám.",
      );
      return;
    }
    setMsg(
      res
        ? ((await res.json().catch(() => ({}))) as { error?: string }).error ?? "Lỗi lưu phiếu."
        : "Mất kết nối — phiếu CHƯA được lưu, sẽ thử lại khi bạn gõ tiếp.",
    );
  }
  const save = () => luu(values, false);

  const sections = schema.sections;

  /** Mục Cận lâm sàng: dài, và chỉ cần khi đã có kết quả trong tay. */
  const laCanLamSang = (title: string) =>
    title.toLowerCase().startsWith("cận lâm sàng");

  /** "Tất cả bình thường" cho MỘT mục — chỉ đụng radio/checkbox_group có
   *  option mang nghĩa bình thường, không đụng field khác. */
  const coBinhThuong = (sec: FormSection) =>
    sec.fields.some(
      (f) =>
        (f.type === "radio" || f.type === "checkbox_group") &&
        normalOption(f) != null,
    );
  const datBinhThuong = (sec: FormSection) => {
    if (readOnly) return;
    setValues((s) => {
      const next = { ...s };
      for (const f of sec.fields) {
        if (f.type !== "radio" && f.type !== "checkbox_group") continue;
        const nv = normalOption(f);
        if (nv == null) continue;
        next[f.key] = f.type === "radio" ? nv : [nv];
      }
      return next;
    });
  };

  return (
    <div className="rounded-card border border-line bg-surface p-3 shadow-card">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-sm font-semibold text-ink">
          Phiếu {schema.title}
          <span className="ml-2 rounded-chip bg-status-assigned-bg px-1.5 py-0.5 text-label font-medium text-status-assigned">
            form chuyên khoa
          </span>
        </h4>
        {readOnly && (
          <span className="text-xs text-danger">🔒 chỉ xem</span>
        )}
      </div>

      {loading ? (
        <p className="text-sm text-ink-faint">Đang tải phiếu…</p>
      ) : (
        <>
          {/* HAI CỘT XẾP GẠCH, CUỘN DỌC MỘT MẠCH.
              Bản trước là thanh tab + "Mục trước / Mục sau": mỗi lần chỉ thấy
              MỘT mục, nên đi hết phiếu Phụ khoa phải bấm 11 lần, phiếu Hiếm
              muộn 20 lần — và không bao giờ nhìn được lý do khám cùng lúc với
              chẩn đoán.

              Dùng `columns` chứ không phải grid hai cột: các mục lệch nhau rất
              xa (mục "Lý do khám" 1 trường nằm cạnh "Khám lâm sàng" 15 trường),
              nên chia cứng sẽ để lại khoảng trắng so le. Xếp gạch thì thẻ tự
              rơi vào cột nào còn chỗ. */}
          <KhoiSinhHieuChiXem khoi={sinhHieu} />
          <div className="[column-gap:0.75rem] lg:[columns:2]">
            {sections.map((sec, i) => {
              const cls = laCanLamSang(sec.title);
              const mo = moThem[sec.title] ?? !cls;
              const xong = sectionFilled(sec, values);
              return (
                <section
                  key={sec.title}
                  className="mb-3 break-inside-avoid rounded-card border border-line bg-surface p-3"
                >
                  <div className="flex items-center gap-2">
                    <span className="grid size-5 shrink-0 place-items-center rounded-control bg-brand-50 text-label font-bold tabular-nums text-brand-700">
                      {i + 1}
                    </span>
                    <h5 className="min-w-0 flex-1 text-sm font-semibold text-ink">
                      {sec.title}
                      {xong && <span className="ml-1.5 text-brand-600">✓</span>}
                    </h5>
                    {cls && (
                      <button
                        type="button"
                        onClick={() =>
                          setMoThem((m) => ({ ...m, [sec.title]: !mo }))
                        }
                        className="shrink-0 rounded-control px-2 py-1 text-xs text-ink-muted hover:bg-surface-muted"
                      >
                        {mo ? "thu gọn" : `mở · ${sec.fields.length} trường`}
                      </button>
                    )}
                  </div>

                  {mo && (
                    <>
                      {!readOnly && coBinhThuong(sec) && (
                        <div className="mt-2 flex justify-end">
                          <button
                            type="button"
                            onClick={() => datBinhThuong(sec)}
                            className="rounded-lg border border-brand-100 bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-800 transition-colors hover:bg-brand-100"
                          >
                            Tất cả bình thường
                          </button>
                        </div>
                      )}
                      <div className="mt-2 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                        {sec.fields
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
                    </>
                  )}
                </section>
              );
            })}
          </div>

          {/* Chỉ phiếu Nam khoa mới có bảng đối chiếu ngưỡng. Đặt ở đây chứ
              không trong Field: nó đọc CẢ phiếu (tinh dịch đồ + khám bìu + nội
              tiết) để suy ra gợi ý, không đọc từng ô rời. */}
          {schema.service_code === "NK" && <AndrologyReview values={values} visitId={visitId} />}

          {/* Thanh dưới — chỉ còn nút Lưu. Không còn prev/next: cả phiếu
              nằm trên một mạch cuộn, nên "Mục 3/11" không còn nghĩa gì. */}
          <div className="mt-1 flex items-center justify-between gap-2 border-t border-surface-sunken pt-3">
            <span className="text-xs text-ink-muted">
              {sections.length} mục ·{" "}
              {sections.filter((sec) => sectionFilled(sec, values)).length} đã điền
            </span>
            {!readOnly && (
              <button
                type="button"
                onClick={save}
                disabled={saving}
                className="min-h-9 shrink-0 rounded-control bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
              >
                {saving ? "Đang lưu…" : "Lưu phiếu"}
              </button>
            )}
          </div>

          {!readOnly && msg && (
            <p
              className={
                "mt-2 text-right text-xs " +
                (msg.startsWith("Đã lưu") ? "text-success" : "text-danger")
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
            <span className="shrink-0 text-xs text-ink-faint">{field.unit}</span>
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
        <label className="inline-flex items-center gap-1.5 text-sm text-ink-soft">
          <input
            type="checkbox"
            className="h-4 w-4 accent-brand-600"
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

/** Sinh hiệu CHỈ XEM trên đầu phiếu (S0-3, 18/09/2026). Đo và sửa ở màn Đo
 *  sinh hiệu; phiếu chuyên khoa không còn ô nhập trùng. */
function KhoiSinhHieuChiXem({ khoi }: { khoi: KhoiSinhHieu | null }) {
  if (!khoi) return null;
  const luc = khoi.luc
    ? new Date(khoi.luc).toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Asia/Ho_Chi_Minh",
      })
    : null;
  return (
    <section className="mb-3 rounded-card border border-line bg-surface-sunken p-3">
      <h5 className="text-sm font-semibold text-ink">
        Sinh hiệu
        <span className="ml-2 text-label font-normal text-ink-muted">
          {khoi.nguon === "do"
            ? `từ màn Đo sinh hiệu${luc ? ` · đo lúc ${luc}` : ""} — chỉ xem`
            : "ghi trên phiếu cũ — chỉ xem"}
        </span>
      </h5>
      {khoi.o.length === 0 ? (
        <p className="mt-1 text-sm text-ink-muted">Chưa đo sinh hiệu cho lượt này.</p>
      ) : (
        <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-4">
          {khoi.o.map((o, i) => (
            <div key={`${o.nhan}-${i}`} className="flex items-baseline gap-2">
              <dt className="text-label text-ink-muted">{o.nhan}</dt>
              <dd className="text-sm font-medium tabular-nums text-ink">{o.gia_tri}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}
