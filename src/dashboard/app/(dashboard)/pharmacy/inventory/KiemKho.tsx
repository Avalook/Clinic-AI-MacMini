"use client";

// Phiếu kiểm kho (Tuyền 29/09/2026). Chọn lô → cột tồn máy, ô số đếm thực tế;
// cột "lệch" chỉ là số XEM TRƯỚC (thực tế − tồn máy lúc mở màn). [Lưu phiếu
// kiểm] → `POST /api/pharmacy/kiem-kho` → `POST /api/v1/pharmacy/kiem-kho` kèm
// Idempotency-Key: MÁY CHỦ đọc lại tồn máy trong giao dịch, tính lệch, ghi
// điều chỉnh vào sổ kho và lưu phiếu — con số cuối cùng là của máy chủ.

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import { INPUT, TBL_DIV, TBL_HEAD, TBL_WRAP } from "../../form-ui";
import DanhSachPhieu from "./DanhSachPhieu";
import { guiKho, soKho } from "./gui-kho";
import type { InvBatch } from "./InventoryBoard";

const khoaMoi = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `kk-${Date.now()}-${Math.random().toString(36).slice(2)}`;

const tenLo = (b: InvBatch) =>
  `${b.drug?.name_base ?? b.drug?.name_raw ?? "—"}${b.drug?.variant ? ` (${b.drug.variant})` : ""}`;

export default function KiemKho({ batches, ghiDuoc }: { batches: InvBatch[]; ghiDuoc: boolean }) {
  const router = useRouter();
  const [tim, setTim] = useState("");
  const [caLoRong, setCaLoRong] = useState(false);
  // drug_batch_id → số đếm thực tế (chuỗi người gõ).
  const [dem, setDem] = useState<Record<string, string>>({});
  const [ghiChu, setGhiChu] = useState("");
  const [khoa, setKhoa] = useState(khoaMoi);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);
  const [lanTai, setLanTai] = useState(0);

  const hang = useMemo(() => {
    const q = tim.trim().toLowerCase();
    return batches.filter((b) => {
      if (!caLoRong && Number(b.quantity_on_hand) <= 0 && !(b.id in dem)) return false;
      if (!q) return true;
      return tenLo(b).toLowerCase().includes(q) || b.batch_code.toLowerCase().includes(q);
    });
  }, [batches, tim, caLoRong, dem]);

  const daDem = Object.entries(dem).filter(([, v]) => v.trim() !== "");

  const luu = async () => {
    setDang(true);
    setLoi(null);
    setBao(null);
    const kq = await guiKho(
      "kiem-kho",
      {
        ghi_chu: ghiChu.trim() || null,
        dong: daDem.map(([id, v]) => ({ drug_batch_id: id, thuc_te: v.trim() })),
      },
      khoa,
    );
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    const d = kq.data as { ma_phieu?: string; dong?: { lech: number | string }[] } | null;
    const lech = (d?.dong ?? []).filter((x) => Number(x.lech) !== 0).length;
    setBao(
      `Đã lưu phiếu kiểm ${d?.ma_phieu ?? ""}: ${d?.dong?.length ?? daDem.length} lô, ${lech} lô lệch đã điều chỉnh.`,
    );
    setDem({});
    setGhiChu("");
    setKhoa(khoaMoi());
    setLanTai((n) => n + 1);
    router.refresh();
  };

  return (
    <div className="flex flex-col gap-4">
      {ghiDuoc ? (
        <section
          aria-label="Lập phiếu kiểm kho"
          className="space-y-3 rounded-card border border-line bg-surface p-4 shadow-card"
        >
          <h3 className="text-title text-ink">Phiếu kiểm kho</h3>
          <div className="flex flex-wrap items-center gap-2">
            <input
              value={tim}
              onChange={(e) => setTim(e.target.value)}
              placeholder="Tìm thuốc / mã lô…"
              aria-label="Tìm lô để kiểm"
              className={`${INPUT} sm:w-64`}
            />
            <label className="flex min-h-10 items-center gap-2 text-body text-ink">
              <input
                type="checkbox"
                className="size-4 accent-brand-600"
                checked={caLoRong}
                onChange={(e) => setCaLoRong(e.target.checked)}
              />
              Hiện cả lô đã hết
            </label>
          </div>
          <div className={`${TBL_WRAP} overflow-x-auto`}>
            <table className="w-full min-w-2xl text-left text-body">
              <thead className={TBL_HEAD}>
                <tr>
                  <th className="px-3 py-2">Thuốc</th>
                  <th className="px-3 py-2">Lô</th>
                  <th className="px-3 py-2 text-right">Tồn máy</th>
                  <th className="px-3 py-2">Thực tế</th>
                  <th className="px-3 py-2 text-right">Lệch (xem trước)</th>
                </tr>
              </thead>
              <tbody className={TBL_DIV}>
                {hang.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-ink-muted">
                      Không có lô nào.
                    </td>
                  </tr>
                ) : (
                  hang.map((b) => {
                    const v = dem[b.id] ?? "";
                    const so = Number(v.replace(",", "."));
                    const lech = v.trim() !== "" && Number.isFinite(so) ? so - Number(b.quantity_on_hand) : null;
                    return (
                      <tr key={b.id}>
                        <td className="px-3 py-2 font-medium text-ink">{tenLo(b)}</td>
                        <td className="px-3 py-2 text-ink-muted">
                          {b.batch_code}
                          <span className="block text-meta">{b.unit}</span>
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums text-ink">
                          {soKho(b.quantity_on_hand)}
                        </td>
                        <td className="px-3 py-2">
                          <input
                            value={v}
                            inputMode="decimal"
                            aria-label={`Số đếm thực tế ${tenLo(b)} lô ${b.batch_code}`}
                            onChange={(e) => setDem((m) => ({ ...m, [b.id]: e.target.value }))}
                            className={`${INPUT} sm:w-28`}
                          />
                        </td>
                        <td
                          className={`px-3 py-2 text-right font-semibold tabular-nums ${
                            lech == null || lech === 0
                              ? "text-ink-muted"
                              : lech < 0
                                ? "text-danger"
                                : "text-success"
                          }`}
                        >
                          {lech == null ? "—" : `${lech > 0 ? "+" : ""}${soKho(lech)}`}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <input
              value={ghiChu}
              onChange={(e) => setGhiChu(e.target.value)}
              placeholder="Ghi chú (kiểm cuối tháng…)"
              aria-label="Ghi chú phiếu kiểm"
              className={`${INPUT} sm:w-80`}
            />
            <p className="text-meta text-ink-muted sm:ml-auto">Đã đếm {daDem.length} lô</p>
            <Button
              type="button"
              variant="primary"
              disabled={dang || daDem.length === 0}
              onClick={() => void luu()}
            >
              {dang ? "Đang lưu…" : "Lưu phiếu kiểm"}
            </Button>
          </div>
          {loi ? (
            <p role="alert" className="text-meta text-danger">
              {loi}
            </p>
          ) : null}
          {bao ? <p className="text-meta text-success">{bao}</p> : null}
        </section>
      ) : null}

      <DanhSachPhieu loai="KIEM" lanTai={lanTai} />
    </div>
  );
}
