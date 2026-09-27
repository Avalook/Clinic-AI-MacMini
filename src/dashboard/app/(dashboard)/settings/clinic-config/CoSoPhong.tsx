"use client";

// CƠ SỞ → PHÒNG, GỌN (Tuyền 27/09/2026: "cho thêm cơ sở, chỉnh sửa cơ sở, thêm
// phòng, chỉnh sửa phòng, thêm nhân sự vào phòng đó, các node lego vào phòng
// đó, chứ không có cả đống như rác vậy được").
//
// Trước: mỗi phòng bày ~50 chip bước (tick / bỏ tick) — đọc không ra phòng làm
// gì. Nay mỗi phòng MỘT DÒNG (tên · việc chính · số việc · số người); bấm dòng mở
// phần sửa: tên, tầng, bật/tắt, việc ĐÃ GẮN (★ việc chính không bỏ được) + ô
// "+ Thêm việc", nhân sự ĐÃ GẮN + ô "+ Thêm người".
//
// Nhân sự của phòng = lego Phòng dịch vụ gắn theo phòng — máy chủ
// (`nhan_su_phong_service`) đọc/ghi qua cùng cửa với màn Phân quyền. Người
// đang làm được MỌI phòng không thêm/bớt ở đây (máy chủ chặn thu hẹp).

import { Building2, ChevronDown, ChevronRight, Star, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import type { ConfigLocation, ConfigRoom, ConfigStaff, NodeDef } from "./types";

interface NguoiPhong {
  staff_id: string;
  full_name: string;
}
interface GoiNhanSu {
  phong: Record<string, NguoiPhong[]>;
  moi_phong: NguoiPhong[];
}

const O = "h-8 rounded-control border border-line bg-surface px-2 text-meta text-ink";

async function goi(method: "PUT" | "POST", what: string, payload: Record<string, unknown>) {
  const res = await fetch("/api/clinic-config", {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ what, ...payload }),
  });
  if (!res.ok) {
    const b = (await res.json().catch(() => ({}))) as { detail?: string; error?: string; message?: string };
    throw new Error(b.detail ?? b.message ?? b.error ?? "Không lưu được.");
  }
}

export default function CoSoPhong({
  locations,
  nodes,
  staff,
  onDocLai,
  onLoi,
}: {
  locations: ConfigLocation[];
  nodes: NodeDef[];
  staff: ConfigStaff[];
  onDocLai: () => Promise<void>;
  onLoi: (cau: string | null) => void;
}) {
  const [nhanSu, setNhanSu] = useState<GoiNhanSu>({ phong: {}, moi_phong: [] });
  const [dangLam, setDangLam] = useState(false);
  const [moCoSo, setMoCoSo] = useState<string | null>(null); // "moi" | location_id
  const [moPhong, setMoPhong] = useState<string | null>(null);
  const [themPhongO, setThemPhongO] = useState<string | null>(null);

  const [lanNap, setLanNap] = useState(0);
  const taiNhanSu = useCallback(async () => setLanNap((n) => n + 1), []);
  useEffect(() => {
    let huy = false;
    void fetch("/api/clinic-config?what=room-staff", { cache: "no-store" })
      .then((r) => r.json())
      .catch(() => null)
      .then((d: (GoiNhanSu & { ok?: boolean }) | null) => {
        if (!huy && d?.phong) setNhanSu({ phong: d.phong, moi_phong: d.moi_phong ?? [] });
      });
    return () => {
      huy = true;
    };
  }, [lanNap]);

  const lam = async (viec: () => Promise<void>, sau?: () => void) => {
    setDangLam(true);
    onLoi(null);
    try {
      await viec();
      await onDocLai();
      await taiNhanSu();
      sau?.();
    } catch (e) {
      onLoi(e instanceof Error ? e.message : String(e));
    } finally {
      setDangLam(false);
    }
  };

  const tenBuoc = (code: string) => nodes.find((n) => n.code === code)?.name ?? code;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-body font-semibold text-ink">Cơ sở &amp; phòng</h2>
        <Button size="sm" variant="soft" onClick={() => setMoCoSo(moCoSo === "moi" ? null : "moi")}>
          + Thêm cơ sở
        </Button>
      </div>
      {moCoSo === "moi" ? (
        <FormCoSo
          dangLam={dangLam}
          onThoi={() => setMoCoSo(null)}
          onLuu={(ten, diaChi) =>
            void lam(() => goi("POST", "location-create", { name: ten, address: diaChi || null }), () =>
              setMoCoSo(null),
            )
          }
        />
      ) : null}

      {locations.map((loc) => {
        const soPhong = loc.floors.reduce((s, f) => s + f.rooms.length, 0);
        return (
          <section key={loc.location_id} className="rounded-card border border-line bg-surface shadow-card">
            <header className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2.5">
              <Building2 className="size-4 shrink-0 text-brand-600" aria-hidden="true" />
              <h3 className="text-body font-semibold text-ink">{loc.name}</h3>
              <span className="text-label text-ink-muted">{loc.code}</span>
              {loc.address ? <span className="truncate text-label text-ink-muted">· {loc.address}</span> : null}
              {!loc.is_active ? <Chip tone="neutral">ngừng hoạt động</Chip> : null}
              <span className="ml-auto text-label text-ink-muted">{soPhong} phòng</span>
              <Button size="sm" variant="ghost" onClick={() => setMoCoSo(moCoSo === loc.location_id ? null : loc.location_id)}>
                Sửa
              </Button>
              <Button
                size="sm"
                variant="soft"
                onClick={() => setThemPhongO(themPhongO === loc.location_id ? null : loc.location_id)}
              >
                + Thêm phòng
              </Button>
            </header>

            {moCoSo === loc.location_id ? (
              <div className="border-b border-line p-3">
                <FormCoSo
                  ten={loc.name}
                  diaChi={loc.address ?? ""}
                  dangHoatDong={loc.is_active}
                  dangLam={dangLam}
                  onThoi={() => setMoCoSo(null)}
                  onLuu={(ten, diaChi, bat) =>
                    void lam(
                      () =>
                        goi("PUT", "location", {
                          location_id: loc.location_id,
                          name: ten,
                          address: diaChi || null,
                          is_active: bat,
                        }),
                      () => setMoCoSo(null),
                    )
                  }
                />
              </div>
            ) : null}

            {themPhongO === loc.location_id ? (
              <FormThemPhong
                nodes={nodes}
                dangLam={dangLam}
                onThoi={() => setThemPhongO(null)}
                onThem={(ten, buoc, tang) =>
                  void lam(
                    () =>
                      goi("POST", "room-create", {
                        location_id: loc.location_id,
                        name: ten,
                        node_code: buoc,
                        floor: tang || null,
                      }),
                    () => setThemPhongO(null),
                  )
                }
              />
            ) : null}

            {soPhong === 0 ? (
              <p className="px-4 py-3 text-meta text-ink-faint">Chưa có phòng nào.</p>
            ) : (
              loc.floors.map((f) => (
                <div key={f.floor ?? "_"}>
                  <p className="bg-surface-muted px-4 py-1 text-label font-semibold uppercase text-ink-muted">
                    {f.floor ? `Tầng ${f.floor.replace(/^Tầng\s*/i, "")}` : "Chưa khai tầng"}
                  </p>
                  <ul>
                    {f.rooms.map((r) => (
                      <DongPhong
                        key={r.room_id}
                        phong={r}
                        tang={f.floor}
                        mo={moPhong === r.room_id}
                        onMo={() => setMoPhong(moPhong === r.room_id ? null : r.room_id)}
                        nodes={nodes}
                        tenBuoc={tenBuoc}
                        nguoi={nhanSu.phong[r.room_id] ?? []}
                        moiPhong={nhanSu.moi_phong}
                        staff={staff}
                        dangLam={dangLam}
                        lam={lam}
                      />
                    ))}
                  </ul>
                </div>
              ))
            )}
          </section>
        );
      })}
    </div>
  );
}

function DongPhong({
  phong: r,
  tang,
  mo,
  onMo,
  nodes,
  tenBuoc,
  nguoi,
  moiPhong,
  staff,
  dangLam,
  lam,
}: {
  phong: ConfigRoom;
  tang: string | null;
  mo: boolean;
  onMo: () => void;
  nodes: NodeDef[];
  tenBuoc: (c: string) => string;
  nguoi: NguoiPhong[];
  moiPhong: NguoiPhong[];
  staff: ConfigStaff[];
  dangLam: boolean;
  lam: (viec: () => Promise<void>, sau?: () => void) => Promise<void>;
}) {
  const [ten, setTen] = useState(r.name ?? "");
  const [tangMoi, setTangMoi] = useState(tang ?? "");
  const coNguoi = new Set([...nguoi, ...moiPhong].map((n) => n.staff_id));
  const conLaiViec = nodes.filter((n) => !r.serves.includes(n.code));
  const conLaiNguoi = staff.filter((s) => !coNguoi.has(s.staff_id));
  const doiViec = (next: string[]) => void lam(() => goi("PUT", "room-nodes", { room_id: r.room_id, node_codes: next }));
  const doiNguoi = (staffId: string, them: boolean) =>
    void lam(() => goi("PUT", "room-staff", { room_id: r.room_id, staff_id: staffId, them }));

  return (
    <li className="border-t border-line first:border-t-0">
      <button
        type="button"
        aria-expanded={mo}
        onClick={onMo}
        className={`flex w-full items-center gap-2 px-4 py-2 text-left hover:bg-surface-sunken ${mo ? "bg-surface-selected" : ""}`}
      >
        {mo ? (
          <ChevronDown className="size-4 shrink-0 text-ink-muted" aria-hidden="true" />
        ) : (
          <ChevronRight className="size-4 shrink-0 text-ink-muted" aria-hidden="true" />
        )}
        <span className={`min-w-0 truncate text-body font-medium ${r.is_active ? "text-ink" : "text-ink-faint line-through"}`}>
          {r.name ?? r.code}
        </span>
        {r.primary_node ? <span className="truncate text-meta text-ink-muted">· {tenBuoc(r.primary_node)}</span> : null}
        <span className="ml-auto shrink-0 text-label text-ink-muted">
          {r.serves.length} việc · {nguoi.length} người
        </span>
        {!r.is_active ? <Chip tone="neutral">Tắt</Chip> : null}
      </button>

      {mo ? (
        <div className="space-y-3 border-t border-line bg-surface-muted/40 px-4 py-3">
          <div className="flex flex-wrap items-end gap-2">
            <label className="flex min-w-48 flex-1 flex-col gap-0.5 text-label text-ink-muted">
              Tên phòng
              <input value={ten} onChange={(e) => setTen(e.target.value)} className={O} />
            </label>
            <label className="flex w-28 flex-col gap-0.5 text-label text-ink-muted">
              Tầng
              <input value={tangMoi} onChange={(e) => setTangMoi(e.target.value)} placeholder="1 · Trệt" className={O} />
            </label>
            <Button
              size="sm"
              variant="primary"
              disabled={dangLam || (ten.trim() === (r.name ?? "") && tangMoi.trim() === (tang ?? ""))}
              onClick={() =>
                void lam(async () => {
                  if (ten.trim() && ten.trim() !== (r.name ?? "")) {
                    await goi("PUT", "room-name", { room_id: r.room_id, name: ten.trim() });
                  }
                  if (tangMoi.trim() !== (tang ?? "")) {
                    await goi("PUT", "room-floor", { room_id: r.room_id, floor: tangMoi.trim() });
                  }
                })
              }
            >
              Lưu
            </Button>
            <Button
              size="sm"
              variant={r.is_active ? "danger" : "secondary"}
              disabled={dangLam}
              onClick={() => void lam(() => goi("PUT", "room-active", { room_id: r.room_id, is_active: !r.is_active }))}
            >
              {r.is_active ? "Tắt phòng" : "Bật lại phòng"}
            </Button>
          </div>

          <div>
            <p className="mb-1 text-label font-semibold uppercase text-ink-muted">Phòng làm việc gì</p>
            <div className="flex flex-wrap items-center gap-1.5">
              {r.serves.map((c) => {
                const chinh = c === r.primary_node;
                return (
                  <span
                    key={c}
                    className={`inline-flex h-7 items-center gap-1 rounded-full px-2.5 text-meta ${
                      chinh ? "bg-brand-100 font-medium text-brand-800" : "bg-surface text-ink ring-1 ring-inset ring-line"
                    }`}
                  >
                    {chinh ? <Star className="size-3" aria-hidden="true" /> : null}
                    {tenBuoc(c)}
                    {!chinh ? (
                      <button
                        type="button"
                        aria-label={`Bỏ ${tenBuoc(c)}`}
                        disabled={dangLam}
                        onClick={() => doiViec(r.serves.filter((x) => x !== c))}
                        className="rounded-full p-0.5 text-ink-muted hover:bg-surface-sunken hover:text-danger"
                      >
                        <X className="size-3" aria-hidden="true" />
                      </button>
                    ) : null}
                  </span>
                );
              })}
              <select
                aria-label="Thêm việc cho phòng"
                value=""
                disabled={dangLam}
                onChange={(e) => e.target.value && doiViec([...r.serves, e.target.value].sort())}
                className={`${O} text-ink-muted`}
              >
                <option value="">+ Thêm việc…</option>
                {conLaiViec.map((n) => (
                  <option key={n.code} value={n.code}>
                    {n.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <p className="mb-1 text-label font-semibold uppercase text-ink-muted">Nhân sự làm ở phòng này</p>
            <div className="flex flex-wrap items-center gap-1.5">
              {nguoi.length === 0 ? <span className="text-meta text-ink-faint">Chưa gắn ai riêng.</span> : null}
              {nguoi.map((n) => (
                <span
                  key={n.staff_id}
                  className="inline-flex h-7 items-center gap-1 rounded-full bg-surface px-2.5 text-meta text-ink ring-1 ring-inset ring-line"
                >
                  {n.full_name}
                  <button
                    type="button"
                    aria-label={`Bỏ ${n.full_name} khỏi phòng`}
                    disabled={dangLam}
                    onClick={() => doiNguoi(n.staff_id, false)}
                    className="rounded-full p-0.5 text-ink-muted hover:bg-surface-sunken hover:text-danger"
                  >
                    <X className="size-3" aria-hidden="true" />
                  </button>
                </span>
              ))}
              <select
                aria-label="Thêm người vào phòng"
                value=""
                disabled={dangLam}
                onChange={(e) => e.target.value && doiNguoi(e.target.value, true)}
                className={`${O} text-ink-muted`}
              >
                <option value="">+ Thêm người…</option>
                {conLaiNguoi.map((s) => (
                  <option key={s.staff_id} value={s.staff_id}>
                    {s.full_name}
                  </option>
                ))}
              </select>
            </div>
            {moiPhong.length > 0 ? (
              <details className="mt-1.5 text-label text-ink-muted">
                <summary className="cursor-pointer">+ {moiPhong.length} người làm được mọi phòng (sửa ở Phân quyền)</summary>
                <p className="mt-1">{moiPhong.map((n) => n.full_name).join(", ")}</p>
              </details>
            ) : null}
          </div>
        </div>
      ) : null}
    </li>
  );
}

function FormCoSo({
  ten = "",
  diaChi = "",
  dangHoatDong,
  dangLam,
  onLuu,
  onThoi,
}: {
  ten?: string;
  diaChi?: string;
  /** undefined = đang thêm mới (không có công tắc). */
  dangHoatDong?: boolean;
  dangLam: boolean;
  onLuu: (ten: string, diaChi: string, bat: boolean) => void;
  onThoi: () => void;
}) {
  const [t, setT] = useState(ten);
  const [d, setD] = useState(diaChi);
  const [bat, setBat] = useState(dangHoatDong ?? true);
  return (
    <div className="flex flex-wrap items-end gap-2 rounded-card border border-line bg-surface p-3">
      <label className="flex min-w-48 flex-1 flex-col gap-0.5 text-label text-ink-muted">
        Tên cơ sở
        <input value={t} onChange={(e) => setT(e.target.value)} placeholder="VD: Kim Ngưu" className={O} />
      </label>
      <label className="flex min-w-60 flex-[2] flex-col gap-0.5 text-label text-ink-muted">
        Địa chỉ
        <input value={d} onChange={(e) => setD(e.target.value)} className={O} />
      </label>
      {dangHoatDong !== undefined ? (
        <label className="flex h-8 items-center gap-1.5 text-meta text-ink">
          <input type="checkbox" checked={bat} onChange={(e) => setBat(e.target.checked)} className="size-4 accent-brand-600" />
          Đang hoạt động
        </label>
      ) : null}
      <Button size="sm" variant="primary" disabled={dangLam || !t.trim()} onClick={() => onLuu(t.trim(), d.trim(), bat)}>
        {dangHoatDong === undefined ? "Thêm cơ sở" : "Lưu"}
      </Button>
      <Button size="sm" variant="ghost" onClick={onThoi}>
        Thôi
      </Button>
    </div>
  );
}

function FormThemPhong({
  nodes,
  dangLam,
  onThem,
  onThoi,
}: {
  nodes: NodeDef[];
  dangLam: boolean;
  onThem: (ten: string, buoc: string, tang: string) => void;
  onThoi: () => void;
}) {
  const [ten, setTen] = useState("");
  const [buoc, setBuoc] = useState("");
  const [tang, setTang] = useState("");
  return (
    <div className="flex flex-wrap items-end gap-2 border-b border-line bg-surface-muted/40 px-4 py-3">
      <label className="flex min-w-48 flex-1 flex-col gap-0.5 text-label text-ink-muted">
        Tên phòng mới
        <input value={ten} onChange={(e) => setTen(e.target.value)} placeholder="VD: Siêu âm 4" className={O} />
      </label>
      <label className="flex min-w-48 flex-1 flex-col gap-0.5 text-label text-ink-muted">
        Việc chính
        <select value={buoc} onChange={(e) => setBuoc(e.target.value)} className={O}>
          <option value="">— chọn —</option>
          {nodes.map((n) => (
            <option key={n.code} value={n.code}>
              {n.name}
            </option>
          ))}
        </select>
      </label>
      <label className="flex w-28 flex-col gap-0.5 text-label text-ink-muted">
        Tầng
        <input value={tang} onChange={(e) => setTang(e.target.value)} placeholder="1 · Trệt" className={O} />
      </label>
      <Button size="sm" variant="primary" disabled={dangLam || !ten.trim() || !buoc} onClick={() => onThem(ten.trim(), buoc, tang.trim())}>
        Thêm phòng
      </Button>
      <Button size="sm" variant="ghost" onClick={onThoi}>
        Thôi
      </Button>
    </div>
  );
}
