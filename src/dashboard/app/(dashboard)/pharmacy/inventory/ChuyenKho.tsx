"use client";

// Chuyển kho ↔ quầy (G7, 14/10/2026). Khi cơ sở bật tách kho / quầy: nhập đi vào
// KHO, bán / giao chỉ lấy ở QUẦY; màn này lập phiếu chuyển (hai chiều) và hoàn
// tác phiếu cũ. Công tắc tách nằm ở đây cho người có `config.clinic.manage`.
// Mọi luật (quá tồn → 409, lô hết hạn không ra quầy, số rác → 422, hoàn tác mỗi
// phiếu một lần) ở máy chủ — màn chỉ gửi lệnh và hiện câu trả lời nguyên văn.

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { INPUT, TBL_DIV, TBL_HEAD, TBL_WRAP } from "../../form-ui";
import type { InvBatch } from "./InventoryBoard";
import { guiKho, soKho } from "./gui-kho";

type Huong = "KHO_QUAY" | "QUAY_KHO";

const NHAN_HUONG: Record<Huong, string> = {
  KHO_QUAY: "Kho → Quầy",
  QUAY_KHO: "Quầy → Kho",
};

interface DongChuyen {
  stt: number;
  ten: string;
  so_lo: string;
  don_vi: string | null;
  so_luong: number | null;
  noi_chua: "KHO" | "QUAY";
}

interface PhieuChuyen {
  id: string;
  ma_phieu: string;
  huong: Huong | null;
  ly_do: string | null;
  tao_luc: string;
  nguoi_tao: string | null;
  hoan_tac_cua: string | null;
  da_hoan_tac: boolean;
  dong: DongChuyen[];
}

const gio = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

export default function ChuyenKho({
  batches,
  tachKhoQuay,
  suaTachDuoc = false,
  ghiDuoc = false,
}: {
  batches: InvBatch[];
  /** Cơ sở này đang bật tách kho / quầy (máy chủ trả). */
  tachKhoQuay: boolean;
  /** Có quyền bật / tắt tách (`config.clinic.manage`) — máy chủ vẫn kiểm. */
  suaTachDuoc?: boolean;
  /** Có quyền ghi kho — chỉ ẩn / hiện nút. */
  ghiDuoc?: boolean;
}) {
  const router = useRouter();
  const [huong, setHuong] = useState<Huong>("KHO_QUAY");
  const [so, setSo] = useState<Record<string, string>>({});
  const [lyDo, setLyDo] = useState("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [lanTai, setLanTai] = useState(0);
  const [ds, setDs] = useState<PhieuChuyen[] | null>(null);
  const [mo, setMo] = useState<string | null>(null);
  // Một khoá cho một lần lập phiếu: bấm đúp / gửi lại sau mất mạng = cùng phiếu.
  const khoa = useRef(crypto.randomUUID());

  useEffect(() => {
    if (!tachKhoQuay) return;
    let bo = false;
    fetch("/api/pharmacy/phieu-kho?loai=CHUYEN", { cache: "no-store" })
      .then(async (r) => {
        const d = (await r.json().catch(() => null)) as { items?: PhieuChuyen[]; error?: string } | null;
        if (bo) return;
        if (!r.ok || !d?.items) setLoi(d?.error ?? "Không đọc được danh sách phiếu chuyển.");
        else setDs(d.items);
      })
      .catch(() => {
        if (!bo) setLoi("Mất kết nối — chưa đọc được danh sách phiếu chuyển.");
      });
    return () => {
      bo = true;
    };
  }, [tachKhoQuay, lanTai]);

  const nguon = huong === "KHO_QUAY" ? "KHO" : "QUAY";
  const loNguon = batches.filter((b) => b.noi_chua === nguon && b.quantity_on_hand > 0);
  const dongGui = loNguon
    .filter((b) => (so[b.id] ?? "").trim() !== "")
    .map((b) => ({ drug_batch_id: b.id, so_luong: so[b.id].trim() }));

  const doiTach = async (bat: boolean) => {
    setDang(true);
    setLoi(null);
    const kq = await guiKho("tach-kho-quay", { bat });
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    router.refresh();
  };

  const lapPhieu = async () => {
    setDang(true);
    setLoi(null);
    const kq = await guiKho(
      "chuyen-kho",
      { huong, ly_do: lyDo.trim() || null, dong: dongGui },
      khoa.current,
    );
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    khoa.current = crypto.randomUUID();
    setSo({});
    setLyDo("");
    setLanTai((n) => n + 1);
    router.refresh();
  };

  const hoanTac = async (phieuId: string) => {
    setDang(true);
    setLoi(null);
    const kq = await guiKho("hoan-tac-chuyen-kho", { phieu_id: phieuId }, crypto.randomUUID());
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setLanTai((n) => n + 1);
    router.refresh();
  };

  return (
    <div className="flex flex-col gap-4">
      <section
        aria-label="Tách kho và quầy"
        className="flex flex-wrap items-center gap-3 rounded-card border border-line bg-surface p-3"
      >
        <Chip tone={tachKhoQuay ? "success" : "neutral"}>
          {tachKhoQuay ? "Đang tách kho / quầy" : "Chưa tách (một kho như cũ)"}
        </Chip>
        <p className="min-w-0 flex-1 text-meta text-ink-muted">
          {tachKhoQuay
            ? "Nhập thuốc đi vào KHO; quầy chỉ bán và giao thuốc đã chuyển sang QUẦY. Tắt tách chỉ được khi kho đã hết hàng."
            : "Bật để tách: hàng đang có giữ nguyên ở QUẦY, kho bắt đầu từ 0; từ đó hàng nhập đi vào kho rồi chuyển ra quầy."}
        </p>
        {suaTachDuoc ? (
          <Button
            type="button"
            size="sm"
            variant={tachKhoQuay ? "secondary" : "primary"}
            disabled={dang}
            onClick={() => void doiTach(!tachKhoQuay)}
          >
            {tachKhoQuay ? "Tắt tách kho / quầy" : "Bật tách kho / quầy"}
          </Button>
        ) : null}
      </section>
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}

      {tachKhoQuay ? (
        <>
          {ghiDuoc ? (
            <section aria-label="Lập phiếu chuyển" className="space-y-3 rounded-card border border-line bg-surface p-3">
              <div className="flex flex-wrap items-end gap-2">
                <label className="block">
                  <span className="mb-1 block text-meta text-ink-soft">Chiều chuyển</span>
                  <select
                    value={huong}
                    onChange={(e) => {
                      setHuong(e.target.value as Huong);
                      setSo({});
                    }}
                    className={INPUT}
                  >
                    <option value="KHO_QUAY">{NHAN_HUONG.KHO_QUAY}</option>
                    <option value="QUAY_KHO">{NHAN_HUONG.QUAY_KHO}</option>
                  </select>
                </label>
                <label className="block min-w-0 flex-1">
                  <span className="mb-1 block text-meta text-ink-soft">Lý do (không bắt buộc)</span>
                  <input
                    value={lyDo}
                    onChange={(e) => setLyDo(e.target.value)}
                    placeholder="Bổ sung quầy đầu ngày…"
                    className={INPUT}
                  />
                </label>
                <Button
                  type="button"
                  variant="primary"
                  disabled={dang || dongGui.length === 0}
                  onClick={() => void lapPhieu()}
                >
                  {dang ? "Đang lưu…" : `Tạo phiếu chuyển (${dongGui.length} dòng)`}
                </Button>
              </div>
              <div className={`${TBL_WRAP} overflow-x-auto`}>
                <table className="w-full min-w-xl text-left text-body">
                  <thead className={TBL_HEAD}>
                    <tr>
                      <th className="px-3 py-2">Thuốc</th>
                      <th className="px-3 py-2">Mã lô</th>
                      <th className="px-3 py-2 text-right">Tồn ở {nguon === "KHO" ? "kho" : "quầy"}</th>
                      <th className="px-3 py-2">Chuyển</th>
                    </tr>
                  </thead>
                  <tbody className={TBL_DIV}>
                    {loNguon.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="px-3 py-6 text-center text-ink-muted">
                          {nguon === "KHO" ? "Kho đang trống." : "Quầy đang trống."}
                        </td>
                      </tr>
                    ) : (
                      loNguon.map((b) => (
                        <tr key={b.id}>
                          <td className="px-3 py-2 font-medium text-ink">
                            {b.drug?.name_base ?? b.drug?.name_raw ?? "—"}
                            {b.drug?.variant ? ` (${b.drug.variant})` : ""}
                          </td>
                          <td className="px-3 py-2 text-ink-muted">{b.batch_code}</td>
                          <td className="px-3 py-2 text-right tabular-nums text-ink">
                            {soKho(b.quantity_on_hand)} {b.unit}
                          </td>
                          <td className="px-3 py-2">
                            <input
                              value={so[b.id] ?? ""}
                              inputMode="decimal"
                              aria-label={`Số chuyển — ${b.batch_code}`}
                              onChange={(e) => setSo({ ...so, [b.id]: e.target.value })}
                              className={`${INPUT} w-28`}
                            />
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}

          <section aria-label="Phiếu chuyển đã lưu" className="space-y-2">
            <h3 className="text-title text-ink">Phiếu chuyển đã lưu</h3>
            <div className={`${TBL_WRAP} overflow-x-auto`}>
              <table className="w-full min-w-2xl text-left text-body">
                <thead className={TBL_HEAD}>
                  <tr>
                    <th className="px-3 py-2">Mã phiếu</th>
                    <th className="px-3 py-2">Lúc</th>
                    <th className="px-3 py-2">Chiều</th>
                    <th className="px-3 py-2">Lý do</th>
                    <th className="px-3 py-2">Người lập</th>
                    <th className="px-3 py-2" />
                  </tr>
                </thead>
                <tbody className={TBL_DIV}>
                  {ds === null ? (
                    <tr>
                      <td colSpan={6} className="px-3 py-6 text-center text-ink-muted">
                        Đang đọc…
                      </td>
                    </tr>
                  ) : ds.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-3 py-6 text-center text-ink-muted">
                        Chưa có phiếu chuyển nào.
                      </td>
                    </tr>
                  ) : (
                    ds.flatMap((p) => {
                      const hang = (
                        <tr key={p.id}>
                          <td className="px-3 py-2 font-medium text-ink">
                            {p.ma_phieu}
                            {p.hoan_tac_cua ? <Chip tone="warning">Phiếu hoàn tác</Chip> : null}
                            {p.da_hoan_tac ? <Chip tone="neutral">Đã hoàn tác</Chip> : null}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2 text-ink-muted">{gio(p.tao_luc)}</td>
                          <td className="px-3 py-2 text-ink-muted">{p.huong ? NHAN_HUONG[p.huong] : "—"}</td>
                          <td className="px-3 py-2 text-ink-muted">{p.ly_do ?? "—"}</td>
                          <td className="px-3 py-2 text-ink-muted">{p.nguoi_tao ?? "—"}</td>
                          <td className="whitespace-nowrap px-3 py-2 text-right">
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => setMo(mo === p.id ? null : p.id)}
                            >
                              {mo === p.id ? "Thu gọn" : "Xem dòng"}
                            </Button>
                            {ghiDuoc && !p.da_hoan_tac && !p.hoan_tac_cua ? (
                              <Button
                                type="button"
                                size="sm"
                                variant="ghost"
                                disabled={dang}
                                onClick={() => void hoanTac(p.id)}
                              >
                                Hoàn tác
                              </Button>
                            ) : null}
                          </td>
                        </tr>
                      );
                      if (mo !== p.id) return [hang];
                      return [
                        hang,
                        <tr key={`${p.id}-dong`} className="bg-surface-muted">
                          <td colSpan={6} className="px-3 py-3">
                            <ul className="space-y-1 text-meta text-ink">
                              {p.dong.map((d) => (
                                <li key={d.stt}>
                                  {d.stt}. <span className="font-medium">{d.ten}</span> · lô {d.so_lo} ·{" "}
                                  {soKho(d.so_luong)} {d.don_vi ?? ""} → {d.noi_chua === "KHO" ? "kho" : "quầy"}
                                </li>
                              ))}
                            </ul>
                          </td>
                        </tr>,
                      ];
                    })
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
