"use client";

/**
 * BẢNG GIÁ DỊCH VỤ & PHÒNG (Tuyền 01/10/2026) — `/cashier/dich-vu`.
 *
 * MỌI dịch vụ của phòng khám (nhóm hàng · tên · giá · bên thu · nhóm việc ·
 * PHÒNG LÀM ĐƯỢC) trên một bảng; lọc "Chưa có phòng" và gán / bỏ phòng tại chỗ.
 * Thay phần dịch vụ của `CashierView` (bảng giá thuốc vẫn dùng CashierView).
 *
 * Chỉ vẽ và gửi lệnh: phí khám hay không, cần phòng không, phòng nào làm được,
 * thiếu phòng không — máy chủ quyết (hàm Postgres `danh_muc_dich_vu`, cùng luật
 * `phong_lam_duoc` với xếp phòng). Gán phòng là đổi cấu hình phòng: máy chủ trả
 * `sua_phong_duoc` (quyền `config.clinic.manage`) và vẫn hỏi lại quyền khi ghi.
 *
 * Không có nút Xoá: dịch vụ thôi bán thì bỏ tick "Đang bán" (Tuyền: không để
 * cái gì mất hẳn — sửa sai được).
 */

import { CircleAlert, Plus, Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import ChipLoc from "@/components/ui/ChipLoc";
import NganGap from "@/components/ui/NganGap";
import PopoverNeo from "@/components/ui/PopoverNeo";

import VatTuBangGia, { type DongVatTu } from "./VatTuBangGia";

export interface PhongDv {
  id: string;
  ten: string | null;
  doi_tac: boolean;
  co_so?: string | null;
}

export interface DongDichVu {
  id: string;
  service_code: string;
  name: string;
  nhom: string | null;
  nhom_hien: string | null;
  unit_price: number | null;
  active: boolean;
  billing_owner: "CLINIC" | "EXTERNAL_PARTNER";
  billing_owner_chon_tay: boolean;
  node_code: string | null;
  ten_nhom_viec: string | null;
  ma_kiotviet: string | null;
  gia_tam: boolean;
  can_phong: boolean;
  gan_rieng: boolean;
  phong: PhongDv[];
  chua_co_phong: boolean;
}

export interface DanhMucGoi {
  dich_vu: DongDichVu[];
  /** Vật tư bán thêm ở quầy thu dịch vụ (C13) — không phòng, không phí khám. */
  vat_tu: DongVatTu[];
  phong: PhongDv[];
  nhom_hang: string[];
  sua_phong_duoc: boolean;
  so_chua_co_phong: number;
}

interface NhomViec {
  ma: string;
  ten: string;
}

type Loc = "tat_ca" | "dang_ban" | "chua_phong" | "thieu_gia" | "tam_ngung";

const O_NHAP =
  "h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink " +
  "outline-none placeholder:text-ink-faint focus:border-brand-500 lg:h-8";

function tien(v: number | null): string {
  return v === null ? "chưa có giá" : `${new Intl.NumberFormat("vi-VN").format(v)} đ`;
}

/** Bỏ dấu + thường để tìm "sieu am" ra "Siêu âm". */
function boDau(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLocaleLowerCase("vi");
}

export default function DanhMucDichVuPhong({
  banDau,
  chiChuaPhong = false,
}: {
  banDau: DanhMucGoi | null;
  /** Mở từ cảnh báo trang chủ (`?loc=chua-phong`). */
  chiChuaPhong?: boolean;
}) {
  const [goi, setGoi] = useState<DanhMucGoi | null>(banDau);
  const [nhomViec, setNhomViec] = useState<NhomViec[]>([]);
  const [loc, setLoc] = useState<Loc>(chiChuaPhong ? "chua_phong" : "tat_ca");
  const [nhomLoc, setNhomLoc] = useState("");
  const [tim, setTim] = useState("");
  const [ban, setBan] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);
  const [nhapGia, setNhapGia] = useState<Record<string, string>>({});
  const [moPhong, setMoPhong] = useState<{ dv: DongDichVu; neo: HTMLElement | null } | null>(null);

  const taiLai = useCallback(async () => {
    const r = await fetch("/api/service-price?xem=danh-muc", { cache: "no-store" }).catch(() => null);
    if (!r || !r.ok) {
      setLoi("Không tải lại được danh mục — số trên màn có thể đã cũ.");
      return;
    }
    setGoi((await r.json()) as DanhMucGoi);
  }, []);

  useEffect(() => {
    let huy = false;
    void fetch("/api/service-price?xem=phong-lam", { cache: "no-store" })
      .then((r) => (r.ok ? (r.json() as Promise<NhomViec[]>) : []))
      .then((ds) => {
        if (!huy) setNhomViec(ds);
      })
      .catch(() => undefined);
    return () => {
      huy = true;
    };
  }, []);

  async function gui(
    url: string,
    method: "POST" | "PATCH" | "PUT",
    body: unknown,
    xong?: string,
  ): Promise<boolean> {
    setBan(true);
    setLoi(null);
    setBao(null);
    try {
      const r = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const kq = (await r.json().catch(() => null)) as { error?: string; detail?: string } | null;
        setLoi(kq?.error ?? kq?.detail ?? "Không lưu được — thử lại.");
        return false;
      }
      await taiLai();
      if (xong) setBao(xong);
      return true;
    } catch {
      setLoi("Không kết nối được máy chủ — chưa lưu.");
      return false;
    } finally {
      setBan(false);
    }
  }

  const sua = (dv: DongDichVu, patch: Record<string, unknown>, xong: string) =>
    gui("/api/service-price", "PATCH", { id: dv.id, ...patch }, xong);

  const ds = useMemo(() => goi?.dich_vu ?? [], [goi]);
  const hien = useMemo(() => {
    const kim = boDau(tim.trim());
    return ds.filter((d) => {
      if (nhomLoc && (d.nhom_hien ?? "") !== nhomLoc) return false;
      if (loc === "dang_ban" && !d.active) return false;
      if (loc === "chua_phong" && !d.chua_co_phong) return false;
      if (loc === "thieu_gia" && !(d.active && d.unit_price === null)) return false;
      if (loc === "tam_ngung" && d.active) return false;
      if (!kim) return true;
      return [d.name, d.service_code, d.ma_kiotviet ?? "", d.nhom_hien ?? ""].some((x) =>
        boDau(x).includes(kim),
      );
    });
  }, [ds, tim, loc, nhomLoc]);

  // Gom theo nhóm hàng — thứ tự nhóm như máy chủ trả (thứ tự file phòng khám).
  const theoNhom = useMemo(() => {
    const thuTu = goi?.nhom_hang ?? [];
    const m = new Map<string, DongDichVu[]>();
    for (const d of hien) {
      const k = d.nhom_hien ?? "Chưa có nhóm";
      m.set(k, [...(m.get(k) ?? []), d]);
    }
    return [...m.entries()].sort(
      ([a], [b]) =>
        (thuTu.indexOf(a) < 0 ? 999 : thuTu.indexOf(a)) - (thuTu.indexOf(b) < 0 ? 999 : thuTu.indexOf(b)) ||
        a.localeCompare(b, "vi"),
    );
  }, [hien, goi]);

  if (!goi) {
    return (
      <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2.5 text-body text-danger">
        Không tải được danh mục dịch vụ. Vui lòng thử lại sau.
      </p>
    );
  }

  const dangBan = ds.filter((d) => d.active).length;
  const thieuGia = ds.filter((d) => d.active && d.unit_price === null).length;
  const tamNgung = ds.length - dangBan;

  return (
    <div className="space-y-4">
      {goi.so_chua_co_phong > 0 ? (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-card border border-warning bg-warning-bg px-4 py-3 text-body text-warning"
        >
          <CircleAlert className="size-4 shrink-0" aria-hidden />
          <span className="flex-1">
            <b>{goi.so_chua_co_phong} dịch vụ đang bán chưa có phòng làm</b> — chỉ định xong khách
            không được xếp vào phòng nào.{" "}
            {goi.sua_phong_duoc ? "Gán phòng ở cột Phòng làm." : "Báo quản lý (Cài đặt phòng khám) gán phòng."}
          </span>
          {loc !== "chua_phong" ? (
            <Button type="button" size="sm" variant="secondary" onClick={() => setLoc("chua_phong")}>
              Xem các dịch vụ này
            </Button>
          ) : null}
        </div>
      ) : (
        <p className="flex items-center gap-2 text-meta text-success">
          Mọi dịch vụ đang bán đều có phòng làm.
        </p>
      )}

      <section className="space-y-3 rounded-card border border-hairline bg-surface p-3 shadow-card sm:p-4">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
          <label className="flex h-10 min-w-0 flex-1 items-center gap-2 rounded-control border border-line bg-surface px-2.5 focus-within:border-brand-500 lg:h-8">
            <Search aria-hidden className="size-4 shrink-0 text-ink-muted" />
            <span className="sr-only">Tìm dịch vụ</span>
            <input
              type="search"
              value={tim}
              onChange={(e) => setTim(e.target.value)}
              placeholder="Tìm tên, mã, nhóm — vd “PRP”, “NIPT”, “liên cầu”"
              className="min-w-0 flex-1 bg-transparent text-body text-ink outline-none placeholder:text-ink-faint"
            />
          </label>
          <label className="lg:w-60">
            <span className="sr-only">Lọc nhóm hàng</span>
            <select value={nhomLoc} onChange={(e) => setNhomLoc(e.target.value)} className={O_NHAP}>
              <option value="">Mọi nhóm hàng</option>
              {goi.nhom_hang.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
        </div>
        <ChipLoc<Loc>
          nhan="Lọc danh mục"
          chon={loc}
          onChon={setLoc}
          muc={[
            { ma: "tat_ca", nhan: `Tất cả ${ds.length}` },
            { ma: "dang_ban", nhan: `Đang bán ${dangBan}` },
            { ma: "chua_phong", nhan: `Chưa có phòng ${goi.so_chua_co_phong}`, nhac: goi.so_chua_co_phong > 0 },
            { ma: "thieu_gia", nhan: `Thiếu giá ${thieuGia}` },
            { ma: "tam_ngung", nhan: `Tạm ngưng ${tamNgung}` },
          ]}
        />
        {loi ? (
          <p role="alert" className="text-meta text-danger">
            {loi}
          </p>
        ) : null}
        {bao ? <p className="text-meta text-success">{bao}</p> : null}
      </section>

      <section aria-label="Danh mục dịch vụ" className="overflow-hidden rounded-card border border-hairline bg-surface shadow-card">
        {/* Đầu cột — chỉ máy rộng; dưới 1024px mỗi dịch vụ là một thẻ. */}
        <div className="hidden grid-cols-[minmax(0,2.2fr)_minmax(0,1.1fr)_minmax(0,1.2fr)_minmax(0,1.3fr)_minmax(0,2fr)_auto] gap-3 border-b border-hairline bg-surface-muted px-4 py-2 text-label font-semibold uppercase tracking-wide text-ink-muted lg:grid">
          <span>Dịch vụ · nhóm hàng</span>
          <span className="text-right">Đơn giá</span>
          <span>Bên thu</span>
          <span>Nhóm việc</span>
          <span>Phòng làm</span>
          <span className="text-right">Đang bán</span>
        </div>
        {theoNhom.length === 0 ? (
          <p className="px-4 py-12 text-center text-body text-ink-muted">Không có dịch vụ phù hợp.</p>
        ) : (
          theoNhom.map(([nhom, dong]) => (
            <div key={nhom}>
              <h3 className="border-b border-hairline bg-surface-muted px-4 py-1.5 text-label font-semibold uppercase tracking-wide text-ink-muted">
                {nhom} · {dong.length}
              </h3>
              <ul>
                {dong.map((d) => (
                  <DongDv
                    key={d.id}
                    d={d}
                    goi={goi}
                    nhomViec={nhomViec}
                    ban={ban}
                    nhapGia={nhapGia[d.id]}
                    onNhapGia={(v) => setNhapGia((c) => ({ ...c, [d.id]: v }))}
                    onLuuGia={async () => {
                      const v = nhapGia[d.id];
                      if (v === undefined) return;
                      const ok = await sua(d, { unit_price: v.trim() === "" ? null : v.trim() }, `Đã lưu giá “${d.name}”.`);
                      if (ok)
                        setNhapGia((c) => Object.fromEntries(Object.entries(c).filter(([k]) => k !== d.id)));
                    }}
                    onSua={(patch, xong) => void sua(d, patch, xong)}
                    onMoPhong={(neo) => setMoPhong({ dv: d, neo })}
                  />
                ))}
              </ul>
            </div>
          ))
        )}
      </section>

      <section className="rounded-card border border-hairline bg-surface px-4 py-2 shadow-card">
        <NganGap tieuDe="+ Thêm dịch vụ mới" co="the">
        <ThemDichVu
          goi={goi}
          nhomViec={nhomViec}
          ban={ban}
          onThem={(body) => gui("/api/service-price", "POST", body, `Đã thêm “${String(body.name)}”.`)}
        />
        </NganGap>
      </section>

      <VatTuBangGia
        ds={goi.vat_tu ?? []}
        ban={ban}
        onSua={(id, patch, xong) => gui("/api/service-price", "PATCH", { id, ...patch }, xong)}
      />

      {moPhong ? (
        <GanPhong
          key={moPhong.dv.id}
          dv={ds.find((x) => x.id === moPhong.dv.id) ?? moPhong.dv}
          phong={goi.phong}
          neo={moPhong.neo}
          ban={ban}
          onDong={() => setMoPhong(null)}
          onLuu={async (ids) => {
            const ok = await gui(
              "/api/clinic-config",
              "PUT",
              { what: "service-rooms", service_code: moPhong.dv.service_code, room_ids: ids },
              ids.length > 0
                ? `“${moPhong.dv.name}” chỉ làm ở ${ids.length} phòng đã tick.`
                : `“${moPhong.dv.name}” về theo nhóm việc.`,
            );
            if (ok) setMoPhong(null);
          }}
        />
      ) : null}
    </div>
  );
}

function DongDv({
  d,
  goi,
  nhomViec,
  ban,
  nhapGia,
  onNhapGia,
  onLuuGia,
  onSua,
  onMoPhong,
}: {
  d: DongDichVu;
  goi: DanhMucGoi;
  nhomViec: NhomViec[];
  ban: boolean;
  nhapGia: string | undefined;
  onNhapGia: (v: string) => void;
  onLuuGia: () => void;
  onSua: (patch: Record<string, unknown>, xong: string) => void;
  onMoPhong: (neo: HTMLElement | null) => void;
}) {
  const doiGia = nhapGia !== undefined;
  const nhan = "text-label font-semibold uppercase tracking-wide text-ink-muted lg:hidden";
  return (
    <li
      className={`grid grid-cols-1 gap-2 border-b border-hairline px-4 py-3 last:border-b-0 sm:grid-cols-2 lg:grid-cols-[minmax(0,2.2fr)_minmax(0,1.1fr)_minmax(0,1.2fr)_minmax(0,1.3fr)_minmax(0,2fr)_auto] lg:items-center lg:gap-3 lg:py-2 ${
        d.chua_co_phong ? "bg-warning-bg/40" : ""
      } ${d.active ? "" : "opacity-60"}`}
    >
      <div className="min-w-0 sm:col-span-2 lg:col-span-1">
        <p className="text-emph font-medium text-ink">{d.name}</p>
        <p className="text-meta text-ink-faint">
          {[d.ma_kiotviet, d.service_code].filter(Boolean).join(" · ")}
        </p>
        <label className="mt-1 block">
          <span className="sr-only">Nhóm hàng của {d.name}</span>
          <select
            value={d.nhom_hien ?? ""}
            disabled={ban}
            onChange={(e) => onSua({ nhom: e.target.value }, `Đã đổi nhóm “${d.name}”.`)}
            className="h-10 max-w-full rounded-control border border-line bg-surface px-2 text-meta text-ink-muted outline-none focus:border-brand-500 lg:h-7"
          >
            <option value="">Chưa có nhóm</option>
            {goi.nhom_hang.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="lg:text-right">
        <span className={nhan}>Đơn giá</span>
        <div className="flex items-center gap-1.5 lg:justify-end">
          <input
            aria-label={`Đơn giá ${d.name}`}
            inputMode="numeric"
            value={doiGia ? nhapGia : (d.unit_price ?? "")}
            placeholder="chưa có giá"
            disabled={ban}
            onChange={(e) => onNhapGia(e.target.value)}
            className="h-10 w-28 rounded-control border border-line bg-surface px-2 text-right text-body tabular-nums text-ink outline-none placeholder:text-ink-faint focus:border-brand-500 lg:h-8"
          />
          {doiGia ? (
            <Button type="button" size="sm" variant="primary" disabled={ban} onClick={onLuuGia}>
              Lưu
            </Button>
          ) : null}
        </div>
        <div className="mt-1 flex flex-wrap gap-1 lg:justify-end">
          {d.billing_owner === "EXTERNAL_PARTNER" ? (
            <Chip tone="neutral">{`tham khảo ${tien(d.unit_price)}`}</Chip>
          ) : null}
          {d.gia_tam ? <Chip tone="warning">Giá tạm</Chip> : null}
        </div>
      </div>

      <label className="block">
        <span className={nhan}>Bên thu</span>
        <select
          aria-label={`Bên thu ${d.name}`}
          value={d.billing_owner}
          disabled={ban}
          onChange={(e) => onSua({ billing_owner: e.target.value }, `Đã đổi bên thu “${d.name}”.`)}
          className={O_NHAP}
        >
          <option value="CLINIC">Phòng khám thu</option>
          <option value="EXTERNAL_PARTNER">Thu hộ đối tác</option>
        </select>
      </label>

      <label className="block">
        <span className={nhan}>Nhóm việc</span>
        {/* Phí khám cũng chọn nhóm việc + phòng như mọi dịch vụ (C21, 02/10/2026). */}
        <select
          aria-label={`Nhóm việc ${d.name}`}
          value={d.node_code ?? ""}
          disabled={ban}
          onChange={(e) => onSua({ node_code: e.target.value }, `Đã đổi nhóm việc “${d.name}”.`)}
          className={O_NHAP}
        >
          <option value="" disabled>
            Chưa chọn nhóm việc
          </option>
          {nhomViec.map((n) => (
            <option key={n.ma} value={n.ma}>
              {n.ten}
            </option>
          ))}
        </select>
      </label>

      <div className="min-w-0 sm:col-span-2 lg:col-span-1">
        <span className={nhan}>Phòng làm</span>
        <div className="flex flex-wrap items-center gap-1">
          {d.chua_co_phong ? <Chip tone="warning">Chưa có phòng</Chip> : null}
          {d.phong.map((p) => (
            <Chip key={p.id} tone={p.doi_tac ? "info" : "neutral"}>
              {p.ten}
              {p.doi_tac ? " · đối tác" : ""}
            </Chip>
          ))}
          {!d.can_phong && d.phong.length === 0 ? (
            <span className="text-meta text-ink-muted">Đối tác làm — không cần phòng</span>
          ) : null}
          {d.gan_rieng ? <Chip tone="brand">gán riêng</Chip> : null}
          {goi.sua_phong_duoc ? (
            <Button
              type="button"
              size="sm"
              variant={d.chua_co_phong ? "soft" : "ghost"}
              disabled={ban}
              onClick={(e) => onMoPhong(e.currentTarget)}
              className="max-lg:h-10"
            >
              {d.chua_co_phong ? "Gán phòng" : "Sửa phòng"}
            </Button>
          ) : null}
        </div>
      </div>

      <label className="flex min-h-10 items-center gap-2 text-meta text-ink-soft lg:min-h-0 lg:justify-end">
        <input
          type="checkbox"
          checked={d.active}
          disabled={ban}
          onChange={() =>
            onSua(
              { active: !d.active },
              d.active ? `Đã tạm ngưng “${d.name}”.` : `Đã bán lại “${d.name}”.`,
            )
          }
          className="size-4 accent-brand-600"
        />
        <span className="lg:sr-only">{d.active ? "Đang bán" : "Tạm ngưng"}</span>
      </label>
    </li>
  );
}

function GanPhong({
  dv,
  phong,
  neo,
  ban,
  onDong,
  onLuu,
}: {
  dv: DongDichVu;
  phong: PhongDv[];
  neo: HTMLElement | null;
  ban: boolean;
  onDong: () => void;
  onLuu: (ids: string[]) => void;
}) {
  const [chon, setChon] = useState<string[]>(dv.phong.map((p) => p.id));
  const bat = (id: string, co: boolean) => setChon((c) => (co ? [...c, id] : c.filter((x) => x !== id)));
  return (
    <PopoverNeo
      neo={neo}
      onDong={onDong}
      dau={
        <>
          <p className="text-emph font-semibold text-ink">Phòng làm — {dv.name}</p>
          <p className="text-meta text-ink-muted">
            Tick phòng làm được dịch vụ này. Lưu = dịch vụ CHỈ làm ở các phòng đã tick.
            {dv.ten_nhom_viec ? ` Nhóm việc: ${dv.ten_nhom_viec}.` : " Dịch vụ chưa có nhóm việc — lấy theo phòng đầu tiên."}
          </p>
        </>
      }
      chan={
        <div className="flex flex-wrap items-center gap-2 px-4 py-3">
          <Button type="button" variant="primary" disabled={ban || chon.length === 0} onClick={() => onLuu(chon)}>
            {ban ? "Đang lưu…" : `Lưu ${chon.length} phòng`}
          </Button>
          {dv.gan_rieng ? (
            <Button type="button" variant="secondary" disabled={ban} onClick={() => onLuu([])}>
              Bỏ gán riêng — theo nhóm việc
            </Button>
          ) : null}
          <Button type="button" variant="ghost" onClick={onDong}>
            Đóng
          </Button>
        </div>
      }
    >
      <ul className="grid grid-cols-1 gap-1 px-4 py-3 sm:grid-cols-2">
        {phong.map((p) => (
          <li key={p.id}>
            <label className="flex min-h-10 items-center gap-2 text-body text-ink sm:min-h-8">
              <input
                type="checkbox"
                checked={chon.includes(p.id)}
                onChange={(e) => bat(p.id, e.target.checked)}
                className="size-4 accent-brand-600"
              />
              <span className="min-w-0 flex-1">
                {p.ten}
                {p.doi_tac ? <span className="text-meta text-ink-muted"> · đối tác</span> : null}
                {p.co_so ? <span className="block text-meta text-ink-faint">{p.co_so}</span> : null}
              </span>
            </label>
          </li>
        ))}
      </ul>
    </PopoverNeo>
  );
}

function ThemDichVu({
  goi,
  nhomViec,
  ban,
  onThem,
}: {
  goi: DanhMucGoi;
  nhomViec: NhomViec[];
  ban: boolean;
  onThem: (body: Record<string, unknown>) => Promise<boolean>;
}) {
  const [ten, setTen] = useState("");
  const [nhom, setNhom] = useState("");
  const [maKv, setMaKv] = useState("");
  const [gia, setGia] = useState("");
  const [node, setNode] = useState("");
  const [benThu, setBenThu] = useState<"" | "CLINIC" | "EXTERNAL_PARTNER">("");

  const them = async () => {
    const ok = await onThem({
      name: ten.trim(),
      group: "dich_vu",
      // Không mã phòng khám → máy chủ tự sinh mã nội bộ từ tên.
      service_code: "",
      ma_kiotviet: maKv.trim(),
      unit_price: gia.trim() === "" ? null : gia.trim(),
      node_code: node || null,
      ...(benThu ? { billing_owner: benThu } : {}),
      ...(nhom ? { nhom } : {}),
    });
    if (ok) {
      setTen("");
      setMaKv("");
      setGia("");
      setNode("");
      setBenThu("");
    }
  };

  return (
    <div className="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
      <label className="block sm:col-span-2 lg:col-span-1">
        <span className="mb-1 block text-meta font-medium text-ink-soft">Tên dịch vụ</span>
        <input className={O_NHAP} value={ten} onChange={(e) => setTen(e.target.value)} maxLength={200} />
      </label>
      <label className="block">
        <span className="mb-1 block text-meta font-medium text-ink-soft">Nhóm hàng</span>
        <select className={O_NHAP} value={nhom} onChange={(e) => setNhom(e.target.value)}>
          <option value="">Chưa có nhóm</option>
          {goi.nhom_hang.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>
      <label className="block">
        <span className="mb-1 block text-meta font-medium text-ink-soft">Mã phòng khám (KiotViet, nếu có)</span>
        <input className={O_NHAP} value={maKv} onChange={(e) => setMaKv(e.target.value)} maxLength={32} placeholder="VD: SP000214" />
      </label>
      <label className="block">
        <span className="mb-1 block text-meta font-medium text-ink-soft">Đơn giá (đ)</span>
        <input className={O_NHAP} value={gia} inputMode="numeric" onChange={(e) => setGia(e.target.value)} placeholder="Để trống = chưa có giá" />
      </label>
      <label className="block">
        <span className="mb-1 block text-meta font-medium text-ink-soft">Nhóm việc (để xếp phòng)</span>
        <select className={O_NHAP} value={node} onChange={(e) => setNode(e.target.value)}>
          <option value="">Chưa chọn — gán phòng sau</option>
          {nhomViec.map((n) => (
            <option key={n.ma} value={n.ma}>
              {n.ten}
            </option>
          ))}
        </select>
      </label>
      <label className="block">
        <span className="mb-1 block text-meta font-medium text-ink-soft">Bên thu</span>
        <select className={O_NHAP} value={benThu} onChange={(e) => setBenThu(e.target.value as typeof benThu)}>
          <option value="">Theo nhóm việc (mặc định)</option>
          <option value="CLINIC">Phòng khám thu</option>
          <option value="EXTERNAL_PARTNER">Thu hộ đối tác</option>
        </select>
      </label>
      <div className="sm:col-span-2 lg:col-span-3">
        <Button type="button" variant="primary" size="lg" disabled={ban || !ten.trim()} onClick={() => void them()}>
          <Plus className="size-4" aria-hidden />
          {ban ? "Đang lưu…" : "Thêm dịch vụ"}
        </Button>
      </div>
    </div>
  );
}
