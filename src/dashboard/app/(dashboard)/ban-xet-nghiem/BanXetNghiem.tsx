"use client";

// BÀN XÉT NGHIỆM ĐỐI TÁC (05/11/2026, ADR-0015). Một khách một dòng (trái), chi tiết
// các việc + thao tác ở khung phải (375: xếp dưới). Tab "Tiền thu hộ" lọc theo NGÀY
// GHI NHẬN. Trạng thái, cờ nút, lý do mờ nút — đều do máy chủ tính.

import { useCallback, useEffect, useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import ONhap from "@/components/ui/ONhap";
import ThanhTab from "@/components/ui/ThanhTab";

import { loiDocDuoc } from "@/lib/loi-doc-duoc";

import { useNgheBang } from "../dung-nghe-bang";
import { tien, type DongTien, type Viec } from "./kieu";
import ThaoTacViec from "./ThaoTacViec";

const BANG = [
  "xet_nghiem_viec",
  "doi_tac_thanh_toan",
  "doi_tac_hoan_tien",
  "mau_xet_nghiem",
  "mau_xet_nghiem_viec",
  "xet_nghiem_dong",
  "tep_ket_qua",
] as const;

async function docBan(): Promise<Viec[] | null> {
  try {
    const r = await fetch("/api/xet-nghiem/ban", { cache: "no-store" });
    return r.ok ? ((await r.json()) as { viec: Viec[] }).viec : null;
  } catch {
    return null;
  }
}

interface Khach {
  khoa: string;
  ten: string;
  ma_bn: string;
  viec: Viec[];
}

function TienThuHo() {
  const [ngay, setNgay] = useState(() => new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Ho_Chi_Minh" }));
  const [ds, setDs] = useState<{ tong: number; tien_mat: number; chuyen_khoan: number; dong: DongTien[] } | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  useEffect(() => {
    let huy = false;
    void fetch(`/api/xet-nghiem/ban/tien?ngay=${encodeURIComponent(ngay)}`, { cache: "no-store" })
      .then(async (r) => {
        const d = await r.json().catch(() => null);
        if (huy) return;
        if (!r.ok) setLoi(loiDocDuoc(d, `Chưa đọc được sổ thu hộ (HTTP ${r.status}).`));
        else {
          setLoi(null);
          setDs(d);
        }
      })
      .catch(() => {
        if (!huy) setLoi("Mất kết nối — chưa đọc được sổ thu hộ.");
      });
    return () => {
      huy = true;
    };
  }, [ngay]);
  return (
    <section aria-label="Tiền thu hộ" className="space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-meta text-ink-soft">
          Ngày ghi nhận
          <ONhap type="date" value={ngay} onChange={(e) => setNgay(e.target.value)} />
        </label>
        {ds ? (
          <p className="text-body text-ink">
            Tổng <b className="tabular-nums">{tien(ds.tong)}</b> · TM {tien(ds.tien_mat)} · CK {tien(ds.chuyen_khoan)}
          </p>
        ) : null}
      </div>
      <p className="text-meta text-ink-muted">Tiền khách trả cho đối tác — sổ riêng, không vào két hay doanh thu phòng khám.</p>
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
      <ul className="divide-y divide-line rounded-card border border-line bg-surface">
        {(ds?.dong ?? []).map((d) => (
          <li key={d.id} className="flex flex-wrap gap-x-4 gap-y-1 px-3 py-2 text-meta">
            <span className="min-w-0 flex-1 text-ink">
              {d.ten_khach} · {d.ten}
            </span>
            <span className="tabular-nums text-ink">{tien(d.so_tien)}</span>
            <span className="text-ink-muted">
              {d.loai === "HOAN" ? "Hoàn" : `TM ${tien(d.tien_mat)} · CK ${tien(d.chuyen_khoan)}`}
              {d.ma_giao_dich ? ` · ${d.ma_giao_dich}` : ""} · {d.nguoi}
            </span>
          </li>
        ))}
        {ds && ds.dong.length === 0 ? <li className="px-3 py-2 text-meta text-ink-muted">Không có khoản nào.</li> : null}
      </ul>
    </section>
  );
}

export default function BanXetNghiem() {
  const [tab, setTab] = useState<"viec" | "tien">("viec");
  const [viec, setViec] = useState<Viec[] | null>(null);
  const [chon, setChon] = useState<string | null>(null);
  const [gop, setGop] = useState<string[]>([]);
  const [bao, setBao] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [mauMoi, setMauMoi] = useState<{ ma: string; hen: string | null } | null>(null);

  const tai = useCallback(async () => {
    const d = await docBan();
    if (d) setViec(d);
  }, []);
  useEffect(() => {
    let huy = false;
    void docBan().then((d) => {
      if (!huy && d) setViec(d);
    });
    return () => {
      huy = true;
    };
  }, []);
  useNgheBang(BANG, tai);

  const khach = useMemo(() => {
    const m = new Map<string, Khach>();
    for (const v of viec ?? []) {
      const k = v.visit_id ?? v.order_id;
      const g = m.get(k) ?? { khoa: k, ten: v.ten_khach ?? "Khách", ma_bn: v.ma_bn ?? "", viec: [] };
      g.viec.push(v);
      m.set(k, g);
    }
    return [...m.values()];
  }, [viec]);
  const dang = khach.find((k) => k.khoa === chon) ?? null;
  const layDuoc = (dang?.viec ?? []).filter((v) => v.nut.lay_mau);
  const lyDoMo = (dang?.viec ?? []).find((v) => !v.nut.lay_mau && v.trang_thai.ly_do_khong_lay_mau)?.trang_thai
    .ly_do_khong_lay_mau;

  async function xong(cau: string) {
    setBao(cau);
    setLoi(null);
    await tai();
  }

  async function layMau() {
    setLoi(null);
    // Chưa tick ô nào ⇒ một ống cho các việc CÙNG đối tác với việc đầu (khác đối tác
    // phải ống khác — máy chủ cũng chặn). Đây chỉ là chọn sẵn, không phải luật.
    const dau = layDuoc[0]?.doi_tac_id;
    const ids = gop.length ? gop : layDuoc.filter((v) => v.doi_tac_id === dau).map((v) => v.order_id);
    const r = await fetch("/api/xet-nghiem/ban/lay-mau", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order_ids: ids }),
    }).catch(() => null);
    const d = (await r?.json().catch(() => null)) as { ma_mau?: string; hen_tra_ngay?: string | null; message?: string } | null;
    if (!r?.ok || !d?.ma_mau) {
      setLoi(loiDocDuoc(d, r ? `Chưa lấy mẫu được (HTTP ${r.status}).` : "Mất kết nối — chưa lấy mẫu."));
      return;
    }
    setMauMoi({ ma: d.ma_mau, hen: d.hen_tra_ngay ?? null });
    setGop([]);
    await xong(`Đã lấy mẫu — mã ống ${d.ma_mau}.`);
  }

  return (
    <section aria-label="Bàn xét nghiệm đối tác" className="space-y-4">
      <ThanhTab
        nhan="Bàn xét nghiệm"
        muc={[
          { ma: "viec", nhan: "Việc" },
          { ma: "tien", nhan: "Tiền thu hộ" },
        ]}
        chon={tab}
        onChon={setTab}
      />
      {tab === "tien" ? (
        <TienThuHo />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <ul className="divide-y divide-line overflow-hidden rounded-card border border-line bg-surface shadow-card">
            {!viec ? <li className="px-4 py-3 text-body text-ink-muted">Đang tải…</li> : null}
            {viec && khach.length === 0 ? (
              <li className="px-4 py-3 text-body text-ink-muted">
                Chưa có việc nào trong 30 ngày (dịch vụ phải được gán đối tác ở Cài đặt → Đối tác xét nghiệm).
              </li>
            ) : null}
            {khach.map((k) => (
              <li key={k.khoa}>
                <button
                  type="button"
                  onClick={() => {
                    setChon(k.khoa);
                    setGop([]);
                    setMauMoi(null);
                  }}
                  className={`flex w-full flex-wrap items-center gap-2 px-4 py-3 text-left ${chon === k.khoa ? "bg-brand-bg" : ""}`}
                >
                  <span className="min-w-0 flex-1 text-emph font-medium text-ink">
                    {k.ten} <span className="text-meta text-ink-muted">{k.ma_bn}</span>
                  </span>
                  {k.viec.map((v) => (
                    <Chip key={v.order_id} tone="neutral">
                      {v.trang_thai.nhan}
                    </Chip>
                  ))}
                </button>
              </li>
            ))}
          </ul>

          <div className="space-y-3">
            {bao ? <p className="text-meta text-success">{bao}</p> : null}
            {loi ? (
              <p role="alert" className="text-meta text-danger">
                {loi}
              </p>
            ) : null}
            {!dang ? <p className="text-body text-ink-muted">Chọn một khách ở danh sách.</p> : null}
            {dang ? (
              <>
                <p className="text-emph font-semibold text-ink">
                  {dang.ten} <span className="text-meta text-ink-muted">{dang.ma_bn}</span>
                </p>
                {mauMoi ? (
                  <div className="rounded-card border border-line bg-surface p-4 text-center shadow-card">
                    <p className="text-meta text-ink-muted">Mã ống — viết / dán lên ống</p>
                    <p className="font-mono text-title font-bold tracking-widest text-ink">{mauMoi.ma}</p>
                    {mauMoi.hen ? (
                      <p className="text-meta text-ink-muted">Hẹn trả {new Date(mauMoi.hen).toLocaleDateString("vi-VN")}</p>
                    ) : null}
                  </div>
                ) : null}
                <div className="flex flex-wrap items-center gap-2">
                  {layDuoc.length > 1
                    ? layDuoc.map((v) => (
                        <label key={v.order_id} className="flex items-center gap-1 text-meta text-ink-soft">
                          <input
                            type="checkbox"
                            checked={gop.includes(v.order_id)}
                            onChange={(e) =>
                              setGop((g) => (e.target.checked ? [...g, v.order_id] : g.filter((x) => x !== v.order_id)))
                            }
                          />
                          {v.ten_dich_vu}
                        </label>
                      ))
                    : null}
                  <span title={layDuoc.length ? undefined : (lyDoMo ?? undefined)}>
                    <Button type="button" variant="primary" disabled={!layDuoc.length} onClick={() => void layMau()}>
                      Lấy mẫu{layDuoc.length ? ` (${gop.length || layDuoc.length} việc, một ống)` : ""}
                    </Button>
                  </span>
                  {!layDuoc.length && lyDoMo ? <span className="text-meta text-ink-muted">{lyDoMo}</span> : null}
                </div>
                {dang.viec.map((v) => (
                  <ThaoTacViec key={v.order_id} v={v} onXong={(c) => void xong(c)} />
                ))}
              </>
            ) : null}
          </div>
        </div>
      )}
    </section>
  );
}
