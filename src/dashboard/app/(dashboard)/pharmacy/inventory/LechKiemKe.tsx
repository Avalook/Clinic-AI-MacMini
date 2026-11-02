"use client";

// Khối "Lệch kiểm kê" ở Báo cáo kho (Tuyền 31/10/2026): gom dòng lệch của Kiểm ca và
// Kiểm đếm kho trong khoảng ngày đang xem. Người có quyền báo cáo / quản trị sửa số
// sau cùng tại đây: máy chủ ghi thêm một dòng sổ, phiếu gốc và lịch sử giữ nguyên.
// `thao_tac.sua` do máy chủ quyết, màn không tự suy theo vai.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { INPUT, TBL_DIV, TBL_HEAD, TBL_WRAP } from "../../form-ui";
import { guiKho, soKho } from "./gui-kho";

interface LanSua {
  so_cu: number;
  so_moi: number;
  ly_do: string;
  sua_luc: string;
  nguoi: string | null;
}

interface DongLech {
  nguon: "CA" | "KHO";
  dong_id: string;
  ngay: string;
  ca: string;
  loai: string;
  luc: string;
  ten: string;
  so_lo: string | null;
  noi_chua: "KHO" | "QUAY";
  don_vi: string;
  so_so: number;
  giao_chua_gan_lo: number | null;
  so_dem: number;
  lech: number;
  ly_do: string | null;
  chua_ap: number | null;
  chua_ap_ly_do: string | null;
  so_sau_cung: number;
  nguoi: string | null;
  da_hoan_tac: boolean;
  lich_su_sua: LanSua[];
  thao_tac: { sua: boolean };
}

const NHAN_CA: Record<string, string> = { SANG: "Sáng", CHIEU: "Chiều", TOI: "Tối" };
const NHAN_LOAI: Record<string, string> = {
  DAU: "Đầu ca",
  CUOI: "Cuối ca",
  DOT_XUAT: "Đột xuất",
  KHO: "Kiểm kho",
};

const gio = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

function SuaSo({ d, onXong }: { d: DongLech; onXong: () => void }) {
  const [mo, setMo] = useState(false);
  const [so, setSo] = useState("");
  const [lyDo, setLyDo] = useState("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  const luu = async () => {
    setDang(true);
    setLoi(null);
    const kq = await guiKho("sua-so-kiem-ke", {
      nguon: d.nguon,
      dong_id: d.dong_id,
      so_moi: so.trim(),
      ly_do: lyDo.trim(),
    });
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setMo(false);
    setSo("");
    setLyDo("");
    onXong();
  };

  if (!mo) {
    return (
      <Button type="button" size="sm" variant="ghost" onClick={() => setMo(true)}>
        Sửa số
      </Button>
    );
  }
  return (
    <div className="flex min-w-48 flex-col gap-1">
      <input
        value={so}
        inputMode="decimal"
        aria-label={`Số sau cùng — ${d.ten}`}
        placeholder="Số đúng"
        onChange={(e) => setSo(e.target.value)}
        className={INPUT}
      />
      <input
        value={lyDo}
        maxLength={1000}
        aria-label={`Lý do sửa số — ${d.ten}`}
        placeholder="Lý do sửa"
        onChange={(e) => setLyDo(e.target.value)}
        className={INPUT}
      />
      <div className="flex gap-1">
        <Button
          type="button"
          size="sm"
          variant="primary"
          disabled={dang || !so.trim() || !lyDo.trim()}
          onClick={() => void luu()}
        >
          {dang ? "Đang lưu…" : "Lưu"}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setMo(false)}>
          Thôi
        </Button>
      </div>
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}

export default function LechKiemKe({ tu, den }: { tu: string; den: string }) {
  const [dong, setDong] = useState<DongLech[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [lanTai, setLanTai] = useState(0);

  const doc = useCallback(async () => {
    try {
      const r = await fetch(`/api/pharmacy/lech-kiem-ke?${new URLSearchParams({ tu, den })}`, {
        cache: "no-store",
      });
      const d = (await r.json().catch(() => null)) as { dong?: DongLech[]; error?: string } | null;
      if (!r.ok || !d?.dong) {
        setLoi(d?.error ?? "Không đọc được lệch kiểm kê.");
        return;
      }
      setLoi(null);
      setDong(d.dong);
    } catch {
      setLoi("Mất kết nối — chưa đọc được lệch kiểm kê.");
    }
  }, [tu, den]);

  useEffect(() => {
    let bo = false;
    void Promise.resolve().then(() => {
      if (!bo) void doc();
    });
    return () => {
      bo = true;
    };
  }, [doc, lanTai]);

  const xuatExcel = () => {
    const a = document.createElement("a");
    a.href = `/api/pharmacy/lech-kiem-ke-xlsx?${new URLSearchParams({ tu, den })}`;
    a.click();
  };

  const ds = dong ?? [];

  return (
    <section aria-label="Lệch kiểm kê" className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-title text-ink">Lệch kiểm kê</h3>
        <span className="text-meta text-ink-muted">{ds.length} dòng</span>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          className="sm:ml-auto"
          disabled={ds.length === 0}
          onClick={xuatExcel}
        >
          Xuất Excel lệch
        </Button>
      </div>
      {loi ? (
        <p role="alert" className="text-body text-danger">
          {loi}
        </p>
      ) : null}
      <div className={`${TBL_WRAP} overflow-x-auto`}>
        <table className="w-full min-w-4xl text-left text-body">
          <thead className={TBL_HEAD}>
            <tr>
              <th className="px-3 py-2">Ngày · ca</th>
              <th className="px-3 py-2">Thuốc</th>
              <th className="px-3 py-2">Nơi · lô</th>
              <th className="px-3 py-2 text-right">Số sổ</th>
              <th className="px-3 py-2 text-right">Số đếm</th>
              <th className="px-3 py-2 text-right">Lệch</th>
              <th className="px-3 py-2">Lý do</th>
              <th className="px-3 py-2">Người · lúc</th>
              <th className="px-3 py-2 text-right">Số sau cùng</th>
            </tr>
          </thead>
          <tbody className={TBL_DIV}>
            {dong === null ? (
              <tr>
                <td colSpan={9} className="px-3 py-6 text-center text-ink-muted">
                  Đang đọc…
                </td>
              </tr>
            ) : ds.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-3 py-6 text-center text-ink-muted">
                  Không có dòng lệch trong khoảng này.
                </td>
              </tr>
            ) : (
              ds.map((d) => (
                <tr key={`${d.nguon}-${d.dong_id}`}>
                  <td className="whitespace-nowrap px-3 py-2 text-ink-muted">
                    {String(d.ngay).split("-").reverse().join("/")}
                    <span className="block text-meta">
                      {NHAN_CA[d.ca] ?? d.ca} · {NHAN_LOAI[d.loai] ?? d.loai}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-medium text-ink">
                    {d.ten}
                    <span className="block text-meta font-normal text-ink-muted">{d.don_vi}</span>
                  </td>
                  <td className="px-3 py-2 text-ink-muted">
                    {d.noi_chua === "KHO" ? "Kho" : "Quầy"}
                    {d.so_lo ? <span className="block text-meta">{d.so_lo}</span> : null}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink-muted">
                    {soKho(d.so_so)}
                    {d.giao_chua_gan_lo ? (
                      <span className="block text-meta">chờ gán {soKho(d.giao_chua_gan_lo)}</span>
                    ) : null}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-ink">{soKho(d.so_dem)}</td>
                  <td className="px-3 py-2 text-right font-semibold tabular-nums text-danger">
                    {Number(d.lech) > 0 ? "+" : ""}
                    {soKho(d.lech)}
                  </td>
                  <td className="px-3 py-2 text-ink-muted">
                    {d.ly_do ?? "—"}
                    {d.chua_ap ? (
                      <span className="block text-meta text-danger">
                        Chưa khớp {soKho(d.chua_ap)}: {d.chua_ap_ly_do}
                      </span>
                    ) : null}
                    {d.da_hoan_tac ? <Chip tone="neutral">Đã hoàn tác</Chip> : null}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-ink-muted">
                    {d.nguoi ?? "—"}
                    <span className="block text-meta">{gio(d.luc)}</span>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <span className="tabular-nums font-semibold text-ink">{soKho(d.so_sau_cung)}</span>
                    {d.lich_su_sua.map((s) => (
                      <span key={s.sua_luc} className="block text-meta text-ink-muted">
                        {soKho(s.so_cu)} → {soKho(s.so_moi)}: {s.ly_do}
                        {s.nguoi ? ` — ${s.nguoi}` : ""}
                      </span>
                    ))}
                    {d.thao_tac.sua ? <SuaSo d={d} onXong={() => setLanTai((n) => n + 1)} /> : null}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
