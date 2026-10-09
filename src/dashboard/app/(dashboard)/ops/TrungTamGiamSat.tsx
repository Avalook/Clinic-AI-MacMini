"use client";

// TRUNG TÂM GIÁM SÁT — tab "Agent giám sát" ở /ops (09/10/2026).
//
// Tuyền: "cần một cái nhìn tổng quan mọi thứ… đẹp, chỉn chu" — phong cách theo
// mẫu Kravio (kravio-dashboard.vercel.app): khay xám vân chéo bọc thẻ trắng viền
// mảnh, đơn sắc xám + một màu đậm, xanh/đỏ chỉ cho tăng/giảm và trạng thái.
//
// Hai nguồn dữ liệu:
//   · thật  — /api/ops/agent?xem=tong-quan|chi-phi|tom-tat + danh sách nhận
//             định; tự làm mới 15 giây khi tab đang hiện.
//   · demo  — `?demo=1`: dữ liệu giả lập (agent-demo.ts) để xem giao diện; nút
//             bấm chỉ đổi trên màn, không gửi đi.
// Số, trạng thái, ngưỡng do máy chủ tính; màn chỉ vẽ.

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Activity,
  BrainCircuit,
  ChevronDown,
  CircleCheck,
  CircleX,
  Clock3,
  Coins,
  DoorOpen,
  EyeOff,
  Gauge,
  Hourglass,
  LayoutGrid,
  ListChecks,
  RefreshCw,
  ScanEye,
  ServerCog,
  Sparkles,
  TriangleAlert,
  UserRoundSearch,
  Users,
  Workflow,
} from "lucide-react";

import CongTac from "@/components/ui/CongTac";
import { fmtTime } from "@/lib/datetime";
import { nhipKhiHien } from "@/lib/nhip-khi-hien";

import { DEMO_AGENT, DEMO_CHI_PHI, DEMO_TOM_TAT, DEMO_TONG_QUAN } from "./agent-demo";

// ── Kiểu dữ liệu ─────────────────────────────────────────────────────────────

type Muc = "ok" | "warning" | "critical";
type DanhGia = "dung" | "sai" | "khong_ro";

interface Phong {
  id: string;
  ma: string;
  ten: string;
  tang: number | null;
  dang_lam: number;
  dang_cho: number;
  cho_lau_nhat: number;
  nguong_phut: number;
  nguong_nguoi: number;
  trang_thai: Muc;
  nhan_khach: boolean;
}
interface TongQuan {
  van_hanh: {
    dang_trong_phong_kham: number;
    dang_cho: number;
    dang_lam: number;
    cho_qua_nguong: number;
    cho_lau_nhat_phut: number;
    check_in_hom_nay: number;
    da_ve_hom_nay: number;
    check_in_hom_qua_cung_gio?: number;
    theo_gio: readonly { gio: number; so: number }[];
  };
  phong: readonly Phong[];
  he_thong: {
    su_kien_on: boolean;
    su_kien_ly_do: readonly string[];
    loi_moi: number;
    loi_24h: number;
    canh_bao: readonly { ma: string; muc: string; noi_dung: string }[];
  };
  agent: { critical: number; warning: number; vong_cuoi: string | null };
}
interface ChiPhi {
  hom_nay_usd: number;
  hom_nay_vnd: number;
  tran_ngay_usd: number;
  con_lai_hom_nay_usd: number;
  theo_model: { model: string; lan_goi: number; lan_loi: number; vao: number; ra: number; usd: number; thieu_gia: boolean }[];
  theo_ngay: { ngay: string; lan_goi: number; usd: number }[];
}
interface TomTat {
  llm_bat: boolean;
  model: string;
  gio_tu_dong: number;
  tom_tat: { noi_dung: string; model: string; tao_luc: string; tu_dong: boolean } | null;
}
interface NhanDinh {
  id: string;
  loai: string;
  ten_loai: string;
  muc: "warning" | "critical";
  noi_dung: string;
  muc_bang_chung: "quan_sat" | "suy_ra";
  so_lan: number;
  mo_luc: string;
  lan_cuoi: string;
  dong_luc: string | null;
  ly_do_dong: "HET" | "TAT" | null;
  danh_gia: DanhGia | null;
  danh_gia_ghi_chu: string | null;
}
interface ThongKe {
  loai: string;
  ten: string;
  che_do: "tat" | "shadow";
  dang_mo: number;
  tong_14_ngay: number;
  dung: number;
  sai: number;
  khong_ro: number;
  do_dung: number | null;
}
interface Agent {
  phien_ban: string;
  tat_het: boolean;
  bi_cat: boolean;
  tran: number;
  thong_ke: ThongKe[];
  nhan_dinh: NhanDinh[];
}

// ── Bảng màu & tiện ích ──────────────────────────────────────────────────────
// Đơn sắc theo mẫu: chữ gần đen / xám; xanh-đỏ-hổ phách CHỈ cho trạng thái.

const CHU = "text-[#18181b]";
const CHU_PHU = "text-[#71717a]";
const CHU_MO = "text-[#a1a1aa]";
const VIEN = "border-black/10";

const MAU: Record<Muc, { chu: string; nen: string; cham: string; thanh: string; ten: string }> = {
  ok: { chu: "text-emerald-600", nen: "bg-emerald-50", cham: "bg-emerald-500", thanh: "bg-[#27272a]", ten: "Ổn" },
  warning: { chu: "text-amber-600", nen: "bg-amber-50", cham: "bg-amber-500", thanh: "bg-amber-500", ten: "Đông" },
  critical: { chu: "text-rose-600", nen: "bg-rose-50", cham: "bg-rose-500", thanh: "bg-rose-500", ten: "Quá tải" },
};

const so = (n: number) => n.toLocaleString("vi-VN");
const usd = (n: number) => `$${n.toFixed(n < 1 ? 4 : 2)}`;
const phutGiua = (a: string, b: string) =>
  Math.max(0, Math.round((new Date(b).getTime() - new Date(a).getTime()) / 60000));

/** Khay xám vân chéo + tiêu đề, bọc thẻ trắng — khối dựng chính của màn. */
function Khay({
  tieu_de,
  icon,
  phai,
  children,
  className = "",
  trong = "p-4",
}: {
  tieu_de: string;
  icon?: ReactNode;
  phai?: ReactNode;
  children: ReactNode;
  className?: string;
  trong?: string;
}) {
  return (
    <section
      className={`rounded-2xl border ${VIEN} bg-[#f4f4f5] bg-[repeating-linear-gradient(135deg,transparent_0_7px,rgba(0,0,0,0.022)_7px_8px)] flex flex-col p-1.5 ${className}`}
    >
      <header className="flex min-h-10 items-center justify-between gap-2 px-2.5 pt-1 pb-2">
        <h3 className={`flex items-center gap-2 text-sm font-medium ${CHU}`}>
          {icon ? <span className={CHU_PHU} aria-hidden>{icon}</span> : null}
          {tieu_de}
        </h3>
        {phai}
      </header>
      <div className={`flex-1 rounded-xl border-[0.8px] ${VIEN} bg-white ${trong}`}>{children}</div>
    </section>
  );
}

function Nhan({ muc, children }: { muc: Muc | "xam" | "dam"; children: ReactNode }) {
  const cls =
    muc === "xam"
      ? "bg-[#f4f4f5] text-[#52525b]"
      : muc === "dam"
        ? "bg-[#18181b] text-white"
        : `${MAU[muc].nen} ${MAU[muc].chu}`;
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium whitespace-nowrap ${cls}`}>
      {children}
    </span>
  );
}

function VungNho({ day, xau = false }: { day: readonly number[]; xau?: boolean }) {
  if (day.length < 2) return null;
  const lon = Math.max(...day, 1);
  const diem = day.map((v, i) => [(i / (day.length - 1)) * 100, 30 - (v / lon) * 26] as const);
  const d = diem.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const mau = xau ? "text-rose-500" : "text-emerald-500";
  return (
    <svg viewBox="0 0 100 32" preserveAspectRatio="none" className={`h-11 w-28 shrink-0 ${mau}`} aria-hidden>
      <defs>
        <linearGradient id={`vn-${xau ? "x" : "t"}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="currentColor" stopOpacity="0.28" />
          <stop offset="1" stopColor="currentColor" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={`${d} L100 32 L0 32 Z`} fill={`url(#vn-${xau ? "x" : "t"})`} />
      <path d={d} fill="none" stroke="currentColor" strokeWidth={1.5} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
    </svg>
  );
}

function ChenhLech({ nay, truoc, nhan }: { nay: number; truoc: number; nhan: string }) {
  if (truoc <= 0) return <span className={`text-xs ${CHU_MO}`}>{nhan}</span>;
  const pt = ((nay - truoc) / truoc) * 100;
  const tang = pt >= 0;
  return (
    <span className="text-xs">
      <span className={`font-medium ${tang ? "text-emerald-600" : "text-rose-600"}`}>
        {tang ? "+" : ""}
        {pt.toFixed(1)}%
      </span>{" "}
      <span className={CHU_PHU}>{nhan}</span>
    </span>
  );
}

// ── Ô chỉ số (khay + thẻ trắng, số to nét mảnh, vùng xu hướng bên phải) ───────

function ChiSo({
  nhan,
  icon,
  gia_tri,
  duoi,
  muc,
  ve,
}: {
  nhan: string;
  icon: ReactNode;
  gia_tri: string;
  duoi?: ReactNode;
  muc?: Muc;
  ve?: ReactNode;
}) {
  return (
    <Khay tieu_de={nhan} phai={<span className={CHU_PHU} aria-hidden>{icon}</span>} trong="px-3.5 pt-4 pb-3.5">
      <div className="flex items-end justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {muc && muc !== "ok" ? <span className={`size-2 rounded-full ${MAU[muc].cham}`} aria-hidden /> : null}
            <span className={`text-[28px] leading-none font-normal tracking-tight tabular-nums ${CHU}`}>{gia_tri}</span>
          </div>
          <div className="mt-2.5">{duoi}</div>
        </div>
        {ve}
      </div>
    </Khay>
  );
}

// ── Biểu đồ cột dòng khách (xám dịu, cột chọn màu đậm, nhãn nổi + vạch nối) ───

function CotDongKhach({ du_lieu, gio_nay }: { du_lieu: readonly { gio: number; so: number }[]; gio_nay: number }) {
  const macDinh = du_lieu.findIndex((d) => d.gio === gio_nay);
  const [chon, setChon] = useState<number | null>(null);
  const i = chon ?? (macDinh >= 0 ? macDinh : null);
  const cao = Math.max(1, ...du_lieu.map((d) => d.so));
  const buoc = Math.max(1, Math.ceil(cao / 4));
  const tran = buoc * 4;
  const vach = [4, 3, 2, 1, 0].map((k) => k * buoc);
  const d = i !== null ? du_lieu[i] : null;
  const yChon = d ? 100 - (d.so / tran) * 100 : 0;
  return (
    <div className="relative">
      <div className="flex h-60 gap-3">
        <div className="relative flex-1">
          {/* vạch ngang mờ */}
          <div className="pointer-events-none absolute inset-x-0 top-0 bottom-7 flex flex-col justify-between" aria-hidden>
            {vach.map((v) => (
              <div key={v} className="border-t border-[#f1f1f2]" />
            ))}
          </div>
          {/* vạch gạch nối từ cột đang chọn tới trục phải */}
          {d && d.so > 0 ? (
            <div className="pointer-events-none absolute inset-x-0 top-0 bottom-7" aria-hidden>
              <div className="absolute right-0 border-t border-dashed border-[#27272a]/50" style={{ top: `${yChon}%`, left: `${((i ?? 0) + 0.5) * (100 / du_lieu.length)}%` }} />
            </div>
          ) : null}
          <div className="absolute inset-x-0 top-0 bottom-7 flex items-end gap-2" role="img" aria-label="Khách check-in theo giờ hôm nay">
            {du_lieu.map((x, k) => {
              const dang = k === i;
              return (
                <button
                  key={x.gio}
                  type="button"
                  aria-label={`${x.gio} giờ: ${x.so} khách`}
                  onMouseEnter={() => setChon(k)}
                  onFocus={() => setChon(k)}
                  onMouseLeave={() => setChon(null)}
                  onBlur={() => setChon(null)}
                  className="relative flex h-full flex-1 items-end focus:outline-none"
                >
                  <span
                    className={`w-full rounded-t-[6px] rounded-b-[2px] transition-all duration-200 ${
                      dang
                        ? "bg-gradient-to-b from-[#3f3f46] to-[#18181b]"
                        : "bg-gradient-to-b from-[#ececee] to-[#f6f6f7]"
                    }`}
                    style={{ height: `${Math.max(x.so > 0 ? 4 : 1.5, (x.so / tran) * 100)}%` }}
                  />
                  {dang ? (
                    <span className="absolute left-1/2 z-10 -translate-x-1/2 -translate-y-full rounded-md bg-[#18181b] px-2 py-1 text-xs font-medium whitespace-nowrap text-white shadow-lg" style={{ bottom: `calc(${(x.so / tran) * 100}% + 6px)` }}>
                      {x.gio}h : {x.so}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
          <div className="absolute inset-x-0 bottom-0 flex gap-2" aria-hidden>
            {du_lieu.map((x) => (
              <span key={x.gio} className={`flex-1 text-center text-xs ${x.gio === gio_nay ? `font-medium ${CHU}` : CHU_PHU}`}>
                {x.gio}h
              </span>
            ))}
          </div>
        </div>
        <div className={`flex flex-col justify-between pb-7 text-xs tabular-nums ${CHU_PHU}`} aria-hidden>
          {vach.map((v) => (
            <span key={v} className="-translate-y-1/2 first:translate-y-0 last:translate-y-0">
              {v}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Dòng trong danh sách kiểu "Latest Updates" ───────────────────────────────

function DongMoc({
  icon,
  mau,
  tieu_de,
  phu,
  gio,
  cuoi,
  children,
}: {
  icon: ReactNode;
  mau: string;
  tieu_de: ReactNode;
  phu: ReactNode;
  gio?: string;
  cuoi?: boolean;
  children?: ReactNode;
}) {
  return (
    <li className="relative flex gap-3 pb-4 last:pb-0">
      {!cuoi ? <span className="absolute top-9 bottom-0 left-[15px] border-l border-dashed border-black/15" aria-hidden /> : null}
      <span className={`relative z-[1] flex size-8 shrink-0 items-center justify-center rounded-lg border ${VIEN} bg-white shadow-[0_1px_2px_rgba(0,0,0,0.04)] ${mau}`} aria-hidden>
        {icon}
      </span>
      <div className="min-w-0 flex-1 pt-0.5">
        <div className="flex items-start justify-between gap-3">
          <div className={`text-sm font-medium ${CHU}`}>{tieu_de}</div>
          {gio ? <span className={`shrink-0 text-xs ${CHU_PHU}`}>{gio}</span> : null}
        </div>
        <div className={`mt-0.5 text-[13px] leading-relaxed ${CHU_PHU}`}>{phu}</div>
        {children}
      </div>
    </li>
  );
}

function PhanDoan<T extends string>({ gia_tri, chon, doi }: { gia_tri: readonly { ma: T; ten: string }[]; chon: T; doi: (v: T) => void }) {
  return (
    <div className="grid auto-cols-fr grid-flow-col gap-1.5">
      {gia_tri.map((v) => (
        <button
          key={v.ma}
          type="button"
          aria-pressed={chon === v.ma}
          onClick={() => doi(v.ma)}
          className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
            chon === v.ma
              ? "border-transparent bg-gradient-to-b from-[#3f3f46] to-[#18181b] text-white shadow-sm"
              : `${VIEN} bg-white ${CHU} hover:bg-[#fafafa]`
          }`}
        >
          {v.ten}
        </button>
      ))}
    </div>
  );
}

// ── Tóm tắt AI (markdown nhẹ) ────────────────────────────────────────────────

/** `**đậm**` → <strong>; còn lại để nguyên chữ (không chèn HTML lạ). */
function Dam({ chu }: { chu: string }) {
  const phan = chu.split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
  return (
    <>
      {phan.map((x, i) =>
        x.startsWith("**") && x.endsWith("**") ? (
          <strong key={i} className="font-semibold">
            {x.slice(2, -2)}
          </strong>
        ) : (
          <span key={i}>{x}</span>
        ),
      )}
    </>
  );
}

function VanBanTomTat({ chu }: { chu: string }) {
  const khoi: ReactNode[] = [];
  let ds: string[] = [];
  const dongDs = () => {
    if (!ds.length) return;
    khoi.push(
      <ul key={`u${khoi.length}`} className={`space-y-1.5 text-[13px] leading-relaxed ${CHU}`}>
        {ds.map((x, i) => (
          <li key={i} className="flex gap-2">
            <span className="mt-[7px] size-1 shrink-0 rounded-full bg-[#a1a1aa]" aria-hidden />
            <span>
              <Dam chu={x} />
            </span>
          </li>
        ))}
      </ul>,
    );
    ds = [];
  };
  for (const dong of chu.split("\n")) {
    const t = dong.trim();
    if (!t) continue;
    if (t.startsWith("## ")) {
      dongDs();
      khoi.push(
        <h4 key={`h${khoi.length}`} className={`pt-3 text-xs font-medium first:pt-0 ${CHU_PHU}`}>
          {t.slice(3).replace(/\*\*/g, "")}
        </h4>,
      );
    } else if (t.startsWith("- ")) ds.push(t.slice(2));
    else {
      dongDs();
      khoi.push(
        <p key={`p${khoi.length}`} className={`text-[13px] leading-relaxed ${CHU}`}>
          <Dam chu={t} />
        </p>,
      );
    }
  }
  dongDs();
  return <div className="space-y-1.5">{khoi}</div>;
}

// ── Màn chính ────────────────────────────────────────────────────────────────

const NHAN_DG: Record<DanhGia, string> = { dung: "Đúng", sai: "Sai", khong_ro: "Không rõ" };
const ICON_LOAI: Record<string, ReactNode> = {
  khach_cho_qua_nguong: <Hourglass className="size-4" />,
  phong_qua_tai: <DoorOpen className="size-4" />,
  khach_chua_xep_buoc: <Workflow className="size-4" />,
  khach_lang_im: <UserRoundSearch className="size-4" />,
  luot_khong_ro_co_so: <LayoutGrid className="size-4" />,
  viec_qua_han: <ListChecks className="size-4" />,
};

export default function TrungTamGiamSat({ demo = false }: { demo?: boolean }) {
  const [tq, setTq] = useState<TongQuan | null>(demo ? DEMO_TONG_QUAN : null);
  const [cp, setCp] = useState<ChiPhi | null>(demo ? DEMO_CHI_PHI : null);
  const [tt, setTt] = useState<TomTat | null>(demo ? DEMO_TOM_TAT : null);
  const [ag, setAg] = useState<Agent | null>(demo ? (DEMO_AGENT as unknown as Agent) : null);
  const [luc, setLuc] = useState<string | null>(demo ? new Date().toISOString() : null);
  const [matKetNoi, setMatKetNoi] = useState(false);
  const [dangNap, setDangNap] = useState(false);
  const [dang, setDang] = useState<string | null>(null);
  const [loc, setLoc] = useState<"mo" | "tat_ca">("mo");
  const [ghiChu, setGhiChu] = useState<Record<string, string>>({});
  const [baoLoi, setBaoLoi] = useState<string | null>(null);

  const nap = useCallback(async () => {
    if (demo) {
      setLuc(new Date().toISOString());
      return;
    }
    setDangNap(true);
    const lay = (q: string) => fetch(`/api/ops/agent${q}`, { cache: "no-store" }).catch(() => null);
    const [a, b, c, d] = await Promise.all([lay("?xem=tong-quan"), lay("?xem=chi-phi"), lay("?xem=tom-tat"), lay("")]);
    setDangNap(false);
    if (!a || !a.ok) {
      setMatKetNoi(true);
      return;
    }
    setMatKetNoi(false);
    setTq((await a.json()) as TongQuan);
    if (b?.ok) setCp((await b.json()) as ChiPhi);
    if (c?.ok) setTt((await c.json()) as TomTat);
    if (d?.ok) setAg((await d.json()) as Agent);
    setLuc(new Date().toISOString());
  }, [demo]);

  useEffect(() => {
    let huy = false;
    const chay = () => {
      if (!huy) void nap();
    };
    chay();
    const goNhip = nhipKhiHien(chay, 15000);
    return () => {
      huy = true;
      goNhip();
    };
  }, [nap]);

  const gui = async (body: Record<string, unknown>) => {
    const r = await fetch("/api/ops/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).catch(() => null);
    if (!r || !r.ok) {
      const j = r ? ((await r.json().catch(() => null)) as { message?: string } | null) : null;
      setBaoLoi(j?.message ?? "Không gửi được — thử lại.");
      return;
    }
    setBaoLoi(null);
  };

  const cham = async (n: NhanDinh, gt: DanhGia) => {
    const moi = n.danh_gia === gt ? null : gt;
    if (demo) {
      setAg((a) => (a ? { ...a, nhan_dinh: a.nhan_dinh.map((x) => (x.id === n.id ? { ...x, danh_gia: moi } : x)) } : a));
      return;
    }
    setDang(n.id);
    await gui({ hanh_dong: "danh-gia", id: n.id, danh_gia: moi, ghi_chu: ghiChu[n.id] ?? n.danh_gia_ghi_chu ?? null });
    setDang(null);
    await nap();
  };

  const doiCheDo = async (loai: string, bat: boolean) => {
    if (demo) {
      setAg((a) =>
        a
          ? loai === "*"
            ? { ...a, tat_het: !bat }
            : { ...a, thong_ke: a.thong_ke.map((t) => (t.loai === loai ? { ...t, che_do: bat ? "shadow" : "tat" } : t)) }
          : a,
      );
      return;
    }
    setDang(`che-do:${loai}`);
    await gui({ hanh_dong: "che-do", loai, che_do: bat ? "shadow" : "tat" });
    setDang(null);
    await nap();
  };

  const tomTatNgay = async () => {
    if (demo) return;
    setDang("tom-tat");
    await gui({ hanh_dong: "tom-tat" });
    setDang(null);
    await nap();
  };

  const vh = tq?.van_hanh;
  const ht = tq?.he_thong;
  const sa = tq?.agent;
  const gioNay = new Date().getHours();

  const tang = useMemo(() => {
    const nhom = new Map<string, Phong[]>();
    for (const p of tq?.phong ?? []) {
      const k = p.tang === null ? "Ngoài toà nhà" : `Tầng ${p.tang}`;
      nhom.set(k, [...(nhom.get(k) ?? []), p]);
    }
    return [...nhom.entries()].sort(([a], [b]) => (a.startsWith("Tầng") === b.startsWith("Tầng") ? a.localeCompare(b) : a.startsWith("Tầng") ? -1 : 1));
  }, [tq]);

  const phongNong = (tq?.phong ?? []).filter((p) => p.trang_thai !== "ok" && p.nhan_khach).length;
  const dsNhanDinh = (ag?.nhan_dinh ?? []).filter((n) => loc === "tat_ca" || !n.dong_luc);
  const soMo = (ag?.nhan_dinh ?? []).filter((n) => !n.dong_luc).length;
  const ptTran = cp && cp.tran_ngay_usd > 0 ? Math.min(100, (cp.hom_nay_usd / cp.tran_ngay_usd) * 100) : 0;
  const tienNgay = [...(cp?.theo_ngay ?? [])].reverse();
  const caoTien = Math.max(1e-9, ...tienNgay.map((d) => d.usd));
  const tongModel = Math.max(1e-9, ...(cp?.theo_model ?? []).map((m) => m.usd));
  const homQua = cp && cp.theo_ngay.length > 1 ? cp.theo_ngay[1].usd : 0;

  return (
    <div className="min-h-full bg-[#f8f8f8]">
      <div className="mx-auto max-w-[1400px] space-y-4 p-4 lg:p-6">
        {/* ── ĐẦU MÀN ─────────────────────────────────────────────────── */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className={`flex flex-wrap items-center gap-2 text-2xl font-medium tracking-tight ${CHU}`}>
              Trung tâm giám sát
              {demo ? <Nhan muc="warning">Dữ liệu giả lập</Nhan> : null}
            </h2>
            <p className={`mt-1 text-sm ${CHU_PHU}`}>
              Toàn cảnh phòng khám, hệ thống và AI — agent đang chạy thử ngầm, chưa báo cho ai.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`inline-flex h-9 items-center gap-2 rounded-lg border ${VIEN} bg-white px-3 text-xs ${CHU_PHU}`} aria-live="polite">
              <span className="relative flex size-2">
                {!matKetNoi ? <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-70" /> : null}
                <span className={`relative inline-flex size-2 rounded-full ${matKetNoi ? "bg-rose-500" : "bg-emerald-500"}`} />
              </span>
              {matKetNoi ? "Mất kết nối" : luc ? `Trực tiếp · ${fmtTime(luc)}` : "Đang tải…"}
            </span>
            <span className={`inline-flex h-9 items-center gap-1.5 rounded-lg border ${VIEN} bg-white px-3 text-xs font-medium ${CHU}`}>
              <Clock3 className="size-3.5" aria-hidden /> Hôm nay
            </span>
            <button
              type="button"
              onClick={() => void nap()}
              disabled={dangNap}
              aria-label="Làm mới"
              className={`inline-flex size-9 items-center justify-center rounded-lg border ${VIEN} bg-white ${CHU} hover:bg-[#fafafa] disabled:opacity-60`}
            >
              <RefreshCw className={`size-4 ${dangNap ? "animate-spin" : ""}`} aria-hidden />
            </button>
            {ag ? (
              <label className={`inline-flex h-9 items-center gap-2 rounded-lg border ${VIEN} bg-white pr-3 pl-1 text-xs font-medium ${CHU}`}>
                <CongTac bat={!ag.tat_het} nhan="Bật agent giám sát" disabled={dang === "che-do:*"} onDoi={(bat) => void doiCheDo("*", bat)} />
                Agent
              </label>
            ) : null}
          </div>
        </div>

        {baoLoi ? (
          <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
            {baoLoi}
          </p>
        ) : null}

        {/* ── CHỈ SỐ ──────────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <ChiSo
            nhan="Khách check-in hôm nay"
            icon={<Users className="size-4" />}
            gia_tri={vh ? so(vh.check_in_hom_nay) : "—"}
            duoi={vh ? <ChenhLech nay={vh.check_in_hom_nay} truoc={vh.check_in_hom_qua_cung_gio ?? 0} nhan="so với hôm qua" /> : null}
            ve={vh ? <VungNho day={vh.theo_gio.filter((d) => d.gio <= gioNay).map((d) => d.so)} /> : null}
          />
          <ChiSo
            nhan="Đang trong phòng khám"
            icon={<DoorOpen className="size-4" />}
            gia_tri={vh ? so(vh.dang_trong_phong_kham) : "—"}
            duoi={
              vh ? (
                <span className={`text-xs ${CHU_PHU}`}>
                  <span className={`font-medium ${CHU}`}>{vh.dang_lam}</span> đang làm ·{" "}
                  <span className={`font-medium ${CHU}`}>{vh.dang_cho}</span> đang chờ
                </span>
              ) : null
            }
            ve={
              vh && vh.dang_trong_phong_kham > 0 ? (
                <div className="flex h-11 w-24 items-end gap-1" aria-hidden>
                  {[vh.dang_lam, vh.dang_cho, Math.max(0, vh.dang_trong_phong_kham - vh.dang_lam - vh.dang_cho)].map((v, k) => (
                    <div
                      key={k}
                      className={`flex-1 rounded-t-[4px] ${k === 0 ? "bg-gradient-to-b from-[#3f3f46] to-[#18181b]" : k === 1 ? "bg-amber-400" : "bg-[#ececee]"}`}
                      style={{ height: `${Math.max(6, (v / vh.dang_trong_phong_kham) * 100)}%` }}
                    />
                  ))}
                </div>
              ) : null
            }
          />
          <ChiSo
            nhan="Chờ lâu nhất"
            icon={<Hourglass className="size-4" />}
            gia_tri={vh ? `${vh.cho_lau_nhat_phut} phút` : "—"}
            muc={vh && vh.cho_qua_nguong > 0 ? "warning" : "ok"}
            duoi={
              vh ? (
                vh.cho_qua_nguong > 0 ? (
                  <span className="text-xs">
                    <span className="font-medium text-amber-600">{vh.cho_qua_nguong} khách</span>{" "}
                    <span className={CHU_PHU}>đang chờ quá ngưỡng</span>
                  </span>
                ) : (
                  <span className="text-xs text-emerald-600">Không ai chờ quá ngưỡng</span>
                )
              ) : null
            }
          />
          <ChiSo
            nhan="Tiền AI hôm nay"
            icon={<Coins className="size-4" />}
            gia_tri={cp ? usd(cp.hom_nay_usd) : "—"}
            muc={ptTran >= 90 ? "critical" : ptTran >= 60 ? "warning" : "ok"}
            duoi={cp ? <ChenhLech nay={cp.hom_nay_usd} truoc={homQua} nhan="so với hôm qua" /> : null}
            ve={cp && tienNgay.length > 1 ? <VungNho day={tienNgay.map((d) => d.usd)} xau={cp.hom_nay_usd > homQua && homQua > 0} /> : null}
          />
        </div>

        {/* ── DÒNG KHÁCH + SỨC KHOẺ ───────────────────────────────────── */}
        <div className="grid gap-4 lg:grid-cols-3">
          <Khay
            tieu_de="Dòng khách theo giờ"
            icon={<Activity className="size-4" />}
            className="lg:col-span-2"
            phai={
              <span className={`inline-flex h-8 items-center gap-1.5 rounded-lg border ${VIEN} bg-white px-2.5 text-xs font-medium ${CHU}`}>
                <Clock3 className="size-3.5" aria-hidden /> Hôm nay <ChevronDown className="size-3.5" aria-hidden />
              </span>
            }
          >
            {vh ? (
              <>
                <div className="mb-4 flex items-baseline gap-3">
                  <span className={`text-[32px] leading-none font-normal tracking-tight tabular-nums ${CHU}`}>{so(vh.check_in_hom_nay)}</span>
                  <ChenhLech nay={vh.check_in_hom_nay} truoc={vh.check_in_hom_qua_cung_gio ?? 0} nhan="so với hôm qua cùng giờ" />
                  <span className={`ml-auto text-xs ${CHU_PHU}`}>
                    {so(vh.da_ve_hom_nay)} đã về · {so(vh.dang_trong_phong_kham)} còn trong phòng khám
                  </span>
                </div>
                <CotDongKhach du_lieu={vh.theo_gio} gio_nay={gioNay} />
              </>
            ) : (
              <div className="h-72 animate-pulse rounded-lg bg-[#f4f4f5]" />
            )}
          </Khay>

          <Khay tieu_de="Sức khoẻ hệ thống" icon={<ServerCog className="size-4" />} phai={<span className={`text-xs ${CHU_PHU}`}>tự kiểm mỗi phút</span>}>
            {ht && sa ? (
              <ul>
                {[
                  {
                    muc: (ht.su_kien_on ? "ok" : "critical") as Muc,
                    ten: "Đường đưa tin sự kiện",
                    phu: ht.su_kien_on ? "Tin giữa các bộ phận đi bình thường" : ht.su_kien_ly_do.join("; "),
                    icon: <Workflow className="size-4" />,
                  },
                  {
                    muc: (ht.canh_bao.length === 0 ? "ok" : ht.canh_bao.some((c) => c.muc === "critical") ? "critical" : "warning") as Muc,
                    ten: "Hạ tầng",
                    phu: ht.canh_bao.length === 0 ? "Không có cảnh báo nào" : ht.canh_bao.map((c) => c.noi_dung).slice(0, 2).join(" · "),
                    icon: <ServerCog className="size-4" />,
                  },
                  {
                    muc: (ht.loi_moi > 0 ? "warning" : "ok") as Muc,
                    ten: "Lỗi phần mềm",
                    phu: `${ht.loi_moi} kiểu lỗi mới · ${ht.loi_24h} kiểu gặp trong 24 giờ`,
                    icon: <TriangleAlert className="size-4" />,
                  },
                  {
                    muc: (sa.critical > 0 ? "critical" : sa.warning > 0 || phongNong > 0 ? "warning" : "ok") as Muc,
                    ten: "Vận hành phòng khám",
                    phu:
                      sa.critical + sa.warning > 0
                        ? `${sa.critical} nghiêm trọng, ${sa.warning} cần xem · ${phongNong} phòng đông`
                        : "Agent không thấy chuyện gì bất thường",
                    icon: <Gauge className="size-4" />,
                  },
                ].map((d, k, mang) => (
                  <DongMoc
                    key={d.ten}
                    icon={d.icon}
                    mau={d.muc === "ok" ? CHU_PHU : MAU[d.muc].chu}
                    tieu_de={
                      <span className="flex items-center gap-2">
                        {d.ten}
                        <Nhan muc={d.muc}>
                          {d.muc === "ok" ? <CircleCheck className="size-3" aria-hidden /> : d.muc === "warning" ? <TriangleAlert className="size-3" aria-hidden /> : <CircleX className="size-3" aria-hidden />}
                          {d.muc === "ok" ? "Ổn" : d.muc === "warning" ? "Cần xem" : "Cần xử lý"}
                        </Nhan>
                      </span>
                    }
                    phu={d.phu}
                    cuoi={k === mang.length - 1}
                  />
                ))}
              </ul>
            ) : (
              <div className="h-72 animate-pulse rounded-lg bg-[#f4f4f5]" />
            )}
          </Khay>
        </div>

        {/* ── BẢN ĐỒ PHÒNG ────────────────────────────────────────────── */}
        <Khay
          tieu_de="Bản đồ phòng"
          icon={<LayoutGrid className="size-4" />}
          phai={
            <div className={`hidden items-center gap-3 text-xs sm:flex ${CHU_PHU}`}>
              {(["ok", "warning", "critical"] as const).map((m) => (
                <span key={m} className="inline-flex items-center gap-1.5">
                  <span className={`size-2 rounded-full ${MAU[m].cham}`} aria-hidden />
                  {MAU[m].ten}
                </span>
              ))}
            </div>
          }
        >
          {tq ? (
            tang.length === 0 ? (
              <p className={`text-sm ${CHU_PHU}`}>Chưa có phòng nào đang mở.</p>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {tang.map(([ten, ds]) => {
                  const choTang = ds.reduce((t, p) => t + p.dang_cho, 0);
                  const nongTang = ds.some((p) => p.trang_thai === "critical")
                    ? "critical"
                    : ds.some((p) => p.trang_thai === "warning")
                      ? "warning"
                      : "ok";
                  return (
                    <div key={ten} className={`rounded-xl border ${VIEN} bg-[#fcfcfc]`}>
                      <div className={`flex items-center justify-between gap-2 border-b ${VIEN} px-3 py-2`}>
                        <span className={`text-xs font-medium ${CHU}`}>{ten}</span>
                        <span className={`inline-flex items-center gap-1.5 text-xs ${CHU_PHU}`}>
                          <span className={`size-1.5 rounded-full ${MAU[nongTang].cham}`} aria-hidden />
                          {ds.length} phòng · {choTang} chờ
                        </span>
                      </div>
                      <ul className={`divide-y divide-black/[0.06]`}>
                        {ds.map((p) => {
                          const m = MAU[p.trang_thai];
                          const tai = p.nguong_nguoi > 0 ? Math.min(100, (p.dang_cho / p.nguong_nguoi) * 100) : 0;
                          return (
                            <li key={p.id} className={`px-3 py-2.5 ${p.nhan_khach ? "" : "opacity-50"}`}>
                              <div className="flex items-center gap-2">
                                {p.nhan_khach ? (
                                  <span className={`size-2 shrink-0 rounded-full ${m.cham}`} title={m.ten} aria-label={m.ten} />
                                ) : (
                                  <EyeOff className={`size-3 shrink-0 ${CHU_MO}`} aria-label="Tạm ngưng nhận khách" />
                                )}
                                <span className={`min-w-0 flex-1 truncate text-[13px] font-medium ${CHU}`} title={p.ten}>
                                  {p.ten}
                                </span>
                                <span className={`text-lg leading-none tabular-nums ${p.trang_thai === "ok" ? CHU : m.chu}`}>{p.dang_cho}</span>
                                <span className={`text-xs ${CHU_PHU}`}>chờ</span>
                              </div>
                              <div className="mt-2 flex items-center gap-2 pl-4">
                                <div className="h-1 flex-1 overflow-hidden rounded-full bg-[#ededef]" title={`${p.dang_cho}/${p.nguong_nguoi} người chờ so với ngưỡng`}>
                                  <div className={`h-full rounded-full ${m.thanh}`} style={{ width: `${tai}%` }} />
                                </div>
                                <span className={`text-right text-xs whitespace-nowrap ${CHU_MO}`}>
                                  {!p.nhan_khach ? (
                                    "tạm ngưng"
                                  ) : (
                                    <>
                                      {p.dang_lam} làm
                                      {p.dang_cho > 0 ? (
                                        <span className={p.cho_lau_nhat > p.nguong_phut ? m.chu : ""}>
                                          {" "}· lâu nhất {p.cho_lau_nhat}′/{p.nguong_phut}′
                                        </span>
                                      ) : null}
                                    </>
                                  )}
                                </span>
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  );
                })}
              </div>
            )
          ) : (
            <div className="h-40 animate-pulse rounded-lg bg-[#f4f4f5]" />
          )}
        </Khay>

        {/* ── NHẬN ĐỊNH + AI ──────────────────────────────────────────── */}
        <div className="grid gap-4 lg:grid-cols-5">
          <Khay
            tieu_de="Nhận định của agent"
            icon={<ScanEye className="size-4" />}
            className="lg:col-span-3"
            phai={<span className={`text-xs ${CHU_PHU}`}>chấm Đúng / Sai để đo độ đúng</span>}
          >
            <PhanDoan
              gia_tri={[
                { ma: "mo", ten: `Đang mở (${soMo})` },
                { ma: "tat_ca", ten: "Tất cả hôm nay" },
              ]}
              chon={loc}
              doi={setLoc}
            />
            <p className={`mt-4 mb-4 text-sm ${CHU}`}>
              <span className="text-base font-medium">{dsNhanDinh.length}</span> <span className={CHU_PHU}>nhận định</span>
              {sa && sa.critical > 0 ? <span className="ml-2"><Nhan muc="critical">{sa.critical} nghiêm trọng</Nhan></span> : null}
            </p>
            {ag === null ? (
              <div className="h-40 animate-pulse rounded-lg bg-[#f4f4f5]" />
            ) : dsNhanDinh.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-10 text-emerald-600">
                <CircleCheck className="size-8" aria-hidden />
                <p className="text-sm font-medium">Agent chưa thấy chuyện gì cần xem</p>
              </div>
            ) : (
              <ul>
                {dsNhanDinh.map((n, k) => (
                  <DongMoc
                    key={n.id}
                    icon={ICON_LOAI[n.loai] ?? <ScanEye className="size-4" />}
                    mau={n.dong_luc ? CHU_MO : MAU[n.muc].chu}
                    gio={`${fmtTime(n.mo_luc)} · ${phutGiua(n.mo_luc, n.dong_luc ?? n.lan_cuoi)}′`}
                    cuoi={k === dsNhanDinh.length - 1}
                    tieu_de={
                      <span className="flex flex-wrap items-center gap-1.5">
                        {n.ten_loai}
                        {n.dong_luc ? (
                          <Nhan muc="xam">{n.ly_do_dong === "TAT" ? "Đã tắt" : "Đã hết"}</Nhan>
                        ) : (
                          <Nhan muc={n.muc}>{n.muc === "critical" ? "Nghiêm trọng" : "Cần xem"}</Nhan>
                        )}
                        {n.muc_bang_chung === "suy_ra" ? <Nhan muc="xam">Suy luận</Nhan> : null}
                      </span>
                    }
                    phu={n.noi_dung}
                  >
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <div className={`inline-flex overflow-hidden rounded-lg border ${VIEN}`} role="group" aria-label="Chấm nhận định">
                        {(["dung", "sai", "khong_ro"] as const).map((gt) => (
                          <button
                            key={gt}
                            type="button"
                            aria-pressed={n.danh_gia === gt}
                            disabled={dang === n.id}
                            onClick={() => void cham(n, gt)}
                            className={`border-l px-2.5 py-1 text-xs font-medium first:border-l-0 ${VIEN} transition-colors disabled:opacity-50 ${
                              n.danh_gia === gt
                                ? gt === "dung"
                                  ? "bg-emerald-600 text-white"
                                  : gt === "sai"
                                    ? "bg-rose-600 text-white"
                                    : "bg-[#52525b] text-white"
                                : `bg-white ${CHU_PHU} hover:bg-[#fafafa]`
                            }`}
                          >
                            {NHAN_DG[gt]}
                          </button>
                        ))}
                      </div>
                      <input
                        className={`h-7 min-w-0 flex-1 basis-40 rounded-lg border ${VIEN} bg-white px-2.5 text-xs ${CHU} placeholder:text-[#a1a1aa] focus:border-[#18181b] focus:outline-none`}
                        placeholder="Ghi chú khi chấm (không bắt buộc)"
                        aria-label="Ghi chú đánh giá"
                        maxLength={500}
                        value={ghiChu[n.id] ?? n.danh_gia_ghi_chu ?? ""}
                        onChange={(e) => setGhiChu((g) => ({ ...g, [n.id]: e.target.value }))}
                      />
                    </div>
                  </DongMoc>
                ))}
              </ul>
            )}
          </Khay>

          <div className="space-y-4 lg:col-span-2">
            <Khay
              tieu_de="Tóm tắt của AI"
              icon={<Sparkles className="size-4" />}
              phai={
                <button
                  type="button"
                  onClick={() => void tomTatNgay()}
                  disabled={!tt?.llm_bat || dang === "tom-tat" || demo}
                  className="inline-flex h-8 items-center gap-1.5 rounded-lg bg-gradient-to-b from-[#3f3f46] to-[#18181b] px-3 text-xs font-medium text-white shadow-sm disabled:opacity-40"
                >
                  <BrainCircuit className="size-3.5" aria-hidden />
                  {dang === "tom-tat" ? "Đang viết…" : "Tóm tắt ngay"}
                </button>
              }
            >
              {tt?.tom_tat ? (
                <>
                  <p className={`mb-3 flex flex-wrap items-center gap-1.5 text-xs ${CHU_PHU}`}>
                    <Nhan muc="xam">{tt.tom_tat.model}</Nhan>
                    {tt.tom_tat.tu_dong ? "tự tạo" : "bấm tay"} lúc {fmtTime(tt.tom_tat.tao_luc)} · chỉ đọc nhận định đã không tên khách
                  </p>
                  <div className="max-h-[420px] overflow-y-auto pr-1">
                    <VanBanTomTat chu={tt.tom_tat.noi_dung} />
                  </div>
                </>
              ) : (
                <div className={`flex flex-col items-center gap-2 py-8 text-center text-sm ${CHU_PHU}`}>
                  <Sparkles className={`size-6 ${CHU_MO}`} aria-hidden />
                  {tt?.llm_bat ? `Hôm nay chưa có bản tóm tắt — tự tạo sau ${tt.gio_tu_dong}:00.` : "AI chưa bật cho agent — cần tệp khoá trên máy chủ."}
                </div>
              )}
            </Khay>

            <Khay tieu_de="Chi phí AI · 7 ngày" icon={<Coins className="size-4" />}>
              {cp ? (
                <div className="space-y-4">
                  <div>
                    <div className="flex items-baseline justify-between gap-2">
                      <span className={`text-[28px] leading-none font-normal tracking-tight tabular-nums ${CHU}`}>{usd(cp.hom_nay_usd)}</span>
                      <span className={`text-xs ${CHU_PHU}`}>≈ {so(cp.hom_nay_vnd)} đ hôm nay</span>
                    </div>
                    <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[#f1f1f2]">
                      <div className={`h-full rounded-full ${ptTran >= 90 ? "bg-rose-500" : ptTran >= 60 ? "bg-amber-500" : "bg-[#27272a]"}`} style={{ width: `${ptTran}%` }} />
                    </div>
                    <p className={`mt-1.5 text-xs ${CHU_PHU}`}>
                      {Math.round(ptTran)}% trần ngày {usd(cp.tran_ngay_usd)} · chạm trần thì tự ngừng gọi
                    </p>
                  </div>
                  {tienNgay.length > 0 ? (
                    <div>
                      <div className="flex h-20 items-end gap-1.5">
                        {tienNgay.map((d, k) => (
                          <div key={d.ngay} className="group relative flex h-full flex-1 items-end">
                            <div
                              className={`w-full rounded-t-[5px] rounded-b-[2px] ${k === tienNgay.length - 1 ? "bg-gradient-to-b from-[#3f3f46] to-[#18181b]" : "bg-gradient-to-b from-[#e4e4e7] to-[#f4f4f5] group-hover:from-[#a1a1aa]"}`}
                              style={{ height: `${Math.max(4, (d.usd / caoTien) * 100)}%` }}
                            />
                            <span className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 hidden -translate-x-1/2 rounded-md bg-[#18181b] px-1.5 py-0.5 text-xs whitespace-nowrap text-white group-hover:block">
                              {usd(d.usd)} · {d.lan_goi} lần
                            </span>
                          </div>
                        ))}
                      </div>
                      <div className={`mt-1.5 flex gap-1.5 text-center text-xs ${CHU_PHU}`}>
                        {tienNgay.map((d) => (
                          <span key={d.ngay} className="flex-1">
                            {d.ngay.slice(8)}/{d.ngay.slice(5, 7)}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  <div className="border-t border-dashed border-black/10 pt-3">
                    {cp.theo_model.length === 0 ? (
                      <p className={`text-xs ${CHU_PHU}`}>Chưa có lần gọi nào trong 7 ngày.</p>
                    ) : (
                      <ul className="space-y-3">
                        {cp.theo_model.map((m) => (
                          <li key={m.model}>
                            <div className="flex items-center justify-between gap-2 text-xs">
                              <span className={`font-mono ${CHU}`}>{m.model}</span>
                              <span className={`font-medium tabular-nums ${CHU}`}>{m.thieu_gia ? "chưa có giá" : usd(m.usd)}</span>
                            </div>
                            <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-[#f1f1f2]">
                              <div className="h-full rounded-full bg-[#52525b]" style={{ width: `${(m.usd / tongModel) * 100}%` }} />
                            </div>
                            <p className={`mt-1 text-xs ${CHU_MO}`}>
                              {so(m.lan_goi)} lần{m.lan_loi ? ` · ${m.lan_loi} lỗi` : ""} · {so(m.vao)} token vào · {so(m.ra)} ra
                            </p>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              ) : (
                <div className="h-40 animate-pulse rounded-lg bg-[#f4f4f5]" />
              )}
            </Khay>
          </div>
        </div>

        {/* ── LUẬT GIÁM SÁT ───────────────────────────────────────────── */}
        <Khay tieu_de="Luật giám sát · độ đúng 14 ngày" icon={<ListChecks className="size-4" />} trong="p-1.5" phai={ag ? <Nhan muc="xam">{ag.phien_ban}</Nhan> : null}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-sm">
              <thead>
                <tr className={`text-left text-xs ${CHU_PHU}`}>
                  <th className="px-3 py-2.5 font-medium">Loại nhận định</th>
                  <th className="px-3 py-2.5 text-right font-medium">Đang mở</th>
                  <th className="px-3 py-2.5 text-right font-medium">14 ngày</th>
                  <th className="px-3 py-2.5 text-right font-medium">Đúng / Sai</th>
                  <th className="w-48 px-3 py-2.5 font-medium">Độ đúng</th>
                  <th className="px-3 py-2.5 text-right font-medium">Bật</th>
                </tr>
              </thead>
              <tbody>
                {(ag?.thong_ke ?? []).map((t) => (
                  <tr key={t.loai} className={`border-t ${VIEN} ${t.che_do === "tat" ? "opacity-50" : ""}`}>
                    <td className={`px-3 py-2.5 ${CHU}`}>
                      <span className="inline-flex items-center gap-2">
                        <span className={CHU_PHU} aria-hidden>{ICON_LOAI[t.loai]}</span>
                        {t.ten}
                      </span>
                    </td>
                    <td className={`px-3 py-2.5 text-right tabular-nums ${CHU}`}>{t.dang_mo}</td>
                    <td className={`px-3 py-2.5 text-right tabular-nums ${CHU_PHU}`}>{t.tong_14_ngay}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums">
                      <span className="text-emerald-600">{t.dung}</span> <span className={CHU_MO}>/</span> <span className="text-rose-600">{t.sai}</span>
                    </td>
                    <td className="px-3 py-2.5">
                      {t.do_dung === null ? (
                        <span className={`text-xs ${CHU_MO}`}>chưa chấm</span>
                      ) : (
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#f1f1f2]">
                            <div
                              className={`h-full rounded-full ${t.do_dung >= 0.8 ? "bg-emerald-500" : t.do_dung >= 0.6 ? "bg-amber-500" : "bg-rose-500"}`}
                              style={{ width: `${t.do_dung * 100}%` }}
                            />
                          </div>
                          <span className={`w-9 text-right text-xs font-medium tabular-nums ${CHU}`}>{Math.round(t.do_dung * 100)}%</span>
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      <CongTac
                        bat={t.che_do !== "tat"}
                        nhan={`Bật loại: ${t.ten}`}
                        disabled={Boolean(ag?.tat_het) || dang === `che-do:${t.loai}`}
                        onDoi={(bat) => void doiCheDo(t.loai, bat)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Khay>
      </div>
    </div>
  );
}
