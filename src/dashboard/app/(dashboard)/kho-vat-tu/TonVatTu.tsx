"use client";

// Tab TỒN THEO NƠI CHỨA của Kho vật tư (G8a, 14/10/2026): kho cơ sở + từng phòng.
// Tồn âm và dưới mức tối thiểu là việc BÌNH THƯỜNG của quầy (vật tư vẫn xuất được
// khi sổ hết, rồi kiểm đếm sau) → chữ / chip TRUNG TÍNH, không hộp vàng-đỏ
// (Tuyền 14/10). Máy chủ quyết `canh_bao`; ở đây chỉ vẽ và gửi mức tối thiểu.

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import ChipLoc from "@/components/ui/ChipLoc";
import Chip from "@/components/ui/Chip";
import OChon from "@/components/ui/OChon";
import ONhap from "@/components/ui/ONhap";
import { boDauVatTu } from "@/lib/vat-tu";
import { guiVatTu, soVatTu } from "./gui-vat-tu";

export interface DongTon {
  id: string;
  vat_tu_id: string;
  room_id: string | null;
  ten: string;
  don_vi: string | null;
  noi_chua: string;
  so_luong: number;
  ton_toi_thieu: number;
  /** Chữ máy chủ đặt: "tồn âm — cần kiểm đếm" | "Dưới mức tối thiểu" | "". */
  canh_bao: string;
}

export interface NoiChua {
  room_id: string | null;
  ten: string;
  dang_bat: boolean;
}

const KHO = "kho";

export default function TonVatTu({
  ton,
  noiChua,
  vatTu,
}: {
  ton: DongTon[];
  noiChua: NoiChua[];
  vatTu: { id: string; name: string }[];
}) {
  const router = useRouter();
  const [noi, setNoi] = useState<string>("tat_ca");
  const [chiCanChuY, setChiCanChuY] = useState(false);
  const [tim, setTim] = useState("");
  const [nhap, setNhap] = useState<Record<string, string>>({});
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);
  const [them, setThem] = useState({ ten: "", noi: KHO, muc: "" });

  const canChuY = ton.filter((t) => t.canh_bao).length;
  const hien = useMemo(() => {
    const khoa = boDauVatTu(tim.trim());
    return ton.filter((t) => {
      if (noi !== "tat_ca" && (t.room_id ?? KHO) !== noi) return false;
      if (chiCanChuY && !t.canh_bao) return false;
      return !khoa || boDauVatTu(t.ten).includes(khoa);
    });
  }, [ton, noi, chiCanChuY, tim]);

  async function luuMuc(vatTuId: string, roomId: string | null, muc: string, xong: string) {
    setDang(true);
    setLoi(null);
    setBao(null);
    const kq = await guiVatTu("muc-toi-thieu", { vat_tu_id: vatTuId, room_id: roomId, muc: muc.trim().replace(",", ".") });
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return false;
    }
    setBao(xong);
    router.refresh();
    return true;
  }

  const themMuc = async () => {
    const vt = vatTu.find((v) => v.name === them.ten);
    if (!vt) {
      setLoi("Chọn vật tư có trong danh mục (gõ rồi chọn trong danh sách).");
      return;
    }
    const ok = await luuMuc(
      vt.id,
      them.noi === KHO ? null : them.noi,
      them.muc,
      `Đã đặt mức tối thiểu “${vt.name}”.`,
    );
    if (ok) setThem({ ten: "", noi: KHO, muc: "" });
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <ChipLoc
          nhan="Nơi chứa"
          chon={noi}
          onChon={setNoi}
          muc={[
            { ma: "tat_ca", nhan: "Tất cả nơi" },
            ...noiChua.map((n) => ({
              ma: n.room_id ?? KHO,
              nhan: n.dang_bat ? n.ten : `${n.ten} (đã tắt)`,
            })),
          ]}
        />
        <ONhap
          type="search"
          aria-label="Tìm vật tư"
          placeholder="Tìm vật tư — gõ không dấu cũng được"
          value={tim}
          onChange={(e) => setTim(e.target.value)}
          className="w-full sm:ml-auto sm:w-64"
        />
      </div>
      <ChipLoc
        nhan="Lọc theo tình trạng"
        chon={chiCanChuY ? "can" : "tat_ca"}
        onChon={(v) => setChiCanChuY(v === "can")}
        muc={[
          { ma: "tat_ca", nhan: `Tất cả (${ton.length})` },
          { ma: "can", nhan: `Dưới mức / cần kiểm đếm (${canChuY})` },
        ]}
      />

      {hien.length === 0 ? (
        <p className="rounded-card border border-line bg-surface px-4 py-6 text-center text-body text-ink-muted">
          {ton.length === 0
            ? "Chưa có tồn nào — lập phiếu Nhập kho hoặc Kiểm đếm ở tab Phiếu, hoặc đặt mức tối thiểu bên dưới."
            : "Không có dòng phù hợp."}
        </p>
      ) : (
        <ul className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
          {hien.map((t) => {
            const doi = nhap[t.id] !== undefined;
            return (
              <li
                key={t.id}
                className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-hairline px-3 py-2 last:border-b-0"
              >
                <div className="min-w-0 flex-1 basis-48">
                  <p className="text-emph font-medium text-ink">{t.ten}</p>
                  <p className="text-meta text-ink-muted">
                    {t.noi_chua}
                    {t.don_vi ? ` · ${t.don_vi}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-emph font-semibold tabular-nums text-ink">{soVatTu(t.so_luong)}</span>
                  {t.canh_bao ? (
                    <Chip tone="neutral">{t.canh_bao.charAt(0).toUpperCase() + t.canh_bao.slice(1)}</Chip>
                  ) : null}
                </div>
                <label className="flex items-center gap-1.5 text-meta text-ink-muted">
                  <span>Mức tối thiểu</span>
                  <ONhap
                    inputMode="decimal"
                    aria-label={`Mức tối thiểu ${t.ten} ở ${t.noi_chua}`}
                    value={doi ? nhap[t.id] : String(t.ton_toi_thieu)}
                    onChange={(e) => setNhap((c) => ({ ...c, [t.id]: e.target.value }))}
                    className="w-24 text-right tabular-nums"
                  />
                </label>
                {doi ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="primary"
                    disabled={dang}
                    onClick={async () => {
                      const ok = await luuMuc(t.vat_tu_id, t.room_id, nhap[t.id], `Đã lưu mức tối thiểu “${t.ten}”.`);
                      if (ok) setNhap((c) => Object.fromEntries(Object.entries(c).filter(([k]) => k !== t.id)));
                    }}
                  >
                    Lưu
                  </Button>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}

      <section aria-label="Đặt mức tối thiểu" className="space-y-2 rounded-card border border-line bg-surface p-4 shadow-card">
        <h3 className="text-title text-ink">Đặt mức tối thiểu cho vật tư chưa có trong bảng</h3>
        <datalist id="vat-tu-chon">
          {vatTu.map((v) => (
            <option key={v.id} value={v.name} />
          ))}
        </datalist>
        <div className="flex flex-wrap items-end gap-2">
          <label className="block min-w-0 flex-1 basis-48">
            <span className="mb-1 block text-meta text-ink-soft">Vật tư</span>
            <ONhap
              list="vat-tu-chon"
              value={them.ten}
              placeholder="Gõ tên vật tư…"
              onChange={(e) => setThem({ ...them, ten: e.target.value })}
              className="w-full"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-meta text-ink-soft">Nơi chứa</span>
            <OChon value={them.noi} onChange={(e) => setThem({ ...them, noi: e.target.value })}>
              {noiChua.map((n) => (
                <option key={n.room_id ?? KHO} value={n.room_id ?? KHO}>
                  {n.ten}
                </option>
              ))}
            </OChon>
          </label>
          <label className="block">
            <span className="mb-1 block text-meta text-ink-soft">Mức tối thiểu</span>
            <ONhap
              inputMode="decimal"
              value={them.muc}
              onChange={(e) => setThem({ ...them, muc: e.target.value })}
              className="w-28 text-right tabular-nums"
            />
          </label>
          <Button type="button" variant="primary" disabled={dang || !them.ten || !them.muc.trim()} onClick={() => void themMuc()}>
            Đặt mức
          </Button>
        </div>
      </section>

      {loi ? (
        <p role="alert" className="text-body text-danger">
          {loi}
        </p>
      ) : null}
      {bao ? (
        <p role="status" className="text-body text-success">
          {bao}
        </p>
      ) : null}
    </div>
  );
}
