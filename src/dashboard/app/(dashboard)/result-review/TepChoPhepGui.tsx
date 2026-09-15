"use client";

/**
 * Tệp kết quả CSKH đã tải lên, chờ BÁC SĨ cho phép gửi khách (15/09/2026).
 *
 * CONTEXT v1.0: upload → bác sĩ đánh giá/cho phép gửi → gửi. Bác sĩ mở tệp
 * xem, rồi bấm cho phép; CSKH chỉ xác nhận "đã gửi" được sau bước này.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";

import { VN_TZ } from "../../../lib/datetime";

export interface TepChoPhep {
  id: string;
  ten_hien_thi: string | null;
  loai_tep: string;
  tai_len_luc: string;
  ten_khach: string | null;
  patient_code: string | null;
  tai_len_boi: string | null;
}

export default function TepChoPhepGui({ items }: { items: TepChoPhep[] }) {
  const router = useRouter();
  const [dang, setDang] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  async function choPhep(id: string) {
    setDang(id);
    setLoi(null);
    try {
      const res = await fetch(`/api/cskh/ket-qua/${id}/cho-phep-gui`, { method: "POST" });
      if (!res.ok) {
        const body = (await res.json().catch(() => null)) as { error?: string } | null;
        setLoi(body?.error ?? `Không cho phép được (HTTP ${res.status})`);
        return;
      }
      router.refresh();
    } finally {
      setDang(null);
    }
  }

  return (
    <section className="rounded-control border border-line bg-surface">
      <div className="border-b border-line p-3">
        <h2 className="text-sm font-semibold text-ink">Tệp kết quả chờ cho phép gửi</h2>
        <p className="mt-0.5 text-xs text-ink-muted">
          {items.length} tệp · mở xem rồi cho phép để CSKH gửi khách
        </p>
      </div>
      {items.length === 0 ? (
        <p className="p-4 text-sm text-ink-muted">Không có tệp nào chờ.</p>
      ) : (
        <ul>
          {items.map((t) => (
            <li
              key={t.id}
              className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2.5 text-sm last:border-b-0"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium text-ink">
                  {t.ten_khach ?? "Chưa có tên"}
                  {t.patient_code ? (
                    <span className="ml-1 text-xs text-ink-muted">{t.patient_code}</span>
                  ) : null}
                </p>
                <p className="truncate text-xs text-ink-muted">
                  {t.ten_hien_thi ?? "(không tên)"} · {t.loai_tep} ·{" "}
                  {new Date(t.tai_len_luc).toLocaleString("vi-VN", { timeZone: VN_TZ })}
                  {t.tai_len_boi ? ` · ${t.tai_len_boi} tải lên` : ""}
                </p>
              </div>
              <a
                href={`/api/cskh/ket-qua/${t.id}/noi-dung`}
                target="_blank"
                rel="noreferrer"
                className="text-xs font-semibold text-brand-700 hover:underline"
              >
                Mở tệp
              </a>
              <button
                type="button"
                disabled={dang !== null}
                onClick={() => void choPhep(t.id)}
                className="rounded-control bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
              >
                {dang === t.id ? "Đang ghi…" : "Cho phép gửi"}
              </button>
            </li>
          ))}
        </ul>
      )}
      {loi ? <p className="px-3 pb-3 text-sm text-danger">{loi}</p> : null}
    </section>
  );
}
