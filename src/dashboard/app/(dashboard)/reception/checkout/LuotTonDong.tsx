"use client";

// LƯỢT TỒN ĐỌNG TỪ HÔM TRƯỚC (đợt 3, 27/09/2026 — C8).
//
// API `GET /reception/checkout/ton-dong` có từ 06/08 mà chưa màn nào đọc: lượt
// còn mở từ những ngày trước không hiện ở đâu, trong khi bộ canh gác cứ báo
// "N lượt khám từ hôm trước chưa đóng". Danh sách này và cảnh báo ấy dùng CÙNG
// một câu (backend `services/luot_treo.py`) — đóng hết ở đây là lần canh gác kế
// tiếp tự tắt cảnh báo.
//
// Mỗi lượt: [Đóng lượt] → dải xác nhận TẠI CHỖ bắt gõ lý do → đóng dạng "khách
// về giữa chừng" (INCOMPLETE — không chốt hồ sơ bệnh án, bác sĩ vẫn ký tiếp
// được). Màn không tự quyết gì: lượt nào tồn đọng, đóng được không, đều do máy
// chủ trả lời.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";
import { fmtDayTime } from "@/lib/datetime";

import { useNgheBang } from "../../dung-nghe-bang";
import type { Blocker } from "./CheckoutBoard";

interface LuotTon {
  visit_id: string;
  patient_name: string | null;
  patient_code: string | null;
  room_name: string | null;
  checked_in_at: string | null;
  blockers: Blocker[];
}

const BANG = ["visit", "work_item"] as const;

/** Đọc danh sách từ máy chủ. `null` = không đọc được (khác "không có lượt nào"). */
async function docTonDong(): Promise<LuotTon[] | null> {
  try {
    const r = await fetch("/api/reception/checkout?ton_dong=1", { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as
      | { ok?: boolean; items?: LuotTon[] }
      | null;
    if (!r.ok || !d || d.ok === false) return null;
    return d.items ?? [];
  } catch {
    return null;
  }
}

export default function LuotTonDong({ onDaDong }: { onDaDong?: () => void }) {
  const [ds, setDs] = useState<LuotTon[] | null>(null);
  const [docLoi, setDocLoi] = useState(false);
  const [dangHoi, setDangHoi] = useState<string | null>(null);
  const [lyDo, setLyDo] = useState("");
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);

  const nhan = useCallback((kq: LuotTon[] | null) => {
    if (kq === null) {
      setDocLoi(true);
      return;
    }
    setDs(kq);
    setDocLoi(false);
  }, []);

  const tai = useCallback(async () => nhan(await docTonDong()), [nhan]);

  useEffect(() => {
    let bo = false;
    void docTonDong().then((kq) => {
      if (!bo) nhan(kq);
    });
    return () => {
      bo = true;
    };
  }, [nhan]);
  useNgheBang(BANG, () => void tai());

  async function dong(l: LuotTon) {
    const ly = lyDo.trim();
    if (!ly) return;
    setDangGui(true);
    setLoi(null);
    try {
      const r = await fetch("/api/reception/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          visit_id: l.visit_id,
          incomplete: true,
          incomplete_reason: ly,
        }),
      });
      const d = (await r.json().catch(() => ({}))) as {
        ok?: boolean;
        error?: string;
        message?: string;
      };
      if (!r.ok || !d.ok) {
        setLoi(d.message ?? d.error ?? `Không đóng được lượt (lỗi ${r.status}).`);
        return;
      }
      setBao(`Đã đóng lượt của ${l.patient_name ?? "khách"} — ghi là khách về giữa chừng.`);
      setDangHoi(null);
      setLyDo("");
      await tai();
      onDaDong?.();
    } catch {
      setLoi("Mất kết nối — CHƯA đóng được lượt.");
    } finally {
      setDangGui(false);
    }
  }

  if (docLoi && ds === null) {
    return (
      <p role="alert" className="text-meta text-danger">
        Không đọc được danh sách lượt tồn đọng từ hôm trước — tải lại trang.
      </p>
    );
  }
  if (!ds || ds.length === 0) return null;

  return (
    <section
      aria-label="Lượt tồn đọng từ hôm trước"
      className="min-w-0 rounded-card border border-warning bg-surface shadow-card"
    >
      <div className="border-b border-line px-4 py-3">
        <h2 className="flex flex-wrap items-center gap-2 text-emph font-semibold text-ink">
          Lượt tồn đọng từ hôm trước
          <Chip tone="warning">{ds.length}</Chip>
        </h2>
        <p className="mt-1 text-meta text-ink-muted">
          Check-in từ những ngày trước, còn mở, chưa check-out. Khách đã về thì
          đóng lượt và ghi lý do — hết lượt ở đây là hết cảnh báo &ldquo;lượt
          treo&rdquo;.
        </p>
        {bao ? <p className="mt-1 text-meta text-success">{bao}</p> : null}
      </div>
      <ul className="max-h-[50vh] divide-y divide-line overflow-y-auto">
        {ds.map((l) => (
          <li key={l.visit_id} className="space-y-2 px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-body font-semibold text-ink">
                  {l.patient_name ?? "Chưa rõ tên"}
                  <span className="font-normal text-ink-muted">
                    {" "}
                    · {l.patient_code ?? "—"}
                  </span>
                </p>
                <p className="text-meta text-ink-muted">
                  Check-in {l.checked_in_at ? fmtDayTime(l.checked_in_at) : "—"}
                  {l.room_name ? ` · ${l.room_name}` : ""}
                  {l.blockers.length > 0 ? ` · còn ${l.blockers.length} việc` : ""}
                </p>
              </div>
              {dangHoi !== l.visit_id ? (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    setDangHoi(l.visit_id);
                    setLyDo("");
                    setLoi(null);
                  }}
                >
                  Đóng lượt
                </Button>
              ) : null}
            </div>
            {dangHoi === l.visit_id ? (
              <XacNhanTaiCho
                cau={`Đóng lượt của ${l.patient_name ?? "khách"} — ghi là khách về giữa chừng?`}
                nhanDongY="Đóng lượt"
                dangGui={dangGui}
                choDongY={lyDo.trim().length > 0}
                onThoi={() => {
                  setDangHoi(null);
                  setLyDo("");
                  setLoi(null);
                }}
                onDongY={() => void dong(l)}
              >
                <label className="block text-meta text-ink-muted">
                  Lý do (bắt buộc — CSKH đọc để biết gọi lại nói gì)
                  <textarea
                    rows={2}
                    autoFocus
                    value={lyDo}
                    onChange={(e) => setLyDo(e.target.value)}
                    maxLength={500}
                    placeholder="Vd: khách đã về hôm qua, quên check-out"
                    className="mt-1 w-full resize-none rounded-control border border-line bg-surface px-3 py-2 text-body text-ink outline-none focus:border-brand-500"
                  />
                </label>
                {loi ? <p className="mt-1 text-meta text-danger">{loi}</p> : null}
              </XacNhanTaiCho>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
