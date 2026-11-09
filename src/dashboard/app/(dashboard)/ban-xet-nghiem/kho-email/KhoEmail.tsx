"use client";

// Kho email kết quả (tạm) — Gmail G2b. Chỉ XEM: bảng thư (mới trước), lọc ngày /
// trạng thái / tên hoặc SĐT, bấm dòng ⇒ hộp xem PDF + tiêu đề + thân thư. Chữ trạng
// thái, gợi ý khách, đèn thanh trên đều do máy chủ (`services/xet_nghiem/kho_email.py`)
// tính; màn chỉ vẽ. Mỗi lần mở PDF máy chủ ghi vết `lab.archive_viewed`.

import { useEffect, useMemo, useState } from "react";

import Chip, { type ChipTone } from "@/components/ui/Chip";
import ChipLoc from "@/components/ui/ChipLoc";
import LichKhoangNgay from "@/components/ui/LichKhoangNgay";
import Lightbox, { type TepXem } from "@/components/ui/Lightbox";
import ONhap from "@/components/ui/ONhap";
import ThanhSoTrang from "@/components/ui/ThanhSoTrang";
import type { Khoang } from "@/lib/thanh-ngay";

import { gioNgay, homNayVN } from "../kieu";

interface Thu {
  id: string;
  ten_doi_tac: string;
  ten: string;
  tieu_de: string | null;
  nhan_luc: string;
  ma_tep: string | null;
  trang_thai: string;
  nhan_trang_thai: string;
  goi_y_ten: string | null;
  goi_y_ma: string | null;
}

interface Kho {
  thu: Thu[];
  tong: number;
  trang: number;
  co: number;
  thanh_tren: { nhan: string; mau: string };
}

interface ChiTiet {
  tieu_de: string | null;
  than: string | null;
  ten: string;
  ten_doi_tac: string;
  nhan_luc: string;
}

const TONE: Record<string, ChipTone> = {
  LUU_TRU: "neutral",
  CHO_GHEP: "warning",
  DA_GHEP: "success",
  TU_CHOI: "danger",
};
const LOC = [
  { ma: "", nhan: "Mọi thư" },
  { ma: "LUU_TRU", nhan: "Lưu trữ" },
  { ma: "CHO_GHEP", nhan: "Chờ ghép tay" },
  { ma: "DA_GHEP", nhan: "Đã ghép" },
  { ma: "TU_CHOI", nhan: "Đã từ chối" },
] as const;

async function doc(url: string): Promise<{ ok: true; d: unknown } | { ok: false; loi: string }> {
  try {
    const r = await fetch(url, { cache: "no-store" });
    if (r.status === 404) return { ok: false, loi: "Bạn chưa được cấp quyền xem Kho email." };
    if (!r.ok) return { ok: false, loi: "Không tải được Kho email — thử lại." };
    return { ok: true, d: await r.json() };
  } catch {
    return { ok: false, loi: "Mất kết nối — thử lại." };
  }
}

export default function KhoEmail() {
  const [kho, setKho] = useState<Kho | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [daTai, setDaTai] = useState<string | null>(null);
  const [trangThai, setTrangThai] = useState("");
  const [khoang, setKhoang] = useState<Khoang | null>(null);
  const [goQ, setGoQ] = useState("");
  const [q, setQ] = useState("");
  const [trang, setTrang] = useState(1);
  const [xem, setXem] = useState<{ thu: Thu; chi: ChiTiet | null } | null>(null);

  useEffect(() => {
    const h = setTimeout(() => setQ(goQ.trim()), 350);
    return () => clearTimeout(h);
  }, [goQ]);

  const url = useMemo(() => {
    const p = new URLSearchParams({ trang: String(trang), co: "50" });
    if (trangThai) p.set("trang_thai", trangThai);
    if (khoang) {
      p.set("tu_ngay", khoang.tu);
      p.set("den_ngay", khoang.den);
    }
    if (q) p.set("q", q);
    return `/api/xet-nghiem/kho-email?${p}`;
  }, [trang, trangThai, khoang, q]);
  const dang = daTai !== url;

  useEffect(() => {
    let huy = false;
    void doc(url).then((r) => {
      if (huy) return;
      if (r.ok) {
        setKho(r.d as Kho);
        setLoi(null);
      } else setLoi(r.loi);
      setDaTai(url);
    });
    return () => {
      huy = true;
    };
  }, [url]);

  const mo = async (t: Thu) => {
    setXem({ thu: t, chi: null });
    const r = await doc(`/api/xet-nghiem/kho-email/${encodeURIComponent(t.id)}`);
    if (r.ok) setXem({ thu: t, chi: r.d as ChiTiet });
  };

  const soTrang = kho ? Math.max(1, Math.ceil(kho.tong / kho.co)) : 1;
  const doiLoc = (f: () => void) => {
    f();
    setTrang(1);
  };

  return (
    <>
      {xem ? (
        <Lightbox
          tieuDe={xem.thu.tieu_de || xem.thu.ten}
          phuDe={`${xem.thu.ten_doi_tac} · nhận ${gioNgay(xem.thu.nhan_luc)}`}
          tep={[
            {
              id: xem.thu.id,
              src: `/api/xet-nghiem/kho-email-pdf?id=${encodeURIComponent(xem.thu.id)}`,
              ten: xem.thu.ten,
              loai: "PDF",
              taiVe: `/api/xet-nghiem/kho-email-pdf?id=${encodeURIComponent(xem.thu.id)}`,
            } satisfies TepXem,
          ]}
          trai={
            <div className="flex flex-col gap-3 p-4 text-body text-ink">
              <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">Thư</p>
              <p className="font-semibold">{xem.chi?.tieu_de || "(không tiêu đề)"}</p>
              <p className="whitespace-pre-line text-ink-soft">
                {xem.chi ? xem.chi.than || "(thư không có chữ)" : "Đang tải…"}
              </p>
              <p className="text-label text-ink-muted">Tệp: {xem.thu.ten}</p>
            </div>
          }
          onDong={() => setXem(null)}
        />
      ) : null}

      <header className="flex flex-col gap-2">
        <h1 className="text-title font-semibold text-ink">Kho email kết quả (tạm)</h1>
        {kho ? (
          <Chip tone={TONE_DEN[kho.thanh_tren.mau] ?? "neutral"}>{kho.thanh_tren.nhan}</Chip>
        ) : null}
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <ONhap
          className="w-full sm:w-72"
          type="search"
          placeholder="Tìm tên khách (không dấu cũng được) hoặc SĐT"
          aria-label="Tìm theo tên hoặc số điện thoại"
          value={goQ}
          onChange={(e) => doiLoc(() => setGoQ(e.target.value))}
        />
        <ChipLoc nhan="Trạng thái" chon={trangThai} onChon={(v) => doiLoc(() => setTrangThai(v))} muc={LOC} />
        <LichKhoangNgay
          nhan="Ngày nhận"
          khoang={khoang}
          homNay={homNayVN()}
          onChon={(k) => doiLoc(() => setKhoang(k))}
        />
      </div>

      {loi ? <p className="text-body text-danger">{loi}</p> : null}

      <ul className="flex flex-col divide-y divide-line rounded-card border border-line bg-surface">
        {kho?.thu.map((t) => (
          <li key={t.id}>
            <button
              type="button"
              onClick={() => void mo(t)}
              className="flex w-full flex-col gap-1 p-3 text-left hover:bg-surface-sunken sm:flex-row sm:items-center sm:gap-3"
            >
              <span className="shrink-0 text-label text-ink-muted sm:w-28">{gioNgay(t.nhan_luc)}</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-body font-semibold text-ink">{t.tieu_de || t.ten}</span>
                <span className="block truncate text-label text-ink-muted">
                  {t.ten_doi_tac}
                  {t.ma_tep ? ` · mã ${t.ma_tep}` : ""}
                  {t.goi_y_ten ? ` · Có thể là: ${t.goi_y_ten}${t.goi_y_ma ? ` · ${t.goi_y_ma}` : ""}` : ""}
                </span>
              </span>
              <Chip tone={TONE[t.trang_thai] ?? "neutral"}>{t.nhan_trang_thai}</Chip>
            </button>
          </li>
        ))}
        {kho && kho.thu.length === 0 ? (
          <li className="p-4 text-body text-ink-muted">Không có thư nào khớp bộ lọc.</li>
        ) : null}
        {!kho && dang ? <li className="p-4 text-body text-ink-muted">Đang tải…</li> : null}
      </ul>

      {kho && soTrang > 1 ? (
        <ThanhSoTrang trang={trang} soTrang={soTrang} onChon={setTrang} dangTai={dang} nhan={`${kho.tong} thư`} />
      ) : null}
    </>
  );
}

const TONE_DEN: Record<string, ChipTone> = { success: "success", danger: "danger", neutral: "neutral" };
