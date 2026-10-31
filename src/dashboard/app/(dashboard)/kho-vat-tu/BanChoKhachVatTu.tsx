"use client";

// Tab "Bán cho khách": đối soát vật tư đã bán. Bán tự vào đây, người kho chỉ xử lý
// dòng cần: gán / đổi nơi lấy, nhận lại hàng, nhập bù dòng quầy quên ghi. Máy chủ
// quyết trạng thái và nút nào hiện (`gan_duoc`…), màn chỉ vẽ và gửi lệnh.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import OChon from "@/components/ui/OChon";
import ONhap from "@/components/ui/ONhap";
import type { DongVatTu } from "../cashier/VatTuBangGia";
import { khoangTuanHienTai } from "./bao-cao-vat-tu";
import { guiVatTu, khoaChongGuiTrung, khoaMoi, soVatTu, tienVatTu, xoaKhoaChongGuiTrung } from "./gui-vat-tu";
import NhapBuVatTu from "./NhapBuVatTu";
import type { NoiChua } from "./TonVatTu";

export interface DongBan {
  id: string;
  nguon_ten: string;
  ban_luc: string;
  khach: string | null;
  ma_khach: string | null;
  ten: string;
  don_vi: string | null;
  so_luong: number;
  thanh_tien: number;
  gia_von: number;
  chua_thu: boolean;
  so_hoan_tien: number;
  so_tra: number;
  so_cho_xu_ly: number;
  nguoi_ban: string | null;
  bac_si: string | null;
  room_id: string | null;
  noi_lay: string | null;
  noi_lay_ten: string;
  trang_thai: string;
  trang_thai_ten: string;
  ly_do: string | null;
  gan_duoc: boolean;
  hoan_tac_duoc: boolean;
  nhan_lai_duoc: boolean;
  khong_nhan_duoc: boolean;
}

interface GoiBan {
  items: DongBan[];
  cho_gan: number;
  cho_xu_ly: number;
  bi_cat: boolean;
}

type Viec = "gan" | "nhan" | "khong" | "hoan";

const NHAN_VIEC: Record<Viec, string> = {
  gan: "Lưu nơi lấy",
  nhan: "Nhận lại hàng",
  khong: "Không nhận lại",
  hoan: "Hoàn tác nhập bù",
};

const gio = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

export default function BanChoKhachVatTu({
  noiChua,
  vatTu,
  lanLamMoi,
  onDem,
}: {
  noiChua: NoiChua[];
  vatTu: DongVatTu[];
  /** Tăng khi sổ vật tư đổi: tải lại danh sách. */
  lanLamMoi: number;
  onDem: (so: number) => void;
}) {
  const [khoang, setKhoang] = useState(khoangTuanHienTai);
  const [noi, setNoi] = useState("");
  const [trangThai, setTrangThai] = useState("");
  const [goi, setGoi] = useState<GoiBan | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [lanTai, setLanTai] = useState(0);
  const [mo, setMo] = useState<{ id: string; viec: Viec } | null>(null);
  const [noiChon, setNoiChon] = useState("");
  const [soNhan, setSoNhan] = useState("1");
  const [lyDo, setLyDo] = useState("");
  const [dangGui, setDangGui] = useState(false);
  const [loiLenh, setLoiLenh] = useState<string | null>(null);
  const [moNhapBu, setMoNhapBu] = useState(false);

  useEffect(() => {
    const dieuKhien = new AbortController();
    const q = new URLSearchParams({ tu: khoang.tu, den: khoang.den, noi, trang_thai: trangThai });
    void fetch(`/api/vat-tu-kho/ban?${q}`, { cache: "no-store", signal: dieuKhien.signal })
      .then(async (r) => {
        const d = (await r.json().catch(() => null)) as (GoiBan & { error?: string }) | null;
        if (dieuKhien.signal.aborted) return;
        if (!r.ok || !d?.items) {
          setLoi(d?.error ?? "Không đọc được danh sách bán cho khách.");
          return;
        }
        setLoi(null);
        setGoi(d);
        onDem(d.cho_gan + d.cho_xu_ly);
      })
      .catch(() => {
        if (!dieuKhien.signal.aborted) setLoi("Mất kết nối — chưa đọc được danh sách.");
      });
    return () => dieuKhien.abort();
  }, [khoang.tu, khoang.den, noi, trangThai, lanLamMoi, lanTai, onDem]);

  function moViec(d: DongBan, viec: Viec) {
    setMo({ id: d.id, viec });
    setNoiChon(d.noi_lay === "PHONG" ? (d.room_id ?? "") : "");
    setSoNhan(d.so_cho_xu_ly > 0 ? String(d.so_cho_xu_ly) : "1");
    setLyDo("");
    setLoiLenh(null);
  }

  async function lam(d: DongBan, viec: Viec) {
    setDangGui(true);
    setLoiLenh(null);
    const body: Record<string, unknown> = { ban_id: d.id, ly_do: lyDo };
    if (viec === "gan") body.room_id = noiChon || null;
    if (viec === "nhan") body.so_luong = soNhan;
    const thaoTac = {
      gan: "ban-gan-phong",
      nhan: "ban-nhan-lai",
      khong: "ban-khong-nhan-lai",
      hoan: "ban-hoan-tac",
    } as const;
    const khoa = viec === "gan" || viec === "nhan" ? khoaChongGuiTrung(body) : khoaMoi();
    const kq = await guiVatTu(thaoTac[viec], body, khoa);
    setDangGui(false);
    if (!kq.ok) {
      setLoiLenh(kq.loi);
      return;
    }
    xoaKhoaChongGuiTrung(khoa);
    setMo(null);
    setLanTai((n) => n + 1);
  }

  const ds = goi?.items ?? [];

  return (
    <section aria-label="Vật tư bán cho khách" className="space-y-3">
      <table data-excel-source className="hidden" aria-hidden="true">
        <thead>
          <tr>
            {["Ngày", "Khách", "Mã khách", "Vật tư", "Số lượng", "Đơn vị", "Tiền", "Giá vốn", "Ai bán", "Bác sĩ", "Lấy từ", "Nguồn", "Trạng thái", "Đã hoàn tiền", "Chờ người kho xử lý", "Lý do"].map((nhan) => (
              <th key={nhan}>{nhan}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ds.map((d) => (
            <tr key={d.id}>
              <td>{gio(d.ban_luc)}</td>
              <td>{d.khach ?? ""}</td>
              <td>{d.ma_khach ?? ""}</td>
              <td>{d.ten}</td>
              <td>{Number(d.so_luong)}</td>
              <td>{d.don_vi ?? ""}</td>
              <td>{Number(d.thanh_tien)}</td>
              <td>{Number(d.gia_von)}</td>
              <td>{d.nguoi_ban ?? ""}</td>
              <td>{d.bac_si ?? ""}</td>
              <td>{d.noi_lay_ten}</td>
              <td>{d.nguon_ten}</td>
              <td>{d.trang_thai_ten}</td>
              <td>{Number(d.so_hoan_tien)}</td>
              <td>{Number(d.so_cho_xu_ly)}</td>
              <td>{d.ly_do ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="flex flex-wrap items-end gap-2">
        <label className="text-meta text-ink-soft">
          <span className="mb-1 block">Từ ngày</span>
          <ONhap type="date" aria-label="Từ ngày bán" value={khoang.tu} onChange={(e) => setKhoang((k) => ({ ...k, tu: e.target.value }))} />
        </label>
        <label className="text-meta text-ink-soft">
          <span className="mb-1 block">Đến ngày</span>
          <ONhap type="date" aria-label="Đến ngày bán" value={khoang.den} onChange={(e) => setKhoang((k) => ({ ...k, den: e.target.value }))} />
        </label>
        <label className="text-meta text-ink-soft">
          <span className="mb-1 block">Lấy từ</span>
          <OChon aria-label="Lọc nơi lấy" value={noi} onChange={(e) => setNoi(e.target.value)}>
            <option value="">Tất cả nơi lấy</option>
            <option value="kho">Kho cơ sở</option>
            {noiChua.filter((n) => n.room_id).map((n) => (
              <option key={n.room_id} value={n.room_id ?? ""}>{n.ten}</option>
            ))}
          </OChon>
        </label>
        <label className="text-meta text-ink-soft">
          <span className="mb-1 block">Trạng thái</span>
          <OChon aria-label="Lọc trạng thái" value={trangThai} onChange={(e) => setTrangThai(e.target.value)}>
            <option value="">Tất cả trạng thái</option>
            <option value="CHO_GAN_PHONG">Chờ gán phòng</option>
            <option value="DA_TRU">Đã trừ kho</option>
            <option value="DA_HOAN">Đã hoàn lại kho</option>
          </OChon>
        </label>
        <Button type="button" size="sm" variant="secondary" onClick={() => setMoNhapBu((m) => !m)}>
          {moNhapBu ? "Đóng nhập bù" : "Nhập bù"}
        </Button>
      </div>

      {goi && goi.cho_gan + goi.cho_xu_ly > 0 ? (
        <p className="text-meta text-ink-muted">
          {goi.cho_gan > 0 ? `${goi.cho_gan} dòng chờ gán phòng. ` : ""}
          {goi.cho_xu_ly > 0 ? `${goi.cho_xu_ly} dòng đã hoàn tiền, chờ người kho xử lý hàng.` : ""}
        </p>
      ) : null}

      {moNhapBu ? (
        <NhapBuVatTu
          noiChua={noiChua}
          vatTu={vatTu}
          onXong={() => {
            setMoNhapBu(false);
            setLanTai((n) => n + 1);
          }}
        />
      ) : null}

      {loi ? <p role="alert" className="text-body text-danger">{loi}</p> : null}
      {goi?.bi_cat ? (
        <p role="status" className="text-meta text-ink-muted">Chỉ hiện 1.000 dòng mới nhất — thu hẹp khoảng ngày để xem đủ.</p>
      ) : null}

      {!goi && !loi ? <p role="status" className="text-body text-ink-muted">Đang đọc danh sách…</p> : null}
      {goi && ds.length === 0 ? (
        <p className="rounded-card border border-line bg-surface px-4 py-6 text-center text-body text-ink-muted">
          Chưa có vật tư bán cho khách trong khoảng ngày này.
        </p>
      ) : null}
      {ds.length > 0 ? (
        <ul className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
          {ds.map((d) => {
            const dangMo = mo?.id === d.id ? mo.viec : null;
            return (
              <li key={d.id} className="border-b border-hairline px-3 py-2 last:border-b-0">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                  <div className="min-w-0 flex-1 basis-56">
                    <p className="text-emph font-medium text-ink">
                      {d.ten} × {soVatTu(d.so_luong)} {d.don_vi ?? ""} <Chip tone="neutral">{d.trang_thai_ten}</Chip>
                    </p>
                    <p className="text-meta text-ink-muted">
                      {gio(d.ban_luc)} · {d.khach ?? "—"}{d.ma_khach ? ` (${d.ma_khach})` : ""} · {d.nguon_ten}
                    </p>
                    <p className="text-meta text-ink-muted">
                      Lấy từ {d.noi_lay_ten} · Bán: {d.nguoi_ban ?? "—"} · Bác sĩ: {d.bac_si ?? "—"} ·{" "}
                      {d.chua_thu ? "Chưa thu" : tienVatTu(d.thanh_tien)}
                      {Number(d.gia_von) > 0 ? ` · Giá vốn ${tienVatTu(d.gia_von)}` : ""}
                    </p>
                    {d.so_cho_xu_ly > 0 ? (
                      <p className="text-meta text-ink">
                        Đã hoàn tiền {soVatTu(d.so_cho_xu_ly)} {d.don_vi ?? ""}, chưa biết hàng có về không.
                      </p>
                    ) : null}
                    {d.ly_do ? <p className="text-meta text-ink-muted">Lý do: {d.ly_do}</p> : null}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {d.gan_duoc ? (
                      <Button type="button" size="sm" variant="secondary" onClick={() => moViec(d, "gan")}>
                        {d.noi_lay ? "Đổi nơi lấy" : "Gán phòng"}
                      </Button>
                    ) : null}
                    {d.nhan_lai_duoc ? (
                      <Button type="button" size="sm" variant="ghost" onClick={() => moViec(d, "nhan")}>Nhận lại hàng</Button>
                    ) : null}
                    {d.khong_nhan_duoc ? (
                      <Button type="button" size="sm" variant="ghost" onClick={() => moViec(d, "khong")}>Không nhận lại</Button>
                    ) : null}
                    {d.hoan_tac_duoc ? (
                      <Button type="button" size="sm" variant="ghost" onClick={() => moViec(d, "hoan")}>Hoàn tác</Button>
                    ) : null}
                  </div>
                </div>
                {dangMo ? (
                  <div className="mt-2 flex flex-wrap items-end gap-2 rounded-control bg-surface-muted p-2">
                    {dangMo === "gan" ? (
                      <label className="text-meta text-ink-soft">
                        <span className="mb-1 block">Lấy từ</span>
                        <OChon aria-label="Nơi lấy" value={noiChon} onChange={(e) => setNoiChon(e.target.value)}>
                          {noiChua.map((n) => (
                            <option key={n.room_id ?? "kho"} value={n.room_id ?? ""}>{n.ten}</option>
                          ))}
                        </OChon>
                      </label>
                    ) : null}
                    {dangMo === "nhan" ? (
                      <label className="text-meta text-ink-soft">
                        <span className="mb-1 block">Số nhận lại</span>
                        <ONhap aria-label="Số nhận lại" inputMode="decimal" className="w-24" value={soNhan} onChange={(e) => setSoNhan(e.target.value)} />
                      </label>
                    ) : null}
                    <label className="min-w-40 flex-1 text-meta text-ink-soft">
                      <span className="mb-1 block">Lý do</span>
                      <ONhap aria-label="Lý do" className="w-full" value={lyDo} onChange={(e) => setLyDo(e.target.value)} />
                    </label>
                    <Button type="button" size="sm" disabled={dangGui} onClick={() => void lam(d, dangMo)}>
                      {dangGui ? "Đang lưu…" : NHAN_VIEC[dangMo]}
                    </Button>
                    <Button type="button" size="sm" variant="ghost" onClick={() => setMo(null)}>Thôi</Button>
                    {loiLenh ? <p role="alert" className="w-full text-meta text-danger">{loiLenh}</p> : null}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
    </section>
  );
}
