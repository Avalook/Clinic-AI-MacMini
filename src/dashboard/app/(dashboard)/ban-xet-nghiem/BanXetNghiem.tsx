"use client";

// BÀN XÉT NGHIỆM ĐỐI TÁC — "Việc của đối tác" (ADR-0015). HÌNH theo bản mẫu 05/11:
// đầu trang (tìm khách / mã mẫu, chọn đối tác) · tab Việc theo ngày · Còn tồn · Kết
// quả · Tiền thu hộ · Cài đặt (quản lý). "Việc theo ngày": chip ngày + chip tình trạng,
// khung trái một khách một dòng, khung phải "Hành trình xét nghiệm" 5 mốc + thẻ từng việc.
// HÀNH VI giữ nguyên máy chủ: trạng thái, màu chip, mốc nào sáng, nút nào bấm được,
// khách mang chip gì — đều do máy chủ tính; màn chỉ vẽ và lọc tại chỗ theo mã nó trả.

import { useCallback, useEffect, useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import ChipLoc from "@/components/ui/ChipLoc";
import OChon from "@/components/ui/OChon";
import OTimKhach from "@/components/ui/OTimKhach";
import Stepper from "@/components/ui/Stepper";
import ThanhTab from "@/components/ui/ThanhTab";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";
import { khopTimKhach } from "@/lib/tim-khach-phong";

import DoiTacView from "../settings/doi-tac/DoiTacView";
import { useNgheBang } from "../dung-nghe-bang";
import { ConTon, KetQua, TienThuHo } from "./CacTab";
import { gioNgay, homNayVN, ngayNgan, ngayVN, type Ban, type Khach, type Viec } from "./kieu";
import TheViec from "./TheViec";

const BANG = [
  "xet_nghiem_viec",
  "doi_tac_thanh_toan",
  "doi_tac_hoan_tien",
  "mau_xet_nghiem",
  "mau_xet_nghiem_viec",
  "xet_nghiem_dong",
  "tep_ket_qua",
] as const;

type Tab = "ngay" | "ton" | "kq" | "tien" | "cd";

async function docBan(): Promise<Ban | null> {
  try {
    const r = await fetch("/api/xet-nghiem/ban", { cache: "no-store" });
    return r.ok ? ((await r.json()) as Ban) : null;
  } catch {
    return null;
  }
}

export default function BanXetNghiem() {
  const [ban, setBan] = useState<Ban | null>(null);
  const [tab, setTab] = useState<Tab>("ngay");
  const [tim, setTim] = useState("");
  const [doiTac, setDoiTac] = useState("");
  const [ngay, setNgay] = useState("");
  const [loc, setLoc] = useState("");
  const [chon, setChon] = useState<string | null>(null);
  const [gop, setGop] = useState<string[]>([]);
  const [bao, setBao] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [mauMoi, setMauMoi] = useState<{ ma: string; hen: string | null } | null>(null);

  const tai = useCallback(async () => {
    const d = await docBan();
    if (d) setBan(d);
  }, []);
  useEffect(() => {
    let huy = false;
    void docBan().then((d) => {
      if (!huy && d) setBan(d);
    });
    return () => {
      huy = true;
    };
  }, []);
  useNgheBang(BANG, tai);

  const theoId = useMemo(() => new Map((ban?.viec ?? []).map((v) => [v.order_id, v])), [ban]);
  const doiTacDs = useMemo(() => {
    const m = new Map<string, string>();
    for (const v of ban?.viec ?? []) m.set(v.doi_tac_id, v.ten_doi_tac);
    return [...m.entries()];
  }, [ban]);
  const cuaDt = (v: Viec) => !doiTac || v.doi_tac_id === doiTac;
  const viecCua = (k: Khach) => k.order_ids.map((id) => theoId.get(id)).filter((v): v is Viec => !!v && cuaDt(v));

  const ngays = useMemo(() => [...new Set((ban?.khach ?? []).map((k) => k.ngay))].sort().reverse().slice(0, 7), [ban]);
  const ngayChon = ngay && ngays.includes(ngay) ? ngay : (ngays.find((d) => d === homNayVN()) ?? ngays[0] ?? "");
  const dsKhach = (ban?.khach ?? []).filter(
    (k) => k.ngay === ngayChon && viecCua(k).some((v) => !loc || v.trang_thai.ma === loc),
  );
  const dang = dsKhach.find((k) => k.khoa === chon) ?? dsKhach[0] ?? null;
  const viecDang = dang ? viecCua(dang).filter((v) => !loc || v.trang_thai.ma === loc) : [];
  // Chung một ống chỉ trong CÙNG đối tác (máy chủ cũng chặn bằng khoá ngoại) — chia nhóm
  // để không cho tick lẫn, khỏi nhận 409. Chỉ hiện nhóm có từ hai việc lấy được.
  const nhomOng = [
    ...viecDang
      .filter((v) => v.nut.lay_mau)
      .reduce((m, v) => m.set(v.doi_tac_id, [...(m.get(v.doi_tac_id) ?? []), v]), new Map<string, Viec[]>()),
  ].filter(([, ds]) => ds.length > 1);
  const timRa = tim.trim()
    ? (ban?.khach ?? [])
        .filter((k) => viecCua(k).length && khopTimKhach(tim, { ten: k.ten, ma: [k.ma_bn, ...viecCua(k).map((v) => v.ma_mau)].filter(Boolean).join(" "), so: [] }))
        .slice(0, 6)
    : [];

  function moKhach(k: Khach) {
    setTab("ngay");
    setNgay(k.ngay);
    setLoc("");
    setChon(k.khoa);
    setGop([]);
    setMauMoi(null);
    setTim("");
  }
  const moViec = (v: Viec) => {
    const k = (ban?.khach ?? []).find((x) => x.order_ids.includes(v.order_id));
    if (k) moKhach(k);
  };

  async function xong(cau: string) {
    setBao(cau);
    setLoi(null);
    await tai();
  }

  async function layMau(ids: string[]) {
    setLoi(null);
    const r = await fetch("/api/xet-nghiem/ban/lay-mau", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ order_ids: ids }),
    }).catch(() => null);
    const d = (await r?.json().catch(() => null)) as { ma_mau?: string; hen_tra_ngay?: string | null } | null;
    if (!r?.ok || !d?.ma_mau) {
      setLoi(loiDocDuoc(d, r ? `Chưa lấy mẫu được (HTTP ${r.status}).` : "Mất kết nối — chưa lấy mẫu."));
      return;
    }
    setMauMoi({ ma: d.ma_mau, hen: d.hen_tra_ngay ?? null });
    setGop([]);
    await xong(`Đã lấy mẫu — mã ống ${d.ma_mau}.`);
  }

  const soTon = (ban?.viec ?? []).filter((v) => cuaDt(v) && v.trang_thai.con_ton).length;
  const tabs: { ma: Tab; nhan: string }[] = [
    { ma: "ngay", nhan: "Việc theo ngày" },
    { ma: "ton", nhan: `Còn tồn (${soTon})` },
    { ma: "kq", nhan: "Kết quả" },
    { ma: "tien", nhan: "Tiền thu hộ" },
    ...(ban?.quan_ly ? [{ ma: "cd" as const, nhan: "Cài đặt" }] : []),
  ];

  return (
    <section aria-label="Việc của đối tác" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <h2 className="text-title font-semibold text-ink">Việc của đối tác</h2>
        {doiTacDs.length > 1 ? (
          <OChon aria-label="Đối tác" value={doiTac} onChange={(e) => setDoiTac(e.target.value)}>
            <option value="">Mọi đối tác</option>
            {doiTacDs.map(([id, ten]) => (
              <option key={id} value={id}>
                {ten}
              </option>
            ))}
          </OChon>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <div className="relative w-full sm:w-72">
          <OTimKhach value={tim} onChange={setTim} nhan="Tìm tên khách, mã khách, mã mẫu" />
          {tim.trim() ? (
            <div className="absolute inset-x-0 top-full z-20 mt-1 overflow-hidden rounded-control border border-line bg-surface shadow-card">
              {timRa.map((k) => (
                <button
                  key={k.khoa}
                  type="button"
                  onClick={() => moKhach(k)}
                  className="flex w-full items-center justify-between gap-2 border-b border-line px-3 py-2 text-left last:border-b-0 hover:bg-surface-sunken"
                >
                  <span className="min-w-0">
                    <span className="font-semibold text-ink">{k.ten}</span>{" "}
                    <span className="text-meta text-ink-muted">
                      {k.ma_bn ? `Mã KH ${k.ma_bn} · ` : ""}
                      {ngayNgan(k.ngay)} · {k.order_ids.length} chỉ định
                    </span>
                  </span>
                  <Chip tone={k.mau}>{k.nhan}</Chip>
                </button>
              ))}
              {!timRa.length ? <p className="px-3 py-2 text-meta text-ink-muted">Không thấy khách nào.</p> : null}
            </div>
          ) : null}
        </div>
        <ThanhTab nhan="Việc của đối tác" muc={tabs} chon={tab} onChon={setTab} />
      </div>

      {tab === "ton" ? <ConTon viec={(ban?.viec ?? []).filter(cuaDt)} loc={ban?.loc ?? []} onMo={moViec} /> : null}
      {tab === "kq" ? <KetQua viec={(ban?.viec ?? []).filter(cuaDt)} onMo={moViec} /> : null}
      {tab === "tien" ? <TienThuHo /> : null}
      {tab === "cd" ? <DoiTacView /> : null}

      {tab === "ngay" ? (
        <div className="flex flex-col gap-3">
          {ngays.length ? (
            <ChipLoc
              nhan="Ngày chỉ định"
              chon={ngayChon}
              onChon={(d) => {
                setNgay(d);
                setChon(null);
              }}
              muc={ngays.map((d) => ({ ma: d, nhan: d === homNayVN() ? "Hôm nay" : ngayNgan(d) }))}
            />
          ) : null}
          <ChipLoc
            nhan="Tình trạng"
            chon={loc}
            onChon={setLoc}
            muc={[{ ma: "", nhan: "Tất cả" }, ...(ban?.loc ?? []).map((l) => ({ ma: l.ma, nhan: l.nhan }))]}
          />
          <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
            <div className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
              {!ban ? <p className="px-4 py-3 text-body text-ink-muted">Đang tải…</p> : null}
              {ban && !dsKhach.length ? (
                <p className="px-4 py-3 text-body text-ink-muted">
                  Không có khách nào trong ngày này{ban.viec.length ? "" : " (dịch vụ phải được gán đối tác ở Cài đặt)"}.
                </p>
              ) : null}
              {dsKhach.map((k) => (
                <button
                  key={k.khoa}
                  type="button"
                  aria-pressed={dang?.khoa === k.khoa}
                  onClick={() => {
                    setChon(k.khoa);
                    setGop([]);
                    setMauMoi(null);
                  }}
                  className={`flex w-full items-center justify-between gap-2 border-b border-line px-3 py-2 text-left last:border-b-0 ${dang?.khoa === k.khoa ? "bg-brand-50" : "hover:bg-surface-sunken"}`}
                >
                  <span className="min-w-0">
                    <span className="font-semibold text-ink">{k.ten}</span>{" "}
                    {k.order_ids.length > 1 ? <span className="text-meta text-ink-muted">{k.order_ids.length} xét nghiệm</span> : null}
                  </span>
                  <Chip tone={k.mau}>{k.nhan}</Chip>
                </button>
              ))}
            </div>

            <div className="flex min-w-0 flex-col gap-3">
              {bao ? <p className="text-meta text-success">{bao}</p> : null}
              {loi ? (
                <p role="alert" className="text-meta text-danger">
                  {loi}
                </p>
              ) : null}
              {dang && viecDang.length ? (
                <div className="flex flex-col gap-3 rounded-card border border-line bg-surface p-4 shadow-card">
                  <p className="font-semibold text-ink">
                    Hành trình xét nghiệm · {dang.ten} {dang.ma_bn ? <span className="text-meta font-normal text-ink-muted">{dang.ma_bn}</span> : null}
                  </p>
                  {viecDang.map((v) => (
                    <div key={v.order_id} className="flex flex-col gap-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-body">
                          <span className="font-semibold text-ink">{v.ten_dich_vu}</span>{" "}
                          <span className="text-ink-muted">· {v.ten_doi_tac}</span>
                        </p>
                        <Chip tone={v.trang_thai.chip_mau}>{v.trang_thai.chip_nhan}</Chip>
                      </div>
                      <div className="overflow-x-auto">
                        <Stepper steps={v.hanh_trinh.map((m) => ({ label: m.ten, state: m.trang_thai, detail: m.luc ? gioNgay(m.luc) : undefined }))} />
                      </div>
                    </div>
                  ))}
                  {nhomOng.map(([dt, ds]) => (
                    <div key={dt} className="flex flex-wrap items-center gap-2 border-t border-line pt-3">
                      <span className="text-meta text-ink-soft">Một ống cho nhiều xét nghiệm của {ds[0].ten_doi_tac}:</span>
                      {ds.map((v) => (
                        <label key={v.order_id} className="flex items-center gap-1 text-meta text-ink-soft">
                          <input
                            type="checkbox"
                            checked={gop.includes(v.order_id)}
                            onChange={(e) => setGop((g) => (e.target.checked ? [...g, v.order_id] : g.filter((x) => x !== v.order_id)))}
                          />
                          {v.ten_dich_vu}
                        </label>
                      ))}
                      <Button
                        type="button"
                        variant="primary"
                        disabled={ds.filter((v) => gop.includes(v.order_id)).length < 2}
                        onClick={() => void layMau(ds.filter((v) => gop.includes(v.order_id)).map((v) => v.order_id))}
                      >
                        Lấy mẫu chung một ống
                      </Button>
                    </div>
                  ))}
                </div>
              ) : null}
              {mauMoi ? (
                <div className="rounded-card border border-line bg-surface p-4 text-center shadow-card">
                  <p className="text-meta text-ink-muted">Mã ống — viết / dán lên ống</p>
                  <p className="font-mono text-title font-bold tracking-widest text-ink">{mauMoi.ma}</p>
                  {mauMoi.hen ? <p className="text-meta text-ink-muted">Hẹn trả {ngayVN(mauMoi.hen)}</p> : null}
                </div>
              ) : null}
              {viecDang.map((v) => (
                <TheViec key={v.order_id} v={v} onXong={(c) => void xong(c)} onLayMau={(ids) => void layMau(ids)} />
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
