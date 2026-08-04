"use client";

// KÝ BỆNH ÁN — HAI BƯỚC, và bước hai không tự xảy ra.
//
// Quyết định của Quang (2026-08-04): bác sĩ ký xong, kết quả VẪN CHƯA tới tay
// bệnh nhân. Phải bấm thêm "Cho phép CSKH gửi". Lý do của anh: *"nếu trường hợp
// bệnh án nguy hiểm thì phải cảnh báo CSKH chưa được gửi"* — có những kết quả
// bác sĩ muốn tự gọi báo, hoặc muốn gặp trực tiếp, chứ không để CSKH nhắn đi.
//
// Panel này KHÔNG tự bấm gì. Nó chỉ hiện trạng thái thật và mở đúng nút hợp lệ
// cho từng trạng thái — vì sau chữ ký, hồ sơ bị khoá theo TT13/2011/TT-BYT và
// đường quay lại duy nhất là đính chính có lý do.

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, FileSignature, Send } from "lucide-react";

interface Status {
  state: "DRAFT" | "SIGNED" | "RELEASED" | "AMENDED";
  version: number;
  signed_at: string | null;
  signed_by_name: string | null;
  released_at: string | null;
  released_by_name: string | null;
  missing: string[];
  can_sign: boolean;
  can_release: boolean;
  can_amend: boolean;
}

const LABEL: Record<Status["state"], { text: string; bg: string; fg: string }> = {
  DRAFT: { text: "Bản nháp", bg: "var(--surface-sunken)", fg: "var(--ink-muted)" },
  SIGNED: {
    text: "Đã ký — CSKH chưa gửi được",
    bg: "var(--warning-bg)",
    fg: "var(--warning)",
  },
  RELEASED: {
    text: "Đã cho phép gửi",
    bg: "var(--success-bg)",
    fg: "var(--success)",
  },
  AMENDED: {
    text: "Đã đính chính",
    bg: "var(--brand-50)",
    fg: "var(--brand-700)",
  },
};

/** Bốn mục SOAP mà đính chính sửa được — khớp REQUIRED_SOAP ở backend. */
const SOAP = [
  { key: "soap_subjective", label: "Lý do khám / triệu chứng", json: "ly_do" },
  { key: "soap_objective", label: "Khám lâm sàng", json: "kham" },
  { key: "soap_assessment", label: "Chẩn đoán", json: "chan_doan" },
  { key: "soap_plan", label: "Hướng xử trí", json: "xu_tri" },
];

export default function ClinicalSignPanel({
  visitId,
  isDoctor,
  onChanged,
}: {
  visitId: string | null;
  /** Chỉ bác sĩ thấy nút. Backend cũng chặn — đây là để không bày nút vô dụng. */
  isDoctor: boolean;
  onChanged?: () => void;
}) {
  const [st, setSt] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [amending, setAmending] = useState(false);
  const [reason, setReason] = useState("");
  const [field, setField] = useState(SOAP[2].key);
  const [value, setValue] = useState("");

  const load = useCallback(async () => {
    if (!visitId) return;
    try {
      const r = await fetch(`/api/clinical/${visitId}/status`);
      if (!r.ok) return;
      setSt((await r.json()) as Status);
    } catch {
      // Giữ trạng thái cũ. Panel này không được đoán — đoán sai một chiều là
      // bày ra nút "Ký" cho một hồ sơ đã ký.
    }
  }, [visitId]);

  useEffect(() => {
    // Bọc trong một tick: gọi load() thẳng trong thân effect là setState đồng
    // bộ trong effect — đúng thứ `react-hooks/set-state-in-effect` chặn, và nó
    // có lý do (render lan tầng). Huỷ khi panel đóng để không setState lên một
    // component đã gỡ.
    let alive = true;
    const t = setTimeout(() => {
      if (alive) void load();
    }, 0);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [load]);

  async function act(path: string, body?: unknown, ok?: string) {
    setBusy(true);
    setMsg(null);
    try {
      const r = await fetch(`/api/clinical/${visitId}/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body ?? {}),
      });
      const out = (await r.json().catch(() => ({}))) as {
        ok?: boolean;
        error?: string;
        renotify_created?: boolean;
      };
      if (!r.ok || !out.ok) {
        setMsg(`✗ ${out.error ?? `Lỗi máy chủ (${r.status})`}`);
        return;
      }
      setMsg(
        out.renotify_created
          ? "✓ Đã đính chính. Bản cũ ĐÃ gửi cho bệnh nhân — hệ thống vừa tạo việc cho CSKH gọi lại."
          : (ok ?? "✓ Xong"),
      );
      setAmending(false);
      setReason("");
      setValue("");
      await load();
      onChanged?.();
    } finally {
      setBusy(false);
    }
  }

  if (!visitId || !st) return null;
  const tone = LABEL[st.state];

  return (
    <div className="mt-3 rounded-lg border border-line bg-surface-muted p-3">
      <div className="flex flex-wrap items-center gap-2">
        <FileSignature size={15} className="text-ink-muted" />
        <span className="text-sm font-semibold text-ink">Chốt hồ sơ</span>
        <span
          className="rounded-full px-2 py-0.5 text-xs font-semibold"
          style={{ background: tone.bg, color: tone.fg }}
        >
          {tone.text}
        </span>
        {st.version > 1 && (
          <span className="text-xs text-ink-muted">phiên bản {st.version}</span>
        )}
      </div>

      {st.signed_at && (
        <div className="mt-1.5 text-xs text-ink-muted">
          Ký bởi {st.signed_by_name ?? "—"} lúc{" "}
          {new Date(st.signed_at).toLocaleString("vi-VN", {
            timeZone: "Asia/Ho_Chi_Minh",
            day: "2-digit",
            month: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          })}
          {st.released_at
            ? ` · cho phép gửi bởi ${st.released_by_name ?? "—"}`
            : ""}
        </div>
      )}

      {/* Còn thiếu gì thì NÓI ĐỦ, không nói một mục rồi im — bác sĩ điền xong
          lại bấm, lại bị chặn là cách nhanh nhất để người ta ghét cái nút. */}
      {st.state === "DRAFT" && st.missing.length > 0 && (
        <div className="mt-2 text-xs text-warning">
          Chưa ký được, còn thiếu: <b>{st.missing.join(" · ")}</b>
        </div>
      )}

      {isDoctor && (
        <div className="mt-3 flex flex-wrap gap-2">
          {st.state === "DRAFT" && (
            <button
              disabled={busy || !st.can_sign}
              onClick={() => act("sign", {}, "✓ Đã ký bệnh án")}
              className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-brand-600 px-3 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
            >
              <FileSignature size={14} /> Ký bệnh án
            </button>
          )}

          {st.can_release && (
            <button
              disabled={busy}
              onClick={() =>
                act("release", {}, "✓ Đã cho phép CSKH gửi kết quả")
              }
              className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-success px-3 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              <Send size={14} /> Cho phép CSKH gửi
            </button>
          )}

          {st.can_amend && !amending && (
            <button
              disabled={busy}
              onClick={() => setAmending(true)}
              className="inline-flex min-h-9 items-center gap-1.5 rounded-control border border-line bg-surface px-3 text-sm font-semibold text-ink-soft hover:bg-surface-sunken"
            >
              <AlertTriangle size={14} /> Đính chính
            </button>
          )}
        </div>
      )}

      {/* Hồ sơ đã ký nhưng CHƯA cho phép gửi — nói rõ hệ quả, vì đây chính là
          tình huống Quang muốn có: kết quả nguy hiểm thì giữ lại. */}
      {st.state === "SIGNED" && (
        <div className="mt-2 rounded-md bg-warning-bg px-2.5 py-1.5 text-xs text-warning">
          Hồ sơ đã ký nhưng <b>chưa cho phép gửi</b> — CSKH không thấy nút gửi
          kết quả cho bệnh nhân.
        </div>
      )}

      {amending && (
        <div className="mt-3 space-y-2 rounded-lg border border-warning/40 bg-warning-bg p-2.5">
          <div className="text-xs font-semibold text-warning">
            Đính chính tạo PHIÊN BẢN MỚI. Bản cũ được giữ nguyên và xem lại
            được.
          </div>
          <select
            value={field}
            onChange={(e) => setField(e.target.value)}
            className="w-full rounded-control border border-line bg-white px-2 py-1.5 text-sm"
          >
            {SOAP.map((f) => (
              <option key={f.key} value={f.key}>
                {f.label}
              </option>
            ))}
          </select>
          <textarea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            rows={2}
            placeholder="Nội dung đúng…"
            className="w-full rounded-control border border-line bg-white px-2 py-1.5 text-sm"
          />
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Lý do đính chính (bắt buộc)"
            className="w-full rounded-control border border-line bg-white px-2 py-1.5 text-sm"
          />
          <div className="flex gap-2">
            <button
              disabled={busy || !reason.trim() || !value.trim()}
              onClick={() => {
                const f = SOAP.find((x) => x.key === field);
                if (!f) return;
                // Các cột SOAP là jsonb dạng {"chan_doan": "..."} — gửi object,
                // không gửi chuỗi trần.
                void act(
                  "amend",
                  {
                    reason: reason.trim(),
                    corrected: { [f.key]: { [f.json]: value.trim() } },
                  },
                  "✓ Đã đính chính",
                );
              }}
              className="min-h-9 rounded-lg bg-danger px-3 text-sm font-semibold text-white disabled:opacity-50"
            >
              Xác nhận đính chính
            </button>
            <button
              onClick={() => {
                setAmending(false);
                setReason("");
                setValue("");
              }}
              className="min-h-9 rounded-control border border-line bg-surface px-3 text-sm text-ink-soft"
            >
              Huỷ
            </button>
          </div>
        </div>
      )}

      {msg && (
        <div
          className={`mt-2 flex items-start gap-1.5 text-xs ${
            msg.startsWith("✗") ? "text-danger" : "text-success"
          }`}
        >
          {msg.startsWith("✗") ? null : (
            <CheckCircle2 size={13} className="mt-0.5 shrink-0" />
          )}
          <span>{msg}</span>
        </div>
      )}
    </div>
  );
}
