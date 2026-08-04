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
import { getSupabaseBrowser } from "../../../lib/supabase-browser";

// Yêu cầu kỹ thuật: dữ liệu trên bảng phải mới trong 2–3 giây.
//
// TRƯỚC: poll mỗi 3 giây. Đạt yêu cầu, nhưng bằng cách gõ vào server 20 lần
// mỗi phút cho MỖI tab đang mở — kể cả buổi chiều không có bệnh nhân nào — và
// vẫn trễ tới 3 giây.
//
// NAY: nghe realtime, đọc lại ngay khi có thay đổi thật (≈0,3s), còn nhịp đếm
// chỉ còn là MẠCH ĐẬP: 30 giây một lần để (a) đỡ lúc websocket rớt, và (b) giữ
// đồng hồ "cũ X giây" nói thật. Không có mạch đập thì một buổi chiều yên ắng
// sẽ hiện "cũ 600 giây" trong khi màn hình hoàn toàn đúng — báo động giả, và
// báo động giả lặp lại là cách nhanh nhất để người ta bỏ qua báo động thật.
const HEARTBEAT_MS = 30_000;

// Bảng quyết định nội dung bảng điều phối. Đều nằm trong publication
// `supabase_realtime` (20260803000004) — subscribe một bảng chưa publish thì
// im lặng không bao giờ bắn, nên danh sách này phải khớp.
const LIVE_TABLES = ["visit", "work_item", "appointment"] as const;

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
    let alive = true;
    const pull = async () => {
      try {
        const [ov, al] = await Promise.all([
          fetch("/api/dispatch-read?what=overview").then((r) => r.json()),
          fetch("/api/dispatch-read?what=alerts").then((r) => r.json()),
        ]);
        if (!alive) return;
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
        if (alive) setData((d) => ({ ...d, ok: false }));
      }
    };

    // Gộp một chuỗi thay đổi của cùng một thao tác (chuyển phòng đụng visit +
    // work_item) thành một lần đọc.
    let debounce: ReturnType<typeof setTimeout> | null = null;
    const bump = () => {
      if (debounce) clearTimeout(debounce);
      debounce = setTimeout(() => void pull(), 250);
    };

    const supabase = getSupabaseBrowser();
    let channel = supabase.channel("dispatch-live");
    for (const table of LIVE_TABLES) {
      channel = channel.on(
        "postgres_changes",
        { event: "*", schema: "public", table },
        bump,
      );
    }
    channel.subscribe();

    const beat = setInterval(pull, HEARTBEAT_MS);
    return () => {
      alive = false;
      if (debounce) clearTimeout(debounce);
      clearInterval(beat);
      void supabase.removeChannel(channel);
    };
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
// Ngưỡng báo "dữ liệu cũ" phải BÁM theo mạch đập, không phải một số viết cứng.
//
// Bản trước để 10 giây vì lúc đó poll mỗi 3 giây — quá ba nhịp là thật sự có
// vấn đề. Nay mạch đập 30 giây, nên 10 giây sẽ bật cảnh báo vàng suốt mọi buổi
// vắng trong khi màn hình hoàn toàn đúng. Báo động giả lặp lại là cách nhanh
// nhất để Trưởng ca thôi nhìn cái badge này.
//
// 1,5 nhịp: đủ để bỏ lỡ một mạch mà chưa kêu, đủ sớm để không im khi mạng hỏng
// thật (realtime rớt thì lần đọc kế tiếp cũng hỏng theo, và `ok` sẽ tự nói).
const STALE_AFTER_S = Math.round((HEARTBEAT_MS * 1.5) / 1000);

export function LiveBadge({ seconds, ok }: { seconds: number; ok: boolean }) {
  const stale = !ok || seconds > STALE_AFTER_S;
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
