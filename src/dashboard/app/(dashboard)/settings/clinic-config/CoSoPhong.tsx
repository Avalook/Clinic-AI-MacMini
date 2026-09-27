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
// NHÂN SỰ CỦA PHÒNG = LỊCH CỦA PHÒNG (Tuyền 27/09 tối: "cấu trúc phòng liên
// quan đến lịch làm việc, bản chất là 1"). Phòng → vị trí làm việc → ai được
// xếp theo ngày/ca. Đọc `lich-phong`; ghi thẳng vào lịch (`/api/roster`) và
// vị trí (`/api/day-noi`) — cùng dữ liệu màn Lịch làm việc, không bảng thứ hai.

import { Building2, ChevronDown, ChevronLeft, ChevronRight, Star, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { todayVn } from "@/lib/roster";
import type { ConfigLocation, ConfigRoom, ConfigStaff, NodeDef } from "./types";

interface CaLich {
  id: string;
  ngay: string;
  ca: string;
  staff_id: string | null;
  ten: string;
  duyet: boolean;
}
interface ViTri {
  id: string;
  code: string;
  ten: string;
  nhom_nghe: string;
  ca: CaLich[];
}
interface GoiLich {
  tuan: string;
  ngay: string[];
  phong: Record<string, ViTri[]>;
}

const TEN_CA: Record<string, string> = { SANG: "Sáng", CHIEU: "Chiều", TOI: "Tối", FULL: "Cả ngày" };
const THU = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];

function congNgay(iso: string, n: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const t = new Date(Date.UTC(y, m - 1, d + n));
  return t.toISOString().slice(0, 10);
}

const O = "h-8 rounded-control border border-line bg-surface px-2 text-meta text-ink";

async function goi(method: "PUT" | "POST", what: string, payload: Record<string, unknown>) {
  await goiUrl("/api/clinic-config", method, { what, ...payload });
}

async function goiUrl(url: string, method: "PUT" | "POST" | "DELETE", body: Record<string, unknown>) {
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
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
  const [lich, setLich] = useState<GoiLich | null>(null);
  const [tuan, setTuan] = useState<string | null>(null);
  const [dangLam, setDangLam] = useState(false);
  const [moCoSo, setMoCoSo] = useState<string | null>(null); // "moi" | location_id
  const [moPhong, setMoPhong] = useState<string | null>(null);
  const [themPhongO, setThemPhongO] = useState<string | null>(null);

  const [lanNap, setLanNap] = useState(0);
  const taiNhanSu = useCallback(async () => setLanNap((n) => n + 1), []);
  useEffect(() => {
    let huy = false;
    void fetch(`/api/clinic-config?what=lich-phong${tuan ? `&tuan=${tuan}` : ""}`, { cache: "no-store" })
      .then((r) => r.json())
      .catch(() => null)
      .then((d: (GoiLich & { ok?: boolean }) | null) => {
        if (!huy && d?.phong) setLich({ tuan: d.tuan, ngay: d.ngay, phong: d.phong });
      });
    return () => {
      huy = true;
    };
  }, [lanNap, tuan]);

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
                        viTri={lich?.phong[r.room_id] ?? []}
                        lich={lich}
                        doiTuan={(n) => lich && setTuan(congNgay(lich.tuan, n * 7))}
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
  viTri,
  lich,
  doiTuan,
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
  viTri: ViTri[];
  lich: GoiLich | null;
  doiTuan: (n: number) => void;
  staff: ConfigStaff[];
  dangLam: boolean;
  lam: (viec: () => Promise<void>, sau?: () => void) => Promise<void>;
}) {
  const [ten, setTen] = useState(r.name ?? "");
  const [tangMoi, setTangMoi] = useState(tang ?? "");
  const conLaiViec = nodes.filter((n) => !r.serves.includes(n.code));
  const doiViec = (next: string[]) => void lam(() => goi("PUT", "room-nodes", { room_id: r.room_id, node_codes: next }));
  const homNay = todayVn();
  const nguoiHomNay = new Set(
    viTri.flatMap((v) => v.ca.filter((c) => c.ngay === homNay).map((c) => c.staff_id ?? c.ten)),
  ).size;

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
          {r.serves.length} việc · {nguoiHomNay} người hôm nay
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

          <LichPhong
            phong={r}
            viTri={viTri}
            lich={lich}
            doiTuan={doiTuan}
            staff={staff}
            dangLam={dangLam}
            lam={lam}
          />
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

/** LỊCH CỦA PHÒNG — vị trí × 7 ngày; xếp / bỏ người ghi thẳng vào lịch làm
 *  việc (`/api/roster`); thêm vị trí cho phòng (`/api/day-noi`). */
function LichPhong({
  phong: r,
  viTri,
  lich,
  doiTuan,
  staff,
  dangLam,
  lam,
}: {
  phong: ConfigRoom;
  viTri: ViTri[];
  lich: GoiLich | null;
  doiTuan: (n: number) => void;
  staff: ConfigStaff[];
  dangLam: boolean;
  lam: (viec: () => Promise<void>, sau?: () => void) => Promise<void>;
}) {
  const homNay = todayVn();
  const [vt, setVt] = useState("");
  const [ngay, setNgay] = useState(homNay);
  const [ca, setCa] = useState("FULL");
  const [nguoi, setNguoi] = useState("");
  const [moVt, setMoVt] = useState(false);
  const [tenVt, setTenVt] = useState("");
  const [ngheVt, setNgheVt] = useState("DIEU_DUONG");
  if (!lich) return <p className="text-meta text-ink-muted">Đang tải lịch…</p>;
  const ngayChon = lich.ngay.includes(ngay) ? ngay : lich.ngay[0];
  const vtChon = vt || viTri[0]?.code || "";
  const nv = staff.find((s) => s.staff_id === nguoi);

  return (
    <div>
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <p className="text-label font-semibold uppercase text-ink-muted">Lịch của phòng</p>
        <div className="flex items-center gap-1 text-meta text-ink-soft">
          <button type="button" aria-label="Tuần trước" onClick={() => doiTuan(-1)} className="rounded-control p-1 hover:bg-surface-sunken">
            <ChevronLeft className="size-4" aria-hidden="true" />
          </button>
          <span className="tabular-nums">
            {lich.ngay[0].slice(8, 10)}/{lich.ngay[0].slice(5, 7)} – {lich.ngay[6].slice(8, 10)}/{lich.ngay[6].slice(5, 7)}
          </span>
          <button type="button" aria-label="Tuần sau" onClick={() => doiTuan(1)} className="rounded-control p-1 hover:bg-surface-sunken">
            <ChevronRight className="size-4" aria-hidden="true" />
          </button>
        </div>
        <span className="text-label text-ink-muted">cùng dữ liệu màn Lịch làm việc</span>
      </div>

      {viTri.length === 0 ? (
        <p className="text-meta text-ink-faint">Phòng chưa có vị trí làm việc — thêm vị trí để xếp lịch.</p>
      ) : (
        <div className="overflow-x-auto rounded-control border border-line bg-surface">
          <table className="w-full min-w-160 text-meta">
            <thead className="bg-surface-muted text-label text-ink-muted">
              <tr>
                <th className="px-2 py-1 text-left font-semibold">Vị trí</th>
                {lich.ngay.map((d, i) => (
                  <th key={d} className={`px-1 py-1 text-left font-semibold ${d === homNay ? "text-brand-700" : ""}`}>
                    {THU[i]} {d.slice(8, 10)}/{d.slice(5, 7)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {viTri.map((v) => (
                <tr key={v.id} className="border-t border-line align-top">
                  <td className="px-2 py-1.5 font-medium text-ink">{v.ten}</td>
                  {lich.ngay.map((d) => (
                    <td key={d} className={`px-1 py-1 ${d === homNay ? "bg-brand-50/60" : ""}`}>
                      <div className="flex flex-col gap-0.5">
                        {v.ca
                          .filter((c) => c.ngay === d)
                          .map((c) => (
                            <span
                              key={c.id}
                              title={c.duyet ? undefined : "Chờ duyệt"}
                              className={`inline-flex items-center gap-0.5 rounded-control px-1 ${
                                c.duyet ? "bg-surface-muted text-ink" : "bg-warning-bg text-warning"
                              }`}
                            >
                              <span className="truncate">{c.ten}</span>
                              {c.ca !== "FULL" ? <span className="text-ink-muted">· {TEN_CA[c.ca] ?? c.ca}</span> : null}
                              <button
                                type="button"
                                aria-label={`Bỏ ${c.ten} khỏi lịch ${d}`}
                                disabled={dangLam}
                                onClick={() => void lam(() => goiUrl("/api/roster", "DELETE", { id: c.id }))}
                                className="ml-auto rounded-full text-ink-muted hover:text-danger"
                              >
                                <X className="size-3" aria-hidden="true" />
                              </button>
                            </span>
                          ))}
                      </div>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {viTri.length > 0 ? (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <select aria-label="Vị trí" value={vtChon} onChange={(e) => setVt(e.target.value)} className={O}>
            {viTri.map((v) => (
              <option key={v.code} value={v.code}>
                {v.ten}
              </option>
            ))}
          </select>
          <select aria-label="Ngày" value={ngayChon} onChange={(e) => setNgay(e.target.value)} className={O}>
            {lich.ngay.map((d, i) => (
              <option key={d} value={d}>
                {THU[i]} {d.slice(8, 10)}/{d.slice(5, 7)}
              </option>
            ))}
          </select>
          <select aria-label="Ca" value={ca} onChange={(e) => setCa(e.target.value)} className={O}>
            {Object.entries(TEN_CA).map(([k, t]) => (
              <option key={k} value={k}>
                {t}
              </option>
            ))}
          </select>
          <select aria-label="Người" value={nguoi} onChange={(e) => setNguoi(e.target.value)} className={`${O} min-w-40`}>
            <option value="">— chọn người —</option>
            {staff.map((s) => (
              <option key={s.staff_id} value={s.staff_id}>
                {s.full_name}
              </option>
            ))}
          </select>
          <Button
            size="sm"
            variant="primary"
            disabled={dangLam || !nguoi || !vtChon}
            onClick={() =>
              void lam(
                () =>
                  goiUrl("/api/roster", "POST", {
                    week_start: lich.tuan,
                    work_date: ngayChon,
                    station: vtChon,
                    shift: ca,
                    staff_id: nguoi,
                    staff_name: nv?.full_name ?? "",
                  }),
                () => setNguoi(""),
              )
            }
          >
            Xếp vào lịch
          </Button>
        </div>
      ) : null}

      <div className="mt-2">
        {moVt ? (
          <div className="flex flex-wrap items-center gap-1.5">
            <input
              value={tenVt}
              onChange={(e) => setTenVt(e.target.value)}
              placeholder="VD: BS siêu âm 2"
              aria-label="Tên vị trí"
              className={`${O} min-w-48`}
            />
            <select aria-label="Nhóm nghề" value={ngheVt} onChange={(e) => setNgheVt(e.target.value)} className={O}>
              <option value="BAC_SI">Bác sĩ</option>
              <option value="DIEU_DUONG">Điều dưỡng / nhân viên</option>
              <option value="DOI_TAC">Đối tác</option>
            </select>
            <Button
              size="sm"
              variant="primary"
              disabled={dangLam || !tenVt.trim()}
              onClick={() =>
                void lam(
                  () =>
                    goiUrl("/api/day-noi", "POST", {
                      thao_tac: "vi-tri-moi",
                      du_lieu: { ten: tenVt.trim(), nhom_nghe: ngheVt, room_id: r.room_id },
                    }),
                  () => {
                    setTenVt("");
                    setMoVt(false);
                  },
                )
              }
            >
              Thêm vị trí
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setMoVt(false)}>
              Thôi
            </Button>
          </div>
        ) : (
          <Button size="sm" variant="ghost" onClick={() => setMoVt(true)}>
            + Thêm vị trí cho phòng
          </Button>
        )}
      </div>
    </div>
  );
}
