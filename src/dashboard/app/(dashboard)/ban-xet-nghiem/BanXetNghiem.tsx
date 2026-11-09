"use client";

// BÀN XÉT NGHIỆM ĐỐI TÁC — "Việc của đối tác" (ADR-0015). HÌNH theo bản mẫu 05/11:
// đầu trang (tìm khách / mã mẫu, chọn đối tác) · tab Việc theo ngày · Còn tồn · Kết
// quả · Tiền thu hộ · Cài đặt (quản lý). "Việc theo ngày": chip ngày + chip tình trạng,
// khung trái một khách một dòng, khung phải "Hành trình xét nghiệm" 5 mốc + thẻ từng việc.
// HÀNH VI giữ nguyên máy chủ: trạng thái, màu chip, mốc nào sáng, nút nào bấm được,
// khách mang chip gì — đều do máy chủ tính; màn chỉ vẽ và lọc tại chỗ theo mã nó trả.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import ChipLoc from "@/components/ui/ChipLoc";
import MenuChon from "@/components/ui/MenuChon";
import OTimKhach from "@/components/ui/OTimKhach";
import ThanhHanhTrinh from "@/components/ui/ThanhHanhTrinh";
import ThanhNgay from "@/components/ui/ThanhNgay";
import ThanhTab from "@/components/ui/ThanhTab";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";
import { khopTimKhach } from "@/lib/tim-khach-phong";

import TheKhachHangCho from "../_lam-viec/TheKhachHangCho";
import CaiDat from "./CaiDat";
import { useNgheBang } from "../dung-nghe-bang";
import { ConTon, TienThuHo } from "./CacTab";
import KetQuaKhach from "./KetQuaKhach";
import { gioMoc, homNayVN, ngayVN, type Ban, type Khach, type Viec } from "./kieu";
import PopupKhach from "./PopupKhach";
import TheViec from "./TheViec";

const BANG = [
  "xet_nghiem_viec",
  "doi_tac_thanh_toan",
  "doi_tac_hoan_tien",
  "mau_xet_nghiem",
  "mau_xet_nghiem_viec",
  "xet_nghiem_dong",
  "tep_ket_qua",
  // Công tắc "Hiện mã ống" đổi ⇒ bàn đang mở nạp lại ngay (có / không mã).
  "xet_nghiem_cai_dat",
] as const;

type Tab = "ngay" | "ton" | "kq" | "tien" | "cd";

async function docBan(ngay: string): Promise<Ban | null> {
  try {
    // Máy chủ luôn trả 30 ngày qua + việc còn dở; `ngay` = nạp thêm đúng ngày đang xem.
    const r = await fetch(`/api/xet-nghiem/ban?ngay=${ngay}`, { cache: "no-store" });
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
  // `ma` null khi công tắc "Hiện mã ống" tắt (máy chủ không trả mã).
  const [mauMoi, setMauMoi] = useState<{ ma: string | null; hen: string | null } | null>(null);
  const [popup, setPopup] = useState<string | null>(null);
  const [moVua, setMoVua] = useState<string | null>(null);

  // Ngày đang xem: mặc định hôm nay, chọn ở thanh ngày (giống phòng dịch vụ) — có cả
  // ngày không có việc và ngày cũ hơn cửa sổ 30 ngày.
  const homNay = homNayVN();
  const ngayChon = ngay || homNay;
  // Bàn đang vẽ là của ngày nào: khác ngày đang chọn ⇒ đang tải (không chớp "trống").
  // Lượt tải của ngày cũ về muộn (tin realtime, bấm nhanh) không được đè ngày mới.
  const [banNgay, setBanNgay] = useState<string | null>(null);
  const ngayRef = useRef(ngayChon);
  useEffect(() => {
    ngayRef.current = ngayChon;
  }, [ngayChon]);
  // Ngày tải hỏng (mạng / 5xx): hiện câu lỗi + nút tải lại thay vì "Đang tải…" mãi.
  const [loiNgay, setLoiNgay] = useState<string | null>(null);
  const nhan = useCallback((n: string, d: Ban | null) => {
    if (ngayRef.current !== n) return;
    if (d) {
      setBan(d);
      setBanNgay(n);
      setLoiNgay(null);
    } else setLoiNgay(n);
  }, []);
  const tai = useCallback(async () => {
    const n = ngayRef.current;
    nhan(n, await docBan(n));
  }, [nhan]);
  useEffect(() => {
    void docBan(ngayChon).then((d) => nhan(ngayChon, d));
  }, [ngayChon, nhan]);
  const hongNgay = loiNgay === ngayChon;
  const dangTaiNgay = banNgay !== ngayChon && !hongNgay;
  useNgheBang(BANG, tai);

  const theoId = useMemo(() => new Map((ban?.viec ?? []).map((v) => [v.order_id, v])), [ban]);
  const doiTacDs = ban?.doi_tac ?? [];
  const cuaDt = (v: Viec) => !doiTac || v.doi_tac_id === doiTac;
  const viecCua = (k: Khach) => k.order_ids.map((id) => theoId.get(id)).filter((v): v is Viec => !!v && cuaDt(v));

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
  // Ô tìm (bản mẫu): MỖI KHÁCH một dòng, gộp mọi ngày — bấm ⇒ popup mọi lần XN.
  const timRa = useMemo(() => {
    if (!tim.trim()) return [];
    const m = new Map<string, { khoa: string; ten: string; ma_bn: string | null; viec: Viec[] }>();
    for (const v of (ban?.viec ?? []).filter(cuaDt)) {
      const khoa = v.clinic_patient_id ?? v.order_id;
      const g = m.get(khoa) ?? { khoa, ten: v.ten_khach ?? "Khách", ma_bn: v.ma_bn, viec: [] };
      g.viec.push(v);
      m.set(khoa, g);
    }
    return [...m.values()]
      .filter((g) => khopTimKhach(tim, { ten: g.ten, ma: [g.ma_bn, ...g.viec.map((v) => v.ma_mau)].filter(Boolean).join(" "), so: [] }))
      .slice(0, 6);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- cuaDt chỉ đọc doiTac
  }, [tim, ban, doiTac]);
  // Popup đọc thẳng từ bàn (ô tìm đã xoá chữ khi mở) — mọi việc của khách đó.
  const popupDs = popup ? (ban?.viec ?? []).filter((v) => cuaDt(v) && (v.clinic_patient_id ?? v.order_id) === popup) : [];

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
    setMoVua(v.order_id);
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
    const d = (await r?.json().catch(() => null)) as { ma_mau?: string | null; hen_tra_ngay?: string | null } | null;
    // Thành công xét theo r.ok — công tắc "Hiện mã ống" tắt thì máy chủ không trả mã.
    if (!r?.ok || !d) {
      setLoi(loiDocDuoc(d, r ? `Chưa lấy mẫu được (HTTP ${r.status}).` : "Mất kết nối — chưa lấy mẫu."));
      return;
    }
    setMauMoi({ ma: d.ma_mau ?? null, hen: d.hen_tra_ngay ?? null });
    setGop([]);
    await xong(d.ma_mau ? `Đã lấy mẫu — mã ống ${d.ma_mau}.` : "Đã lấy mẫu.");
  }

  const soTon = (ban?.viec ?? []).filter((v) => cuaDt(v) && v.trang_thai.con_ton).length;
  const tabs: { ma: Tab; nhan: string }[] = [
    { ma: "ngay", nhan: "Việc theo ngày" },
    { ma: "ton", nhan: `Còn tồn (${soTon})` },
    { ma: "kq", nhan: "Kết quả" },
    // Tiền thu hộ + Cài đặt: chỉ quản lý (bản mẫu; máy chủ cũng chặn `GET /ban/tien`).
    ...(ban?.quan_ly
      ? [
          { ma: "tien" as const, nhan: "Tiền thu hộ" },
          { ma: "cd" as const, nhan: "Cài đặt" },
        ]
      : []),
  ];

  return (
    <section aria-label="Việc của đối tác" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <h2 className="text-title font-semibold text-ink">Việc của đối tác</h2>
        {/* Ô thả xuống như bản mẫu ("Đối tác: … ▾"); danh sách do máy chủ trả. */}
        {doiTacDs.length ? (
          <MenuChon
            nhan="Đối tác"
            chon={doiTac}
            onChon={(d) => {
              setDoiTac(d);
              setChon(null);
            }}
            muc={[{ ma: "", nhan: "Mọi đối tác" }, ...doiTacDs.map((d) => ({ ma: d.id, nhan: d.ten }))]}
          />
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <div className="relative w-full sm:w-72">
          <OTimKhach value={tim} onChange={setTim} nhan={ban?.hien_ma_ong ? "Tìm tên khách, mã khách, mã mẫu" : "Tìm tên khách, mã khách"} />
          {tim.trim() ? (
            <div className="absolute inset-x-0 top-full z-20 mt-1 overflow-hidden rounded-control border border-line bg-surface shadow-card">
              {timRa.map((k) => (
                <button
                  key={k.khoa}
                  type="button"
                  onClick={() => {
                    setPopup(k.khoa);
                    setTim("");
                  }}
                  className="flex w-full items-center justify-between gap-2 border-b border-line px-3 py-2 text-left last:border-b-0 hover:bg-surface-sunken"
                >
                  <span className="min-w-0">
                    <span className="font-semibold text-ink">{k.ten}</span>{" "}
                    <span className="text-meta text-ink-muted">
                      {k.ma_bn ? `Mã KH ${k.ma_bn} · ` : ""}
                      {k.viec.length} chỉ định
                    </span>
                  </span>
                  {/* Việc đứng đầu = việc cần làm trước (máy chủ đã xếp); chip đã gộp quá hẹn. */}
                  <Chip tone={k.viec[0].trang_thai.chip_mau}>{k.viec[0].trang_thai.chip_nhan}</Chip>
                </button>
              ))}
              {!timRa.length ? <p className="px-3 py-2 text-meta text-ink-muted">Không thấy khách nào.</p> : null}
            </div>
          ) : null}
        </div>
        <ThanhTab nhan="Việc của đối tác" muc={tabs} chon={tab} onChon={setTab} />
        {tab === "ngay" ? (
          // Thanh ngày dùng chung (như phòng dịch vụ): Hôm nay · Hôm qua · Hôm kia, dải
          // ngày, "Chọn ngày…" — xem được cả ngày cũ, kể cả ngày chưa có việc.
          <ThanhNgay
            motNgay
            nhan="Xem việc theo ngày chỉ định"
            // Màn rộng (≥1536): nằm cạnh tab; hẹp hơn: xuống dòng riêng, đủ rộng cho dải ngày.
            className="min-w-0 basis-full 2xl:flex-1 2xl:basis-0"
            khoang={{ tu: ngayChon, den: ngayChon }}
            homNay={homNay}
            soNgayTruoc={9}
            soNgaySau={0}
            dangTai={dangTaiNgay}
            onChon={(k) => {
              setNgay(k?.den ?? homNay);
              setChon(null);
              setGop([]);
              setMauMoi(null);
            }}
          />
        ) : null}
      </div>

      {popup && popupDs.length ? (
        <PopupKhach
          ten={popupDs[0].ten_khach ?? "Khách"}
          maBn={popupDs[0].ma_bn}
          viec={popupDs}
          onDong={() => setPopup(null)}
          onMo={(v) => {
            setPopup(null);
            moViec(v);
          }}
        />
      ) : null}

      {tab === "ton" ? <ConTon viec={(ban?.viec ?? []).filter(cuaDt)} loc={ban?.loc ?? []} onMo={moViec} /> : null}
      {tab === "kq" ? <KetQuaKhach viec={(ban?.viec ?? []).filter(cuaDt)} onMo={moViec} onXong={(c) => void xong(c)} /> : null}
      {tab === "tien" ? <TienThuHo doiTac={doiTac} /> : null}
      {tab === "cd" ? <CaiDat /> : null}

      {tab === "ngay" ? (
        <div className="flex flex-col gap-3">
          <ChipLoc
            nhan="Tình trạng"
            chon={loc}
            onChon={setLoc}
            muc={[{ ma: "", nhan: "Tất cả" }, ...(ban?.loc ?? []).map((l) => ({ ma: l.ma, nhan: l.nhan }))]}
          />
          <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
            <div className="flex flex-col gap-1">
              {hongNgay ? (
                <div className="flex flex-wrap items-center gap-2 rounded-card border border-line bg-surface px-4 py-3 text-body text-ink-muted">
                  Không tải được việc của ngày này.
                  <Button size="sm" variant="secondary" onClick={() => void tai()}>
                    Tải lại
                  </Button>
                </div>
              ) : !ban || dangTaiNgay ? (
                <p className="px-4 py-3 text-body text-ink-muted">Đang tải…</p>
              ) : null}
              {ban && !dangTaiNgay && !hongNgay && !dsKhach.length ? (
                <p className="rounded-card border border-line bg-surface px-4 py-3 text-body text-ink-muted">
                  Không có khách nào trong ngày này{ban.viec.length ? "" : " (dịch vụ phải được gán đối tác ở Cài đặt)"}.
                </p>
              ) : null}
              <ul className="space-y-1" aria-label="Khách trong ngày">
              {dsKhach.map((k) => {
                // Đang lọc đối tác / tình trạng ⇒ chip theo việc ĐANG HIỆN đầu tiên (chip đã
                // gộp quá hẹn do máy chủ tính), khỏi mang chip của việc bị ẩn.
                const dau = doiTac || loc ? viecCua(k).find((v) => !loc || v.trang_thai.ma === loc) : undefined;
                return (
                  <TheKhachHangCho
                    key={k.khoa}
                    so={k.so_tiep_don}
                    ten={k.ten}
                    sdt={k.sdt}
                    soBooking={k.so_booking}
                    phu={[k.ma_bn, `${k.order_ids.length} chỉ định`].filter(Boolean).join(" · ")}
                    gio=""
                    xuongDong
                    dangChon={dang?.khoa === k.khoa}
                    phai={<Chip tone={dau ? dau.trang_thai.chip_mau : k.mau}>{dau ? dau.trang_thai.chip_nhan : k.nhan}</Chip>}
                    onChon={() => {
                      setChon(k.khoa);
                      setGop([]);
                      setMauMoi(null);
                      setMoVua(null);
                    }}
                  />
                );
              })}
              </ul>
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
                        <ThanhHanhTrinh
                          nhan={`Hành trình ${v.ten_dich_vu ?? ""}`}
                          moc={v.hanh_trinh.map((m) => ({ ten: m.ten, trangThai: m.trang_thai, gio: m.luc ? gioMoc(m.luc) : undefined }))}
                        />
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
                mauMoi.ma ? (
                  <div className="rounded-card border border-line bg-surface p-4 text-center shadow-card">
                    <p className="text-meta text-ink-muted">Mã ống — viết / dán lên ống</p>
                    <p className="font-mono text-title font-bold tracking-widest text-ink">{mauMoi.ma}</p>
                    {mauMoi.hen ? <p className="text-meta text-ink-muted">Hẹn trả {ngayVN(mauMoi.hen)}</p> : null}
                  </div>
                ) : (
                  <div className="rounded-card border border-line bg-surface p-4 text-center shadow-card">
                    <p className="text-body font-semibold text-ink">
                      Đã lấy mẫu{mauMoi.hen ? ` · Hẹn trả ${ngayVN(mauMoi.hen)}` : ""}
                    </p>
                  </div>
                )
              ) : null}
              {viecDang.map((v) => (
                <TheViec key={v.order_id} v={v} moVua={moVua === v.order_id} onXong={(c) => void xong(c)} onLayMau={(ids) => void layMau(ids)} />
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
