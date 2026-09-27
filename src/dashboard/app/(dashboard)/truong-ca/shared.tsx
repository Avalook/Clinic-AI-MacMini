"use client";

// Phần dùng chung của năm màn điều phối.
//
// Trước đây cả năm màn nằm trong MỘT trang với một cột tab bên trái — tức là một
// thanh bên thứ hai, ngay cạnh thanh bên thật. Giờ mỗi màn là một URL riêng nên
// mở thẳng được, gửi link cho nhau được, và nút Quay lại của trình duyệt chạy
// đúng. Cái giá là ba thứ phải dùng chung: nhịp làm mới, chỉ báo dữ liệu cũ, và
// đường gọi thao tác — chúng ở đây.

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { DispatchAlert, DispatchPatient, DispatchRoom } from "./types";
import { useNgheBang } from "../dung-nghe-bang";

// Yêu cầu kỹ thuật: dữ liệu trên bảng phải mới trong 2–3 giây.
//
// TRƯỚC: poll mỗi 3 giây. Đạt yêu cầu, nhưng bằng cách gõ vào server 20 lần
// mỗi phút cho MỖI tab đang mở — kể cả buổi chiều không có bệnh nhân nào — và
// vẫn trễ tới 3 giây.
//
// NAY: nghe dòng SSE chung, đọc lại ngay khi có thay đổi thật (≈0,3s), còn nhịp
// đếm chỉ còn là MẠCH ĐẬP: 30 giây một lần để (a) đỡ lúc dòng rớt, và (b) giữ
// đồng hồ "cũ X giây" nói thật. Không có mạch đập thì một buổi chiều yên ắng
// sẽ hiện "cũ 600 giây" trong khi màn hình hoàn toàn đúng — báo động giả, và
// báo động giả lặp lại là cách nhanh nhất để người ta bỏ qua báo động thật.
const HEARTBEAT_MS = 30_000;

// Bảng quyết định nội dung bảng điều phối — những bảng `_OVERVIEW_SQL` và
// `_STATIONS_SQL` (dispatch_service.py) đọc mà có trigger `trg_notify_*`. Ba
// bảng đầu là luồng cũ; bốn bảng sau là luồng khám mới (lượt, hàng chờ, chỉ
// định), thiếu chúng thì khách đi luồng mới đổi phòng mà bảng đứng im.
//
// 27/09/2026: bỏ `postgres_changes` của Supabase Realtime — đường ấy chết vì
// Postgres từ chối plugin wal2json, nên màn này chỉ sống bằng mạch đập 30 giây.
// Nay nghe dòng SSE chung qua `useNgheBang` (LISTEN/NOTIFY, không mở kết nối
// mới).
const LIVE_TABLES = [
  "visit",
  "work_item",
  "appointment",
  "encounter_flow",
  "consultation",
  "service_order",
  "queue_entry",
] as const;

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

  // `alive` qua ref: `pull` được cả mạch đập lẫn tin SSE gọi, nên nó sống ngoài
  // effect. Gỡ màn giữa chừng một lượt đọc thì kết quả bị bỏ, không ghi vào
  // state của một màn đã đi.
  const aliveRef = useRef(true);
  const pull = useCallback(async () => {
    try {
      const [ov, al] = await Promise.all([
        fetch("/api/dispatch-read?what=overview").then((r) => r.json()),
        fetch("/api/dispatch-read?what=alerts").then((r) => r.json()),
      ]);
      if (!aliveRef.current) return;
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
      if (aliveRef.current) setData((d) => ({ ...d, ok: false }));
    }
  }, []);

  useEffect(() => {
    aliveRef.current = true;
    const beat = setInterval(pull, HEARTBEAT_MS);
    return () => {
      aliveRef.current = false;
      clearInterval(beat);
    };
  }, [pull]);

  // Một thao tác (chuyển phòng đụng visit + work_item) thành MỘT lần đọc — hook
  // gộp nhịp 250ms và bỏ qua tab đang ẩn.
  useNgheBang(LIVE_TABLES, () => void pull());

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
        // Áp tuyến: API bỏ các bước dịch vụ bác sĩ chưa chỉ định (15/09/2026).
        bo_qua_chua_chi_dinh?: string[];
      };
      const fail = !res.ok || !out.ok;
      const boQua = out.bo_qua_chua_chi_dinh?.length ?? 0;
      setToast(
        fail
          ? `✗ ${out.error ?? `Lỗi máy chủ (${res.status})`}`
          : boQua
            ? `${okMsg} — bỏ ${boQua} bước bác sĩ chưa chỉ định`
            : okMsg,
      );
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

/** "Tầng 2 · SA1" — hoặc chỉ tên phòng khi chưa khai tầng.
 *
 *  Cơ sở Kim Ngưu có ba tầng và SIÊU ÂM NẰM Ở HAI TẦNG KHÁC NHAU (báo cáo
 *  onsite 23/04: tầng 2 và tầng 4), còn mọi thứ khác ở tầng 1. Nên "sang SA2"
 *  là một câu chưa đủ để chỉ đường — Trưởng ca đang phải tự nhớ phần còn lại,
 *  40–60 lần mỗi buổi.
 */
export function roomWithFloor(
  name: string | null,
  floor: string | null,
): string {
  if (!name) return "—";
  return floor ? `${tenTang(floor)} · ${name}` : name;
}

/** "Tầng 1" — dữ liệu phòng có nơi khai "1", có nơi khai sẵn "Tầng 1". Ghép
 *  thẳng "Tầng " + floor ra "Tầng Tầng 1" (17/09/2026). */
export function tenTang(floor: string): string {
  const t = floor.trim();
  return /^tầng\b/i.test(t) ? t.charAt(0).toUpperCase() + t.slice(1) : `Tầng ${t}`;
}
