"use client";

// TÌM NHANH ⌘K (Tuyền chốt bản "Đề xuất" khung ứng dụng, 27/09/2026 tối).
//
// Gõ tên màn để nhảy tới — kiểu command palette của Linear / Vercel. Chỉ liệt kê
// màn tài khoản này MỞ ĐƯỢC: cùng hàm lọc với thanh bên (`nhomThanhBen` +
// `hienTrenThanhBen`), không có luật quyền thứ hai. Bàn phím: ⌘K / Ctrl+K mở ·
// ↑↓ chọn · Enter đi · Esc đóng.

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { hienTrenThanhBen, type ClinicRole } from "../../lib/roles";
import { CLINICAL_HREFS } from "../../lib/feature-mode-client";
import { navLabelFor, nhomTheoCongViec, nhomThanhBen } from "./nav-items";

function bo(s: string) {
  return s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase();
}

export default function TimNhanh({
  role,
  quyen,
  featureMode,
}: {
  role: ClinicRole;
  quyen: readonly string[] | null;
  featureMode: string;
}) {
  const router = useRouter();
  const [mo, setMo] = useState(false);
  const [q, setQ] = useState("");
  const [chon, setChon] = useState(0);
  const oRef = useRef<HTMLInputElement>(null);

  const man = useMemo(() => {
    const t = nhomThanhBen(role, (r, href) => hienTrenThanhBen(r, href, quyen), featureMode, CLINICAL_HREFS, [], {}, quyen);
    return nhomTheoCongViec([...t.dau, ...t.nhom.flatMap((g) => g.muc), ...t.khac]).flatMap((g) =>
      g.muc.map((m) => ({ href: m.href, ten: navLabelFor(m, role), nhom: g.ten, Icon: m.icon })),
    );
  }, [role, quyen, featureMode]);

  const loc = useMemo(() => {
    const k = bo(q.trim());
    return k ? man.filter((m) => bo(`${m.ten} ${m.nhom}`).includes(k)) : man;
  }, [man, q]);

  useEffect(() => {
    const phim = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setMo((m) => !m);
      }
    };
    window.addEventListener("keydown", phim);
    return () => window.removeEventListener("keydown", phim);
  }, []);

  useEffect(() => {
    if (!mo) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setQ("");
    setChon(0);
    requestAnimationFrame(() => oRef.current?.focus());
  }, [mo]);

  const di = (href: string) => {
    setMo(false);
    router.push(href);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setMo(true)}
        aria-label="Tìm nhanh màn hình (Ctrl K)"
        className="hidden h-8 min-w-56 items-center gap-2 rounded-control bg-surface-sunken px-2.5 text-meta text-ink-faint transition-colors hover:text-ink-muted md:flex"
      >
        <Search size={14} aria-hidden />
        <span className="flex-1 text-left">Tìm màn hình…</span>
        <kbd className="font-sans text-label text-ink-muted">⌘K</kbd>
      </button>

      {mo ? (
        <div role="dialog" aria-modal="true" aria-label="Tìm nhanh màn hình" className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-24">
          <div aria-hidden className="absolute inset-0 bg-ink/30" onClick={() => setMo(false)} />
          <div className="relative w-full max-w-lg overflow-hidden rounded-2xl bg-surface shadow-panel ring-1 ring-line">
            <div className="flex items-center gap-2 border-b border-line px-4">
              <Search size={16} className="text-ink-faint" aria-hidden />
              <input
                ref={oRef}
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setChon(0);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Escape") setMo(false);
                  else if (e.key === "ArrowDown") {
                    e.preventDefault();
                    setChon((c) => Math.min(c + 1, loc.length - 1));
                  } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    setChon((c) => Math.max(c - 1, 0));
                  } else if (e.key === "Enter" && loc[chon]) {
                    e.preventDefault();
                    di(loc[chon].href);
                  }
                }}
                placeholder="Gõ tên màn: thu tiền, bàn khám, lịch…"
                aria-label="Tên màn hình"
                aria-controls="tim-nhanh-ds"
                className="h-12 min-w-0 flex-1 bg-transparent text-body text-ink outline-none placeholder:text-ink-faint"
              />
              <kbd className="font-sans text-label text-ink-faint">Esc</kbd>
            </div>
            <ul id="tim-nhanh-ds" role="listbox" className="max-h-80 overflow-y-auto p-1.5">
              {loc.length === 0 ? (
                <li className="px-3 py-6 text-center text-meta text-ink-faint">Không có màn nào khớp.</li>
              ) : (
                loc.map((m, i) => (
                  <li key={m.href} role="option" aria-selected={i === chon}>
                    <button
                      type="button"
                      onMouseEnter={() => setChon(i)}
                      onClick={() => di(m.href)}
                      className={`flex h-10 w-full items-center gap-3 rounded-control px-3 text-left text-body ${
                        i === chon ? "bg-brand-50 text-brand-700" : "text-ink-soft"
                      }`}
                    >
                      <m.Icon size={16} aria-hidden className="shrink-0" />
                      <span className="min-w-0 flex-1 truncate">{m.ten}</span>
                      <span className="shrink-0 text-label text-ink-faint">{m.nhom}</span>
                    </button>
                  </li>
                ))
              )}
            </ul>
          </div>
        </div>
      ) : null}
    </>
  );
}
