"use client";

// Phát hiện thông báo lịch làm việc CHẠY NỀN toàn app (gắn Provider ở layout) để
// dù đang ở trang nào cũng biết khi ca của mình được duyệt / từ chối. State chia
// sẻ qua context cho 2 nơi tiêu thụ:
//   - RosterBell (chỉ render ở Trang chủ): chuông + dropdown + popup ngắn.
//   - Nav (sidebar): chấm "!" đỏ nhấp nháy trên mục Trang chủ khi đang ở trang khác.
// Phát hiện bằng dòng SSE chung (bảng `work_roster` và `thong_bao` bắn tin qua
// LISTEN/NOTIFY → RealtimeRefresher) + poll 20s dự phòng. Lần nạp đầu chỉ ghi
// nhận trạng thái (không báo) để khỏi spam ca cũ.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { SU_KIEN_DOI_CA } from "./dung-doi-ca";
import { useNgheBang } from "./dung-nghe-bang";
import {
  SHIFT_LABEL,
  dayShort,
  fmtDayMonth,
  type Shift,
} from "../../lib/roster";
import { nhipKhiHien } from "../../lib/nhip-khi-hien";

const POLL_MS = 20_000;
const TRANSIENT_MS = 7000;
const MAX_KEEP = 40;
/** Bảng mà chuông nghe qua dòng SSE chung — cần trigger `trg_notify_*`. */
const BANG_THONG_BAO = ["thong_bao"] as const;

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
  /** `thong_bao.id` — chỉ có với thông báo đến từ máy chủ. Cần để ĐÓNG việc
   *  (`POST /api/thong-bao/{id}/da-xu-ly`); thông báo ca làm việc sinh ở trình
   *  duyệt thì không có, và cũng không có việc gì để đóng. */
  thongBaoId?: string;
  /** Thông báo "chỉ định bị bỏ" (Khối 2, 06/10/2026): máy chủ nói nó KHÔNG có
   *  nút "Xong" — nút duy nhất là Hoàn tác dòng sổ `hoanTacSoId` (null = đã
   *  hoàn tác / không còn hoàn tác được). */
  chiHoanTac?: boolean;
  hoanTacSoId?: string | null;
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
  /** ĐÓNG một việc: bỏ hẳn khỏi chuông, cho mọi người cùng vai. */
  danhDauDaXuLy: (thongBaoId: string) => Promise<void>;
  /** Đọc lại danh sách từ máy chủ (vd. sau khi bấm Hoàn tác trong chuông). */
  docLai: () => void;
  dismissTransient: (key: string) => void;
}

const Ctx = createContext<NotificationCtx>({
  notifs: [],
  unread: 0,
  transient: [],
  markAllRead: () => {},
  danhDauDaXuLy: async () => {},
  docLai: () => {},
  dismissTransient: () => {},
});

export const useNotifications = () => useContext(Ctx);

export function NotificationProvider({
  staffId,
  tenViTri = {},
  children,
}: {
  staffId: string | null;
  /** Tên vị trí theo mã — từ danh mục trong database (CORE-C4). */
  tenViTri?: Readonly<Record<string, string>>;
  children: React.ReactNode;
}) {
  // Qua ref: layout dựng lại ở mỗi lần chuyển trang nên object này luôn mới —
  // đưa thẳng vào deps thì kênh realtime đóng/mở lại mỗi lần bấm menu.
  const tenViTriRef = useRef(tenViTri);
  useEffect(() => {
    tenViTriRef.current = tenViTri;
  }, [tenViTri]);
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

  // ĐỌC HOÀN CHỈNH, KHAI Ở CẤP COMPONENT.
  //
  // Trước đây `doc` nằm gọn trong `useEffect`, nên không chỗ nào ngoài vòng
  // poll gọi lại được nó. Nay `danhDauDaXuLy` cần đúng việc ấy khi máy chủ từ
  // chối: bỏ một dòng khỏi màn rồi mới biết là không đóng được thì phải trả nó
  // về ngay, không đợi 20 giây.
  const docThongBao = useCallback(async () => {
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
            chi_hoan_tac?: boolean;
            hoan_tac_so_id?: string | null;
          }[];
        };
        setThongBao(
          (d.items ?? []).map((t) => ({
            key: `tb:${t.id}`,
            thongBaoId: t.id,
            chiHoanTac: Boolean(t.chi_hoan_tac),
            hoanTacSoId: t.hoan_tac_so_id ?? null,
            approved: false,
            khan: t.muc_do === "KHAN",
            daDoc: Boolean(t.da_doc_luc),
            title: t.tieu_de,
            duongDan: t.duong_dan,
            detail:
              // "Chỉ định bị bỏ": câu máy chủ đã nêu tên người bỏ — không
              // thêm "X gọi ·" (đó là khuôn của trưởng ca gọi bộ phận).
              (t.nguoi_goi && !t.chi_hoan_tac ? `${t.nguoi_goi} gọi · ` : "") + t.noi_dung,
            at: new Date(t.tao_luc).toLocaleTimeString("vi-VN", {
              hour: "2-digit",
              minute: "2-digit",
            }),
          })),
        );
      } catch {
        /* mạng chập — lần poll sau thử lại */
      }
  }, []);

  // TAB ĐANG ẨN THÌ KHÔNG HỎI (21/08/2026).
  //
  // Chuông chỉ có nghĩa khi có người nhìn nó. Nhịp 20 giây nhân với mười tab
  // của cả phòng khám là ba mươi lượt gọi mỗi phút cho một cái chuông không ai
  // thấy — và mỗi lượt gọi chiếm một trong sáu kết nối HTTP/1.1 mà trình duyệt
  // cho phép tới origin này, đúng thứ đang khan hiếm (xem `lib/nhip-lam-moi`).
  //
  // Quay lại tab thì hỏi NGAY, không chờ hết nhịp: người ta vừa nhìn vào chuông.
  // Lần hỏi ấy do `useNgheBang` bên dưới làm — lúc tab hiện lại
  // `RealtimeRefresher` phát tin `null` và mọi người nghe đều hỏi lại. Bản trước
  // tự nghe thêm `visibilitychange` nên chuông hỏi HAI lần mỗi lần đổi tab (đo
  // prod 30/09/2026). Nhịp 20 giây nay huỷ hẳn lúc tab ẩn (`nhipKhiHien`), không
  // chỉ bỏ lượt.
  useEffect(() => {
    const first = setTimeout(() => void docThongBao(), 0);
    const goNhip = nhipKhiHien(() => void docThongBao(), POLL_MS, {
      hoiKhiHien: false,
    });
    return () => {
      clearTimeout(first);
      goNhip();
    };
  }, [docThongBao]);

  // THÔNG BÁO MỚI HIỆN NGAY, không đợi nhịp 20 giây (27/09/2026). Trưởng ca
  // gọi bộ phận là việc KHẨN — 20 giây là quá lâu cho một chuông đỏ. Bảng
  // `thong_bao` bắn tin qua trigger `trg_notify_thong_bao` (migration
  // 20260927000002); tin chỉ có tên bảng + phòng khám, nội dung vẫn đọc qua API
  // có kiểm người nhận. Nhịp 20 giây ở trên giữ làm lưới an toàn.
  useNgheBang(BANG_THONG_BAO, () => void docThongBao());

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
      const st = tenViTriRef.current[r.station] ?? r.station;
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
      // Qua backend (24/09/2026) — ca của chính mình.
      const res = await fetch("/api/roster?ca_cua_toi=1", { cache: "no-store" }).catch(
        () => null,
      );
      if (stopped || !res?.ok) return;
      const rows = (((await res.json().catch(() => null)) as { items?: MyRow[] } | null)
        ?.items ?? []) as MyRow[];
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
    // Tab ẩn thì im hẳn (bản trước hỏi /api/roster mỗi 20 giây cả khi ẩn). Hiện
    // lại thì không hỏi ở đây: `RealtimeRefresher` rung `SU_KIEN_DOI_CA` trong
    // lần bắt kịp, và tay nghe `khiDoiCa` ngay dưới đã hỏi lại một lần.
    const goNhip = nhipKhiHien(() => void poll(), POLL_MS, { hoiKhiHien: false });

    // QUYẾT ĐỊNH CA của mình: nghe chuông "ca trực vừa đổi" (SU_KIEN_DOI_CA) do
    // RealtimeRefresher rung khi bảng `work_roster` bắn tin qua dòng SSE chung —
    // đã gộp nhịp, và tab ẩn thì không rung. Tin chỉ nói "bảng đổi", không nói
    // ca của ai, nên hỏi lại đúng ca của mình qua API như lượt poll.
    //
    // Trước 27/09 chỗ này mở `postgres_changes` của Supabase Realtime lọc theo
    // staff_id — đường ấy chết từ lâu (Postgres từ chối plugin wal2json) nên
    // chuông chỉ sống nhờ nhịp 20 giây. Trang cũng không cần tự refresh ở đây:
    // `work_roster` nằm trong LIVE_TABLES, RealtimeRefresher đã làm việc đó.
    const khiDoiCa = () => void poll();
    window.addEventListener(SU_KIEN_DOI_CA, khiDoiCa);

    return () => {
      stopped = true;
      goNhip();
      window.removeEventListener(SU_KIEN_DOI_CA, khiDoiCa);
    };
  }, [staffId]);

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

  /** ĐÓNG VIỆC — khác "đã đọc", và đây là vế lâu nay thiếu hẳn.
   *
   *  `cua_toi()` lọc `da_xu_ly_luc IS NULL`, nghĩa là một thông báo chỉ rời
   *  chuông khi có người nói "xong". Không màn nào từng gọi endpoint ấy, nên
   *  hàng đợi chỉ dài ra — và một danh sách chỉ dài ra là một danh sách người
   *  ta thôi đọc.
   *
   *  Bỏ khỏi danh sách NGAY tại chỗ: lượt poll kế tiếp còn cách 20 giây, và một
   *  cái nút bấm xong không đổi gì thì người dùng bấm lại vài lần. Nếu máy chủ
   *  từ chối, lượt poll sau trả nó về — thà hiện lại một dòng còn hơn giấu một
   *  việc chưa đóng được. */
  async function danhDauDaXuLy(thongBaoId: string) {
    setThongBao((ds) => ds.filter((t) => t.thongBaoId !== thongBaoId));
    try {
      const res = await fetch(
        `/api/thong-bao/${encodeURIComponent(thongBaoId)}/da-xu-ly`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        },
      );
      if (!res.ok) void docThongBao();
    } catch {
      void docThongBao();
    }
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
        danhDauDaXuLy,
        docLai: () => void docThongBao(),
        dismissTransient: (key) =>
          setTransient((t) => t.filter((x) => x.key !== key)),
      }}
    >
      {children}
    </Ctx.Provider>
  );
}
