"use client";

// KHỐI "PHÒNG LÀM VIỆC GÌ" (Tuyền chốt 30/09/2026).
//
// Trước: ô "+ Thêm việc…" liệt kê MỌI node, kể cả việc quản trị (huỷ lịch, đổi
// lịch, khai báo lịch làm việc, đối soát…). Nay ô thêm chỉ mời DỊCH VỤ / CHỈ
// ĐỊNH, gom theo nhóm, tìm được:
//   · tick "Cả nhóm"   = gắn node (như cũ) — phòng làm mọi dịch vụ của nhóm
//                        CHƯA gắn phòng riêng;
//   · tick từng dịch vụ = dòng clinic_room_service — dịch vụ ấy CHỈ làm ở các
//                        phòng được gắn (vd Ghế điện từ trường → Phòng Sàn chậu).
// Danh sách "chọn được" là QUYẾT ĐỊNH của máy chủ (`viec_chon_duoc`); màn chỉ vẽ
// và lọc theo chữ gõ. Chip việc quầy đã gắn (LUOTKHAM-*, THUOC-*…) vẫn hiện và
// bỏ được, chỉ không mời thêm.
//
// PHÒNG CHUYÊN ★ (Tuyền chốt 07/10/2026): mỗi nhóm DỊCH VỤ của phòng có nút
// "☆ chuyên" / "★ chuyên" — đánh dấu phòng này là phòng chuyên của nhóm ấy. Chỉ
// để TICK SẴN khi phòng Nhận chỉ định chưa hướng dẫn và để quầy gợi ý hướng dẫn;
// không thu hẹp phòng làm được, không ẩn khách. Máy chủ ghi nhật ký mỗi lần đổi.

import { Star, X } from "lucide-react";
import { useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import ChipChon from "@/components/ui/ChipChon";
import { unaccentVi } from "@/lib/validation";
import type { ConfigRoom, ViecChonDuoc } from "./types";

const O = "h-8 rounded-control border border-line bg-surface px-2 text-meta text-ink";

function NutChuyen({
  ten,
  chuyen,
  dangLam,
  onDoi,
}: {
  ten: string;
  chuyen: boolean;
  dangLam: boolean;
  onDoi: () => void;
}) {
  return (
    <button
      type="button"
      disabled={dangLam}
      onClick={onDoi}
      aria-pressed={chuyen}
      aria-label={chuyen ? `Bỏ phòng chuyên ${ten}` : `Đánh phòng chuyên ${ten}`}
      title={
        chuyen
          ? "Phòng chuyên ★ của nhóm này — bấm để bỏ"
          : "Đánh phòng này là phòng chuyên ★ của nhóm (tick sẵn khi nhận khách, quầy gợi ý)"
      }
      className={`inline-flex h-7 items-center gap-0.5 rounded-full px-2 text-meta ring-1 ring-inset ${
        chuyen ? "bg-warning-bg font-medium text-warning ring-warning" : "bg-surface text-ink-muted ring-line"
      } hover:bg-surface-sunken`}
    >
      <Star className={`size-3 ${chuyen ? "fill-warning" : ""}`} aria-hidden="true" />
      chuyên
    </button>
  );
}

function ChipDaGan({
  ten,
  chinh,
  ghiChu,
  dangLam,
  onBo,
}: {
  ten: string;
  chinh?: boolean;
  ghiChu?: string;
  dangLam: boolean;
  onBo: () => void;
}) {
  return (
    <span
      title={ghiChu}
      className={`inline-flex h-7 items-center gap-1 rounded-full px-2.5 text-meta ${
        chinh ? "bg-brand-100 font-medium text-brand-800" : "bg-surface text-ink ring-1 ring-inset ring-line"
      }`}
    >
      {chinh ? <Star className="size-3" aria-hidden="true" /> : null}
      {ten}
      {!chinh ? (
        <button
          type="button"
          aria-label={`Bỏ ${ten}`}
          disabled={dangLam}
          onClick={onBo}
          className="rounded-full p-0.5 text-ink-muted hover:bg-surface-sunken hover:text-danger"
        >
          <X className="size-3" aria-hidden="true" />
        </button>
      ) : null}
    </span>
  );
}

export default function ViecCuaPhong({
  phong: r,
  viec,
  tenBuoc,
  dangLam,
  doiViec,
  doiDichVu,
  doiChuyen,
}: {
  phong: ConfigRoom;
  viec: ViecChonDuoc[];
  tenBuoc: (c: string) => string;
  dangLam: boolean;
  doiViec: (nodes: string[]) => void;
  doiDichVu: (maDichVu: string[]) => void;
  doiChuyen: (node: string, chuyen: boolean) => void;
}) {
  const [mo, setMo] = useState(false);
  const [tim, setTim] = useState("");
  const [moNhom, setMoNhom] = useState<string | null>(null);
  const dichVuLe = useMemo(() => r.dich_vu ?? [], [r.dich_vu]);
  const daGanLe = useMemo(() => new Set(dichVuLe.map((d) => d.ma)), [dichVuLe]);

  const kim = unaccentVi(tim.trim());
  const nhomHien = useMemo(
    () =>
      viec
        .map((g) => {
          if (!kim) return { g, ds: g.dich_vu, khopTen: true };
          const khopTen = unaccentVi(g.ten).includes(kim);
          const ds = g.dich_vu.filter(
            (d) => unaccentVi(d.ten).includes(kim) || unaccentVi(d.ma_kv ?? "").includes(kim),
          );
          return { g, ds: khopTen ? g.dich_vu : ds, khopTen };
        })
        .filter((x) => x.khopTen || x.ds.length > 0),
    [viec, kim],
  );

  const doiNhom = (node: string) =>
    doiViec(r.serves.includes(node) ? r.serves.filter((x) => x !== node) : [...r.serves, node].sort());
  const doiMot = (ma: string) =>
    doiDichVu(daGanLe.has(ma) ? [...daGanLe].filter((x) => x !== ma) : [...daGanLe, ma].sort());

  return (
    <div>
      <p className="mb-1 text-label font-semibold uppercase text-ink-muted">Phòng làm việc gì</p>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-meta text-ink-muted">Nhóm việc</span>
        {r.serves.map((c) => (
          <span key={c} className="inline-flex items-center gap-0.5">
            <ChipDaGan
              ten={tenBuoc(c)}
              chinh={c === r.primary_node}
              dangLam={dangLam}
              onBo={() => doiViec(r.serves.filter((x) => x !== c))}
            />
            {c.startsWith("DICHVU-") ? (
              <NutChuyen
                ten={tenBuoc(c)}
                chuyen={(r.chuyen ?? []).includes(c)}
                dangLam={dangLam}
                onDoi={() => doiChuyen(c, !(r.chuyen ?? []).includes(c))}
              />
            ) : null}
          </span>
        ))}
      </div>
      {dichVuLe.length > 0 ? (
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
          <span className="text-meta text-ink-muted">Dịch vụ riêng (chỉ làm ở phòng được gắn)</span>
          {dichVuLe.map((d) => (
            <ChipDaGan
              key={d.ma}
              ten={d.ten}
              ghiChu="Dịch vụ gắn riêng — chỉ các phòng được gắn làm dịch vụ này"
              dangLam={dangLam}
              onBo={() => doiDichVu([...daGanLe].filter((x) => x !== d.ma))}
            />
          ))}
        </div>
      ) : null}
      <div className="mt-1.5">
        <Button size="sm" variant="soft" aria-expanded={mo} onClick={() => setMo(!mo)}>
          {mo ? "Đóng" : "+ Thêm dịch vụ"}
        </Button>
      </div>

      {mo ? (
        <div className="mt-2 rounded-card border border-line bg-surface p-3">
          <input
            value={tim}
            onChange={(e) => setTim(e.target.value)}
            placeholder="Tìm dịch vụ, nhóm, mã KiotViet…"
            aria-label="Tìm dịch vụ"
            className={`${O} w-full`}
          />
          <p className="mt-1 text-meta text-ink-muted">
            Tick <b>Cả nhóm</b> để phòng làm mọi dịch vụ của nhóm. Tick từng dịch vụ để gắn riêng — dịch vụ gắn
            riêng CHỈ làm ở các phòng được gắn.
          </p>
          <ul className="mt-2 max-h-96 space-y-2 overflow-y-auto">
            {nhomHien.map(({ g, ds }) => {
              const moDs = kim !== "" || moNhom === g.node;
              return (
                <li key={g.node} className="rounded-control bg-surface-muted p-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <ChipChon
                      chon={r.serves.includes(g.node)}
                      disabled={dangLam || g.node === r.primary_node}
                      onDoi={() => doiNhom(g.node)}
                    >
                      {g.loai === "KHAM" ? g.ten : `Cả nhóm · ${g.ten}`}
                    </ChipChon>
                    {g.dich_vu.length > 0 && !kim ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-expanded={moDs}
                        onClick={() => setMoNhom(moDs ? null : g.node)}
                      >
                        {moDs ? "Ẩn" : `Từng dịch vụ (${g.dich_vu.length})`}
                      </Button>
                    ) : null}
                  </div>
                  {moDs && ds.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {ds.map((d) => (
                        <ChipChon key={d.ma} chon={daGanLe.has(d.ma)} disabled={dangLam} onDoi={() => doiMot(d.ma)}>
                          <span className="min-w-0">
                            {d.ten}
                            {d.ma_kv ? <span className="text-meta text-ink-muted"> · {d.ma_kv}</span> : null}
                            {d.chi_lam_o.length > 0 ? (
                              <span className="block text-meta text-ink-muted">chỉ làm ở: {d.chi_lam_o.join(", ")}</span>
                            ) : null}
                          </span>
                        </ChipChon>
                      ))}
                    </div>
                  ) : null}
                </li>
              );
            })}
            {nhomHien.length === 0 ? <li className="text-meta text-ink-faint">Không có dịch vụ nào khớp.</li> : null}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
