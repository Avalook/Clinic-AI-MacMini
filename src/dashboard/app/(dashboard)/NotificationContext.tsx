"use client";

// Phát hiện thông báo lịch làm việc CHẠY NỀN toàn app (gắn Provider ở layout) để
// dù đang ở trang nào cũng biết khi ca của mình được duyệt / từ chối. State chia
// sẻ qua context cho 2 nơi tiêu thụ:
//   - RosterBell (chỉ render ở Trang chủ): chuông + dropdown + popup ngắn.
//   - Nav (sidebar): chấm "!" đỏ nhấp nháy trên mục Trang chủ khi đang ở trang khác.
// Phát hiện bằng realtime (UPDATE work_roster của staff_id mình) + poll 20s dự
// phòng. Lần nạp đầu chỉ ghi nhận trạng thái (không báo) để khỏi spam ca cũ.

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { getSupabaseBrowser } from "../../lib/supabase-browser";
import {
  STATION_LABEL,
  SHIFT_LABEL,
  dayShort,
  fmtDayMonth,
  type Shift,
} from "../../lib/roster";

const POLL_MS = 20_000;
const TRANSIENT_MS = 7000;
const MAX_KEEP = 40;

export interface Notif {
  key: string;
  approved: boolean;
  title: string;
  detail: string;
  at: string; // giờ nhận, "HH:MM"
  /** Trang xử lý việc này. Backend đã đặt sẵn (`thong_bao.duong_dan`) từ lúc
   *  sinh thông báo — ví dụ "Cần xếp bác sĩ" trỏ /appointments/cho-xep-bac-si.
   *  Bỏ qua nó nghĩa là bắt người đọc tự đoán mình phải đi đâu. */
  duongDan?: string | null;
  /** Thông báo KHẨN do Trưởng ca gọi — chuông tô đỏ, không phải xanh. */
  khan?: boolean;
  /** Đã bấm "Đánh dấu đã đọc" chưa. ĐỌC ≠ ĐÃ XỬ LÝ: việc vẫn nằm trong danh
   *  sách, chỉ thôi tính vào chấm đỏ. */
  daDoc?: boolean;
}

interface MyRow {
  id: string;
  work_date: string;
  station: string;
  shift: Shift;
  status: "PENDING" | "APPROVED" | "REJECTED";
  reject_reason: string | null;
}

interface NotificationCtx {
  notifs: Notif[];
  unread: number;
  transient: Notif[];
  markAllRead: () => void;
  dismissTransient: (key: string) => void;
}

const Ctx = createContext<NotificationCtx>({
  notifs: [],
  unread: 0,
  transient: [],
  markAllRead: () => {},
  dismissTransient: () => {},
});

export const useNotifications = () => useContext(Ctx);

export function NotificationProvider({
  staffId,
  children,
}: {
  staffId: string | null;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [notifs, setNotifs] = useState<Notif[]>([]);
  const [transient, setTransient] = useState<Notif[]>([]);
  const [unread, setUnread] = useState(0);

  // NGUỒN THỨ HAI: Trưởng ca gọi bộ phận (bảng `thong_bao`).
  //
  // Provider này ra đời chỉ để nghe quyết định duyệt ca làm việc của CHÍNH
  // mình. Nhưng nó đã là hạ tầng chuông duy nhất chạy thật trong sản phẩm —
  // dựng thêm một cái chuông thứ hai cho thông báo điều phối nghĩa là nhân
  // viên phải học hai chỗ nhìn, và một trong hai sẽ bị bỏ quên.
  const [thongBao, setThongBao] = useState<Notif[]>([]);

  useEffect(() => {
    let stopped = false;
    async function doc() {
      try {
        const res = await fetch("/api/thong-bao", { cache: "no-store" });
        if (!res.ok) return;
        const d = (await res.json()) as {
          items?: {
            id: string;
            muc_do: string;
            tieu_de: string;
            noi_dung: string;
            tao_luc: string;
            duong_dan: string | null;
            nguoi_goi: string | null;
            da_doc_luc: string | null;
          }[];
        };
        if (stopped) return;
        setThongBao(
          (d.items ?? []).map((t) => ({
            key: `tb:${t.id}`,
            approved: false,
            khan: t.muc_do === "KHAN",
            daDoc: Boolean(t.da_doc_luc),
            title: t.tieu_de,
            duongDan: t.duong_dan,
            detail:
              (t.nguoi_goi ? `${t.nguoi_goi} gọi · ` : "") + t.noi_dung,
            at: new Date(t.tao_luc).toLocaleTimeString("vi-VN", {
              hour: "2-digit",
              minute: "2-digit",
            }),
          })),
        );
      } catch {
        /* mạng chập — lần poll sau thử lại */
      }
    }
    const first = setTimeout(doc, 0);
    const id = setInterval(doc, POLL_MS);
    return () => {
      stopped = true;
      clearTimeout(first);
      clearInterval(id);
    };
  }, []);

  // shownKeys = các quyết định ĐÃ ghi nhận ("id:status"). LƯU localStorage theo
  // staffId để thông báo SỐNG SÓT reload/đổi vai và bắt được cả quyết định xảy ra
  // lúc người dùng không mở app (so sánh với tập đã thấy, không chỉ diff trong phiên).
  const shownKeys = useRef<Set<string>>(new Set());
  const hydratedDone = useRef(false);

  function storeKey(id: string) {
    return `roster_notif_${id}`;
  }

  useEffect(() => {
    if (!staffId) return;
    const supabase = getSupabaseBrowser();
    let stopped = false;
    // Hydrate ở lần poll ĐẦU (trong callback async, không setState đồng bộ trong
    // thân effect) → tránh cảnh báo lint + lệch SSR/hydration.
    let hydratedOnce = false;
    let hadStore = false;

    function hydrateFromStore() {
      try {
        const raw = localStorage.getItem(storeKey(staffId!));
        if (raw) {
          hadStore = true;
          const saved = JSON.parse(raw) as {
            seen?: string[];
            notifs?: Notif[];
            unread?: number;
          };
          shownKeys.current = new Set(saved.seen ?? []);
          if (saved.notifs) setNotifs(saved.notifs);
          if (typeof saved.unread === "number") setUnread(saved.unread);
        }
      } catch {
        /* localStorage không khả dụng → bỏ qua, chạy bằng phiên hiện tại. */
      }
      hydratedDone.current = true;
    }

    function persist(nextNotifs: Notif[], nextUnread: number) {
      try {
        localStorage.setItem(
          storeKey(staffId!),
          JSON.stringify({
            seen: [...shownKeys.current],
            notifs: nextNotifs,
            unread: nextUnread,
          }),
        );
      } catch {
        /* bỏ qua nếu không ghi được */
      }
    }

    function label(r: MyRow) {
      const st = STATION_LABEL[r.station] ?? r.station;
      const sh = r.shift !== "FULL" ? ` (${SHIFT_LABEL[r.shift]})` : "";
      return `${dayShort(r.work_date)} ${fmtDayMonth(r.work_date)} · ${st}${sh}`;
    }

    function notify(r: MyRow) {
      if (r.status !== "APPROVED" && r.status !== "REJECTED") return;
      const key = `${r.id}:${r.status}`;
      if (shownKeys.current.has(key)) return;
      shownKeys.current.add(key);
      const approved = r.status === "APPROVED";
      const now = new Date();
      const at = `${String(now.getHours()).padStart(2, "0")}:${String(
        now.getMinutes(),
      ).padStart(2, "0")}`;
      const n: Notif = {
        key,
        approved,
        title: approved ? "Ca làm việc đã được chấp nhận" : "Ca làm việc bị từ chối",
        detail: approved
          ? label(r)
          : `${label(r)}${r.reject_reason ? " — Lý do: " + r.reject_reason : ""}`,
        at,
      };
      setNotifs((l) => [n, ...l].slice(0, MAX_KEEP));
      setUnread((u) => u + 1);
      setTransient((t) => [...t, n]);
      setTimeout(() => {
        if (!stopped) setTransient((t) => t.filter((x) => x.key !== key));
      }, TRANSIENT_MS);
    }

    async function poll() {
      if (!hydratedOnce) {
        hydrateFromStore();
        hydratedOnce = true;
      }
      const { data } = await supabase
        .from("work_roster")
        .select("id, work_date, station, shift, status, reject_reason")
        .eq("staff_id", staffId)
        .limit(200);
      if (stopped) return;
      const rows = (data as MyRow[] | null) ?? [];
      const decided = rows.filter(
        (r) => r.status === "APPROVED" || r.status === "REJECTED",
      );
      // Lần ĐẦU TIÊN của một danh tính (chưa có store): ghi nhận im lặng để khỏi báo
      // dồn quyết định cũ. Các lần sau: báo mọi quyết định CHƯA thấy (kể cả khi xảy
      // ra lúc app đóng — vì so với tập đã lưu, không phải diff phiên).
      if (!hadStore) {
        for (const r of decided) shownKeys.current.add(`${r.id}:${r.status}`);
        persist([], 0);
        hadStore = true;
        return;
      }
      for (const r of decided) notify(r);
    }

    void poll();
    const timer = setInterval(poll, POLL_MS);

    const channel = supabase
      .channel("roster-my-decisions")
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "work_roster",
          filter: `staff_id=eq.${staffId}`,
        },
        (payload) => {
          const r = payload.new as MyRow;
          notify(r);
          router.refresh();
        },
      )
      .subscribe();

    return () => {
      stopped = true;
      clearInterval(timer);
      void supabase.removeChannel(channel);
    };
  }, [staffId, router]);

  // Lưu localStorage mỗi khi lịch sử / số chưa đọc đổi — CHỈ sau khi hydrate xong
  // (tránh ghi đè dữ liệu cũ bằng state rỗng lúc mới mount). Chỉ ghi, không setState.
  useEffect(() => {
    if (!staffId || !hydratedDone.current) return;
    try {
      localStorage.setItem(
        storeKey(staffId),
        JSON.stringify({ seen: [...shownKeys.current], notifs, unread }),
      );
    } catch {
      /* bỏ qua */
    }
  }, [staffId, notifs, unread]);

  function markAllRead() {
    setUnread(0);
    // TẮT CHẤM ĐỎ Ở CẢ MÁY CHỦ, không chỉ trong tab này.
    //
    // Con số trên chuông là `unread` (thông báo tức thời, chỉ sống trong
    // trình duyệt) CỘNG số thông báo chưa đọc từ máy chủ. `setUnread(0)` một
    // mình chỉ xoá vế đầu — nên chấm đỏ ở lại, và tải lại trang là nó y nguyên.
    // Quang: "làm cho mấy báo động cứ hiện đỏ dù đã hoàn thành".
    //
    // Đặt cờ tại chỗ TRƯỚC khi máy chủ trả lời: lượt poll kế tiếp còn cách tới
    // 20 giây, và một cái nút bấm xong không đổi gì trong 20 giây thì người ta
    // sẽ bấm lại vài lần.
    setThongBao((ds) => ds.map((t) => ({ ...t, daDoc: true })));
    void fetch("/api/thong-bao", { method: "POST" }).catch(() => {
      /* mạng chập — lượt poll sau sẽ trả về trạng thái thật */
    });
  }

  return (
    <Ctx.Provider
      value={{
        // Thông báo KHẨN lên đầu — chúng là thứ có người đang chờ mình xử lý.
        notifs: [...thongBao, ...notifs],
        // CHỈ ĐẾM CÁI CHƯA ĐỌC. Trước đây cộng thẳng `thongBao.length`, tức
        // mọi việc đang mở đều tính là "mới" mãi mãi.
        unread: unread + thongBao.filter((t) => !t.daDoc).length,
        transient,
        markAllRead,
        dismissTransient: (key) =>
          setTransient((t) => t.filter((x) => x.key !== key)),
      }}
    >
      {children}
    </Ctx.Provider>
  );
}
