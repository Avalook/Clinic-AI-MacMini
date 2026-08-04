"use client";

// Phần dùng chung của năm màn điều phối.
//
// Trước đây cả năm màn nằm trong MỘT trang với một cột tab bên trái — tức là một
// thanh bên thứ hai, ngay cạnh thanh bên thật. Giờ mỗi màn là một URL riêng nên
// mở thẳng được, gửi link cho nhau được, và nút Quay lại của trình duyệt chạy
// đúng. Cái giá là ba thứ phải dùng chung: nhịp làm mới, chỉ báo dữ liệu cũ, và
// đường gọi thao tác — chúng ở đây.

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { DispatchAlert, DispatchPatient, DispatchRoom } from "./types";

/** Yêu cầu kỹ thuật: dữ liệu trên bảng phải mới trong 2–3 giây. */
const REFRESH_MS = 3000;

export interface LiveData {
  patients: DispatchPatient[];
  rooms: DispatchRoom[];
  alerts: DispatchAlert[];
  /** false = lần đọc gần nhất thất bại. Màn phải nói ra, không vẽ bảng trống. */
  ok: boolean;
  /** Số giây kể từ lần đọc THÀNH CÔNG gần nhất. */
  staleSeconds: number;
}

/**
 * Giữ dữ liệu điều phối luôn mới, và biết nó cũ bao nhiêu giây khi không mới được.
 *
 * `fetchedAt` CHỈ được cập nhật khi đọc thành công — đó chính là cách đồng hồ
 * "cũ X giây" chạy lên khi mạng hỏng. Đặt lại nó ở mọi vòng lặp sẽ khiến màn
 * hình luôn tự tin là đang cập nhật, kể cả khi đã mất kết nối từ lâu.
 */
export function useDispatchLive(initial: {
  patients: DispatchPatient[];
  rooms: DispatchRoom[];
  alerts: DispatchAlert[];
  ok: boolean;
}): LiveData {
  const [data, setData] = useState(initial);
  const [fetchedAt, setFetchedAt] = useState(() => Date.now());
  const [staleSeconds, setStale] = useState(0);

  useEffect(() => {
    const t = setInterval(async () => {
      try {
        const [ov, al] = await Promise.all([
          fetch("/api/dispatch-read?what=overview").then((r) => r.json()),
          fetch("/api/dispatch-read?what=alerts").then((r) => r.json()),
        ]);
        if (!ov.ok) {
          setData((d) => ({ ...d, ok: false }));
          return;
        }
        setData({
          patients: ov.patients ?? [],
          rooms: ov.rooms ?? [],
          alerts: al.items ?? [],
          ok: true,
        });
        setFetchedAt(Date.now());
      } catch {
        setData((d) => ({ ...d, ok: false }));
      }
    }, REFRESH_MS);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const t = setInterval(
      () => setStale(Math.round((Date.now() - fetchedAt) / 1000)),
      1000,
    );
    return () => clearInterval(t);
  }, [fetchedAt]);

  return { ...data, staleSeconds };
}

/** Gọi một thao tác điều phối, kèm thông báo và làm mới trang. */
export function useDispatchAction() {
  const router = useRouter();
  const [toast, setToast] = useState<string | null>(null);

  const act = useCallback(
    async (action: string, body: unknown, okMsg: string) => {
      const res = await fetch(`/api/dispatch/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const out = (await res.json().catch(() => ({}))) as {
        ok?: boolean;
        error?: string;
      };
      const fail = !res.ok || !out.ok;
      setToast(fail ? `✗ ${out.error ?? `Lỗi máy chủ (${res.status})`}` : okMsg);
      setTimeout(() => setToast(null), 3500);
      if (!fail) router.refresh();
      return !fail;
    },
    [router],
  );

  return { act, toast };
}

export type ActFn = ReturnType<typeof useDispatchAction>["act"];

/** "Cập nhật trực tiếp" hoặc "Dữ liệu cũ X giây" — không bao giờ im lặng. */
export function LiveBadge({ seconds, ok }: { seconds: number; ok: boolean }) {
  const stale = !ok || seconds > 10;
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "4px 10px",
        borderRadius: 999,
        fontSize: 11,
        background: stale ? "var(--warning-bg)" : "var(--surface-muted)",
        color: stale ? "var(--warning)" : "var(--ink-muted)",
      }}
    >
      <span
        className={stale ? undefined : "pulse-dot"}
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: stale ? "var(--warning)" : "var(--success)",
        }}
      />
      {stale ? `Dữ liệu cũ ${seconds} giây` : "Cập nhật trực tiếp"}
    </div>
  );
}

/** Dải báo khi không đọc được — bảng trống trông y hệt "hôm nay chưa có ai". */
export function ReadFailed({ ok }: { ok: boolean }) {
  if (ok) return null;
  return (
    <div
      role="alert"
      className="card"
      style={{
        marginBottom: 12,
        borderColor: "var(--danger)",
        background: "var(--danger-bg)",
        color: "var(--danger)",
        fontSize: 13,
      }}
    >
      Không đọc được dữ liệu điều phối. Các con số bên dưới có thể đã cũ — tải
      lại trang.
    </div>
  );
}

export function Toast({ text }: { text: string | null }) {
  if (!text) return null;
  return <div className="toast">{text}</div>;
}
