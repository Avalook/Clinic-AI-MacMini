"use client";

// Bảng 2 (kiểu PM "xem CSKH Action"): nhật ký VIỆC CSKH, gom theo `Phân loại`.
// KHÁC Bảng 1 — mỗi thẻ ở đây = 1 LẦN CSKH thao tác (không phải 1 lịch hẹn).
// Nguồn: bảng cskh_action (cột `category` = Phân loại). Việc được hệ TỰ GHI (xác
// nhận lịch / khám xong; Zalo/Pancake sau) HOẶC CSKH ghi TAY qua nút "+" trên mỗi
// cột (feedback B4 → POST /api/cskh-action). Bấm thẻ → popup chi tiết + hồ sơ khách.

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ExternalLink, X, Plus } from "lucide-react";
import { fmtDateTimeOrDate } from "../../../lib/datetime";
import { INPUT, LABEL } from "../form-ui";

export interface CskhActionRow {
  id: string;
  category: string | null;
  status: string | null;
  description: string | null;
  action_data: string | null;
  source_created_at: string | null;
  created_by_text: string | null;
  patient: {
    clinic_patient_id: string;
    full_name: string;
    patient_code: string;
    phone_primary: string | null;
  } | null;
}

// 7 nhóm Phân loại (taxonomy phòng khám tự định nghĩa). `match` = từ khoá để gom
// dữ liệu thô (category có thể là kịch bản con) — khớp lỏng để không rớt dòng.
const COLUMNS = [
  { key: "dat_hen", label: "Đặt hẹn", dot: "#2563eb", match: ["đặt hẹn", "đặt lịch", "đổi lịch", "hủy", "huỷ", "nhắc lịch"] },
  { key: "tu_van", label: "Tư vấn", dot: "#7c3aed", match: ["tư vấn"] },
  { key: "tra_xn", label: "Trả xét nghiệm", dot: "#0ea5e9", match: ["xét nghiệm", "trả kết quả", "trả kq", "kết quả"] },
  { key: "sau_kham", label: "CSKH sau khám", dot: "#16a34a", match: ["sau khám", "tái khám", "chăm sóc"] },
  { key: "thu_thuat", label: "Mổ và thủ thuật", dot: "#db2777", match: ["mổ", "thủ thuật"] },
  { key: "su_co", label: "Xử lí sự cố", dot: "#dc2626", match: ["sự cố", "khiếu nại", "thắc mắc"] },
  { key: "ghi_chu", label: "Ghi chú", dot: "#a16207", match: ["ghi chú"] },
];
const OTHER = { key: "khac", label: "Khác", dot: "#a1a1aa", match: [] as string[] };

function bucketKey(category: string | null): string {
  const c = (category ?? "").toLowerCase();
  const col = COLUMNS.find((k) => k.match.some((m) => c.includes(m)));
  return col?.key ?? OTHER.key;
}

export default function CskhActionBoard({ rows }: { rows: CskhActionRow[] }) {
  const router = useRouter();
  const [selId, setSelId] = useState<string | null>(null);
  const sel = rows.find((r) => r.id === selId) ?? null;

  // Ghi tay 1 việc CSKH (feedback B4) — modal mở từ nút "+" trên mỗi cột.
  const [addCat, setAddCat] = useState<string | null>(null);
  const [desc, setDesc] = useState("");
  const [statusVal, setStatusVal] = useState("");
  const [pcode, setPcode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function openAdd(category: string) {
    setAddCat(category);
    setDesc("");
    setStatusVal("");
    setPcode("");
    setErr(null);
  }
  function closeAdd() {
    setAddCat(null);
    setErr(null);
  }
  async function submit() {
    if (!desc.trim()) {
      setErr("Phải nhập nội dung việc.");
      return;
    }
    setBusy(true);
    setErr(null);
    const res = await fetch("/api/cskh-action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        category: addCat,
        description: desc,
        status: statusVal,
        patient_code: pcode,
      }),
    });
    setBusy(false);
    if (!res.ok) {
      setErr((await res.json()).error ?? "Lỗi lưu việc.");
      return;
    }
    closeAdd();
    router.refresh();
  }

  // Gom dòng theo cột; chỉ thêm cột "Khác" nếu thật sự có dòng không khớp.
  const byKey = new Map<string, CskhActionRow[]>();
  for (const r of rows) {
    const k = bucketKey(r.category);
    (byKey.get(k) ?? byKey.set(k, []).get(k)!).push(r);
  }
  const cols = [...COLUMNS];
  if ((byKey.get(OTHER.key)?.length ?? 0) > 0) cols.push(OTHER);

  const content = (r: CskhActionRow) =>
    (r.description || r.action_data || "").trim();

  return (
    <>
    <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
      <div className="min-w-0 flex-1 h-[520px] min-h-[260px] max-h-[88vh] resize-y overflow-x-auto overflow-y-hidden rounded-xl border border-[#f3cfe0] bg-white shadow-[0_1px_3px_rgba(236,72,153,0.08)]">
        <div className="flex h-full divide-x divide-[#f6e0ec]">
          {cols.map((col) => {
            const items = byKey.get(col.key) ?? [];
            return (
              <div key={col.key} className="flex min-w-[200px] flex-1 flex-col">
                <div className="flex items-center gap-2 border-b border-[#f3cfe0] bg-[#fce7f3] px-3 py-2">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ backgroundColor: col.dot }}
                  />
                  <span className="text-sm font-semibold text-[#171717]">
                    {col.label}
                  </span>
                  <div className="ml-auto flex items-center gap-1">
                    <span className="rounded-full bg-white px-2 py-0.5 text-xs text-[#71717a]">
                      {items.length}
                    </span>
                    {col.key !== OTHER.key && (
                      <button
                        onClick={() => openAdd(col.label)}
                        title={`Thêm việc: ${col.label}`}
                        className="rounded-md p-1 text-[#9d2463] hover:bg-white/70"
                      >
                        <Plus size={15} />
                      </button>
                    )}
                  </div>
                </div>
                <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-2">
                  {items.length === 0 && (
                    <p className="py-6 text-center text-xs text-[#a1a1aa]">
                      Trống
                    </p>
                  )}
                  {items.map((r) => (
                    <button
                      key={r.id}
                      onClick={() => setSelId(r.id)}
                      className={
                        "w-full rounded-lg border bg-white p-2.5 text-left transition-colors " +
                        (selId === r.id
                          ? "border-[#ec4899] ring-2 ring-[#ec4899]/20"
                          : "border-[#e4e4e7] hover:border-[#ec4899]/50")
                      }
                    >
                      <span className="block truncate text-sm font-medium text-[#171717]">
                        {r.patient?.full_name ?? "(chưa gắn khách)"}
                      </span>
                      {content(r) && (
                        <span className="mt-0.5 block truncate text-xs text-[#52525b]">
                          {content(r)}
                        </span>
                      )}
                      <span className="mt-1 block truncate text-[11px] text-[#888888]">
                        {fmtDateTimeOrDate(r.source_created_at)}
                        {r.status ? ` · ${r.status}` : ""}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {sel && (
        <aside className="w-full shrink-0 rounded-xl border border-[#f9a8d4] bg-[#fdf2f8] p-4 shadow-[0_1px_3px_rgba(0,0,0,0.06)] lg:sticky lg:top-4 lg:w-[360px]">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-[#9d174d]">Chi tiết việc CSKH</h3>
            <button
              onClick={() => setSelId(null)}
              aria-label="Đóng"
              className="rounded-md p-1 text-[#9d174d] hover:bg-white/60"
            >
              <X size={16} />
            </button>
          </div>
          <dl className="space-y-1.5 text-sm">
            <Row label="Khách" value={sel.patient?.full_name} />
            <Row label="Mã / SĐT" value={[sel.patient?.patient_code, sel.patient?.phone_primary].filter(Boolean).join(" · ")} />
            <Row label="Loại việc" value={sel.category} />
            <Row label="Nội dung" value={content(sel)} />
            <Row label="Trạng thái" value={sel.status} />
            <Row label="Thời gian" value={fmtDateTimeOrDate(sel.source_created_at)} />
            <Row label="Người làm" value={sel.created_by_text} />
          </dl>
          {sel.patient && (
            <div className="mt-4">
              <Link
                href={`/patients/${sel.patient.clinic_patient_id}`}
                className="inline-flex min-h-10 items-center gap-1 rounded-lg border border-[#e4e4e7] bg-white px-4 text-sm font-medium text-[#52525b] hover:bg-[#f4f4f5]"
              >
                <ExternalLink size={14} /> Mở hồ sơ khách
              </Link>
            </div>
          )}
        </aside>
      )}
    </div>

    {addCat !== null && (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
        onClick={closeAdd}
      >
        <div
          className="w-full max-w-md rounded-xl border border-[#f3cfe0] bg-white p-4 shadow-[0_8px_30px_rgba(0,0,0,0.12)]"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-[#9d174d]">
              Thêm việc: {addCat}
            </h3>
            <button
              onClick={closeAdd}
              aria-label="Đóng"
              className="rounded-md p-1 text-[#9d174d] hover:bg-[#fdf2f8]"
            >
              <X size={16} />
            </button>
          </div>
          <div className="space-y-2">
            <div>
              <label className={LABEL}>Nội dung việc *</label>
              <textarea
                className={INPUT}
                rows={3}
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
                placeholder="VD: Gọi nhắc tái khám, tư vấn kết quả…"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className={LABEL}>Trạng thái</label>
                <input
                  className={INPUT}
                  value={statusVal}
                  onChange={(e) => setStatusVal(e.target.value)}
                  placeholder="VD: Đã gọi"
                />
              </div>
              <div>
                <label className={LABEL}>Mã BN (nếu có)</label>
                <input
                  className={INPUT}
                  value={pcode}
                  onChange={(e) => setPcode(e.target.value)}
                  placeholder="BN-2026-..."
                />
              </div>
            </div>
            {err && <p className="text-xs text-[#dc2626]">{err}</p>}
            <div className="flex gap-2 pt-1">
              <button
                onClick={submit}
                disabled={busy}
                className="min-h-10 rounded-lg bg-[#ec4899] px-4 text-sm font-semibold text-white hover:bg-[#db2777] disabled:opacity-50"
              >
                {busy ? "Đang lưu..." : "Lưu việc"}
              </button>
              <button
                onClick={closeAdd}
                className="min-h-10 rounded-lg border border-[#e4e4e7] bg-white px-4 text-sm text-[#52525b] hover:bg-[#f4f4f5]"
              >
                Huỷ
              </button>
            </div>
          </div>
        </div>
      </div>
    )}
    </>
  );
}

function Row({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex gap-2">
      <dt className="w-24 shrink-0 text-[#888888]">{label}</dt>
      <dd className="min-w-0 break-words text-[#171717]">{value || "—"}</dd>
    </div>
  );
}
