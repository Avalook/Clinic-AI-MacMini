"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import ONhap from "@/components/ui/ONhap";
import type { NoiChua } from "./TonVatTu";

type Ca = "SANG" | "CHIEU" | "TOI";
type Loai = "DAU" | "CUOI" | "DOT_XUAT";
type KetQua<T> = { ok: true; data: T } | { ok: false; loi: string };

interface DongDem {
  vat_tu_id: string;
  ten: string;
  don_vi: string | null;
  dem: number | null;
  ton_may: number | null;
  lech: number | null;
}

interface Phieu {
  id: string;
  room_id: string;
  phong: string;
  ngay: string;
  ca: Ca;
  loai: Loai;
  trang_thai: "NHAP" | "CHOT";
  mot_phan: boolean;
  so_da_dem: number;
  so_dong: number;
  so_lech: number;
  dong: DongDem[];
}

type TomTat = Omit<Phieu, "dong">;

const NHAN_CA: Record<Ca, string> = {
  SANG: "Ca sáng",
  CHIEU: "Ca chiều",
  TOI: "Ca tối",
};
const NHAN_LOAI: Record<Loai, string> = {
  DAU: "Đầu ca",
  CUOI: "Cuối ca",
  DOT_XUAT: "Đột xuất",
};

function homNayVn(): string {
  return new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Ho_Chi_Minh" });
}

async function goi<T>(url: string, method: "GET" | "POST", body?: unknown): Promise<KetQua<T>> {
  try {
    const response = await fetch(url, {
      method,
      cache: "no-store",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = (await response.json().catch(() => null)) as
      | (T & { message?: string; detail?: unknown; error?: string })
      | null;
    if (response.ok && data) return { ok: true, data };
    const detail = typeof data?.detail === "string" ? data.detail : null;
    return { ok: false, loi: data?.message ?? detail ?? data?.error ?? "Máy chủ từ chối." };
  } catch {
    return { ok: false, loi: "Mất kết nối — chưa lưu." };
  }
}

function so(value: number | null): string {
  return value == null
    ? "—"
    : new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 3 }).format(value);
}

export default function KiemKeCaVatTu({ noiChua }: { noiChua: NoiChua[] }) {
  const phong = useMemo(() => noiChua.filter((n) => n.room_id), [noiChua]);
  const [roomId, setRoomId] = useState(() => phong.find((n) => n.dang_bat)?.room_id ?? "");
  const [ngay, setNgay] = useState(homNayVn);
  const [ca, setCa] = useState<Ca>("SANG");
  const [loai, setLoai] = useState<Loai>("DAU");
  const [ds, setDs] = useState<TomTat[]>([]);
  const [phieu, setPhieu] = useState<Phieu | null>(null);
  const [dem, setDem] = useState<Record<string, string>>({});
  const [loi, setLoi] = useState<string | null>(null);
  const [thongBao, setThongBao] = useState<string | null>(null);
  const [dang, setDang] = useState(false);
  const [xacNhanChot, setXacNhanChot] = useState(false);

  const taiDanhSach = useCallback(async () => {
    if (!roomId || !ngay) {
      setDs([]);
      setPhieu(null);
      return;
    }
    const query = new URLSearchParams({ ngay, room_id: roomId });
    const result = await goi<{ items: TomTat[] }>(
      `/api/vat-tu-kho/kiem-ke-ca?${query}`,
      "GET",
    );
    if (!result.ok) {
      setLoi(result.loi);
      return;
    }
    setDs(result.data.items);
  }, [ngay, roomId]);

  useEffect(() => {
    if (!roomId || !ngay) return;
    let active = true;
    const query = new URLSearchParams({ ngay, room_id: roomId });
    void goi<{ items: TomTat[] }>(`/api/vat-tu-kho/kiem-ke-ca?${query}`, "GET").then(
      (result) => {
        if (!active) return;
        if (!result.ok) setLoi(result.loi);
        else setDs(result.data.items);
      },
    );
    return () => { active = false; };
  }, [ngay, roomId]);

  async function moPhieu() {
    setDang(true);
    setLoi(null);
    setThongBao(null);
    const result = await goi<Phieu>("/api/vat-tu-kho/kiem-ke-ca-mo", "POST", {
      room_id: roomId,
      ngay,
      ca,
      loai,
    });
    setDang(false);
    if (!result.ok) {
      setLoi(result.loi);
      return;
    }
    napPhieu(result.data);
    await taiDanhSach();
  }

  function napPhieu(value: Phieu) {
    setPhieu(value);
    setDem(Object.fromEntries(value.dong.map((item) => [item.vat_tu_id, item.dem == null ? "" : String(item.dem)])));
    setXacNhanChot(false);
  }

  async function docPhieu(id: string) {
    setDang(true);
    setLoi(null);
    setThongBao(null);
    const query = new URLSearchParams({ phieu_id: id });
    const result = await goi<Phieu>(`/api/vat-tu-kho/kiem-ke-ca?${query}`, "GET");
    setDang(false);
    if (!result.ok) {
      setLoi(result.loi);
      return;
    }
    napPhieu(result.data);
  }

  async function luuDem(): Promise<Phieu | null> {
    if (!phieu) return null;
    const result = await goi<Phieu>("/api/vat-tu-kho/kiem-ke-ca-dem", "POST", {
      phieu_id: phieu.id,
      dong: phieu.dong.map((item) => ({
        vat_tu_id: item.vat_tu_id,
        dem: dem[item.vat_tu_id]?.trim() || null,
      })),
    });
    if (!result.ok) {
      setLoi(result.loi);
      return null;
    }
    napPhieu(result.data);
    setThongBao("Đã lưu số đếm nháp. Tồn kho chưa thay đổi.");
    await taiDanhSach();
    return result.data;
  }

  async function chotPhieu() {
    if (!phieu) return;
    setDang(true);
    setLoi(null);
    setThongBao(null);
    const saved = await luuDem();
    if (!saved) {
      setDang(false);
      return;
    }
    const result = await goi<Phieu>("/api/vat-tu-kho/kiem-ke-ca-chot", "POST", {
      phieu_id: saved.id,
    });
    setDang(false);
    setXacNhanChot(false);
    if (!result.ok) {
      setLoi(result.loi);
      return;
    }
    napPhieu(result.data);
    setThongBao(
      `Đã chốt ${result.data.so_da_dem} dòng${result.data.mot_phan ? " (kiểm kê một phần)" : ""}. Số tồn không tự điều chỉnh.`,
    );
    await taiDanhSach();
  }

  const phongChon = phong.find((item) => item.room_id === roomId);

  return (
    <section aria-label="Kiểm kê vật tư theo ca" className="space-y-3">
      <header className="rounded-card border border-line bg-surface p-3">
        <h2 className="text-section font-semibold text-ink">Kiểm kê đầu / cuối ca theo phòng</h2>
        <p className="mt-1 text-meta text-ink-muted">
          Nhập số thực tế tại phòng. Khi chốt, hệ thống lưu tồn sổ và báo chênh lệch; phiếu kiểm kê không tự đổi tồn.
        </p>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <label className="flex flex-col gap-1 text-meta text-ink-muted">
            <span>Phòng</span>
            <select aria-label="Phòng kiểm kê" value={roomId} onChange={(event) => { setRoomId(event.target.value); setPhieu(null); }} className="min-h-10 rounded-control border border-line-strong bg-surface px-3 text-body text-ink">
              <option value="">Chọn phòng</option>
              {phong.map((item) => <option key={item.room_id} value={item.room_id ?? ""}>{item.ten}{item.dang_bat ? "" : " (đã lưu trữ)"}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-meta text-ink-muted">
            <span>Ngày</span>
            <ONhap type="date" aria-label="Ngày kiểm kê" value={ngay} onChange={(event) => { setNgay(event.target.value); setPhieu(null); }} />
          </label>
          <label className="flex flex-col gap-1 text-meta text-ink-muted">
            <span>Ca</span>
            <select aria-label="Ca kiểm kê" value={ca} onChange={(event) => setCa(event.target.value as Ca)} className="min-h-10 rounded-control border border-line-strong bg-surface px-3 text-body text-ink">
              {Object.entries(NHAN_CA).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-meta text-ink-muted">
            <span>Loại kiểm kê</span>
            <select aria-label="Loại kiểm kê" value={loai} onChange={(event) => setLoai(event.target.value as Loai)} className="min-h-10 rounded-control border border-line-strong bg-surface px-3 text-body text-ink">
              {Object.entries(NHAN_LOAI).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </select>
          </label>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button type="button" size="sm" onClick={() => void moPhieu()} disabled={dang || !roomId || !ngay || !phongChon?.dang_bat}>Mở / tiếp tục phiếu</Button>
          {phongChon ? <span className="text-meta text-ink-muted">Đang kiểm kê: {phongChon.ten}</span> : null}
        </div>
      </header>

      {loi ? <p role="alert" className="rounded-control border border-line p-3 text-body text-danger">{loi}</p> : null}
      {thongBao ? <p role="status" className="rounded-control border border-brand/20 bg-brand-50 p-3 text-body text-brand-800">{thongBao}</p> : null}

      <section aria-label="Phiếu kiểm kê trong ngày" className="rounded-card border border-line bg-surface p-3">
        <h3 className="text-emph font-semibold text-ink">Phiếu trong ngày</h3>
        {ds.length ? (
          <ul className="mt-2 divide-y divide-line">
            {ds.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <div className="flex flex-wrap items-center gap-2 text-body text-ink">
                  <span>{NHAN_CA[item.ca]} · {NHAN_LOAI[item.loai]}</span>
                  <Chip tone={item.trang_thai === "CHOT" ? "success" : "neutral"}>{item.trang_thai === "CHOT" ? "Đã chốt" : "Bản nháp"}</Chip>
                  {item.trang_thai === "CHOT" ? <span className="text-meta text-ink-muted">{item.so_lech} dòng lệch · {item.so_da_dem}/{item.so_dong} dòng đã đếm</span> : null}
                </div>
                <Button type="button" size="sm" variant="secondary" onClick={() => void docPhieu(item.id)} disabled={dang}>Mở phiếu</Button>
              </li>
            ))}
          </ul>
        ) : <p className="mt-2 text-body text-ink-muted">Chưa có phiếu kiểm kê ở phòng và ngày đã chọn.</p>}
      </section>

      {phieu ? (
        <section aria-label="Số đếm vật tư" className="overflow-hidden rounded-card border border-line bg-surface">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line p-3">
            <div>
              <h3 className="text-emph font-semibold text-ink">{NHAN_LOAI[phieu.loai]} · {NHAN_CA[phieu.ca]} · {phieu.phong}</h3>
              <p className="text-meta text-ink-muted">{phieu.ngay.split("-").reverse().join("/")} · {phieu.trang_thai === "CHOT" ? "Đã chốt" : "Bản nháp"}</p>
            </div>
            {phieu.trang_thai === "NHAP" ? <Button type="button" size="sm" variant="secondary" onClick={() => void luuDem()} disabled={dang}>Lưu số đếm</Button> : null}
          </div>
          {phieu.dong.length ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-max text-left text-body">
                <thead className="bg-surface-sunken text-meta text-ink-muted"><tr>
                  <th className="px-3 py-2">Vật tư</th><th className="px-3 py-2">Đơn vị</th>
                  <th className="px-3 py-2 text-right">Số đếm thực tế</th>
                  {phieu.trang_thai === "CHOT" ? <><th className="px-3 py-2 text-right">Tồn sổ lúc chốt</th><th className="px-3 py-2 text-right">Lệch</th></> : null}
                </tr></thead>
                <tbody className="divide-y divide-line">
                  {phieu.dong.map((item) => <tr key={item.vat_tu_id}>
                    <td className="px-3 py-2 text-ink">{item.ten}</td><td className="px-3 py-2 text-ink-muted">{item.don_vi ?? "—"}</td>
                    <td className="px-3 py-2 text-right">
                      {phieu.trang_thai === "NHAP" ? <input aria-label={`Số đếm ${item.ten}`} inputMode="decimal" value={dem[item.vat_tu_id] ?? ""} onChange={(event) => setDem((current) => ({ ...current, [item.vat_tu_id]: event.target.value }))} className="min-h-9 w-32 rounded-control border border-line-strong bg-surface px-2 text-right tabular-nums text-ink" /> : <span className="tabular-nums text-ink">{so(item.dem)}</span>}
                    </td>
                    {phieu.trang_thai === "CHOT" ? <><td className="px-3 py-2 text-right tabular-nums text-ink">{so(item.ton_may)}</td><td className={`px-3 py-2 text-right tabular-nums ${item.lech === 0 ? "text-ink-muted" : "font-semibold text-ink"}`}>{so(item.lech)}</td></> : null}
                  </tr>)}
                </tbody>
              </table>
            </div>
          ) : <p className="p-3 text-body text-ink-muted">Phòng chưa có vật tư trong sổ tồn. Cấp vật tư từ kho cho phòng rồi mở phiếu kiểm kê.</p>}
          {phieu.trang_thai === "NHAP" && phieu.dong.length ? (
            <div className="border-t border-line p-3">
              {xacNhanChot ? <div className="flex flex-wrap items-center gap-2"><span className="text-body text-ink">Chốt số đếm? Hệ thống không tự điều chỉnh tồn.</span><Button type="button" size="sm" onClick={() => void chotPhieu()} disabled={dang}>Xác nhận chốt</Button><Button type="button" size="sm" variant="secondary" onClick={() => setXacNhanChot(false)}>Quay lại</Button></div> : <Button type="button" size="sm" onClick={() => setXacNhanChot(true)} disabled={dang}>Chốt kiểm kê</Button>}
            </div>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}
