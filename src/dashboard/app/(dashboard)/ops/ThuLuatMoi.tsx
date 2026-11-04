"use client";

// Tab "Thử luật mới" (Tuyền 04/11/2026): chạy bóng luật "đứng đâu làm việc đó".
//
// Hệ thống CHƯA chặn ai. Mỗi lệnh ghi qua cổng quyền được máy chủ ghi một dòng:
// nếu bật luật mới thì lệnh ấy có còn làm được không, vì sao
// (`permissions/chay_bong.py`). Màn chỉ vẽ con số máy chủ đã gom
// (`services/chay_bong_doc.py`): theo người / việc / phòng, số "sẽ bị chặn".

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import XuatBangTrongVung from "@/components/ui/XuatBangTrongVung";
import { fmtDateTime } from "@/lib/datetime";

type Theo = "nguoi" | "viec" | "phong";
interface DuLieu {
  tu: string;
  den: string;
  theo: Theo;
  ly_do_ten: Record<string, string>;
  tong: { so_lenh?: number; so_chan?: number; so_nguoi?: number; so_nguoi_bi_chan?: number };
  dong: { khoa: string | null; ten: string; so_lenh: number; so_chan: number; so_nguoi: number; ly_do: string[] }[];
  gan_day: { luc: string; nguoi: string; viec: string; phong: string | null; ly_do: string }[];
}

const O = "min-h-10 rounded-control border border-line bg-surface px-3 text-body text-ink";
const THEO: { ma: Theo; ten: string }[] = [
  { ma: "nguoi", ten: "Theo người" },
  { ma: "viec", ten: "Theo việc" },
  { ma: "phong", ten: "Theo phòng" },
];

function homNay(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

const so = (n: number | undefined) => (n ?? 0).toLocaleString("vi-VN");

export default function ThuLuatMoi() {
  const [tu, setTu] = useState(homNay());
  const [den, setDen] = useState(homNay());
  const [theo, setTheo] = useState<Theo>("nguoi");
  const [dl, setDl] = useState<DuLieu | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  useEffect(() => {
    let huy = false;
    const q = new URLSearchParams({ xem: "chay-bong", tu, den, theo });
    void fetch(`/api/ops/theo-doi?${q.toString()}`, { cache: "no-store" })
      .then(async (r) => {
        if (huy) return;
        if (!r.ok) {
          setLoi("Không đọc được sổ thử luật.");
          return;
        }
        setLoi(null);
        setDl((await r.json()) as DuLieu);
      })
      .catch(() => !huy && setLoi("Mất kết nối."));
    return () => {
      huy = true;
    };
  }, [tu, den, theo]);

  const tenLyDo = (ma: string) => dl?.ly_do_ten[ma] ?? ma;

  return (
    <div className="space-y-4 p-4 lg:p-5">
      <div className="space-y-1">
        <h2 className="text-title font-semibold text-ink">Thử luật “đứng đâu làm việc đó”</h2>
        <p className="text-meta text-ink-muted">
          Chưa chặn ai. Mỗi lần nhân viên bấm một việc, hệ thống ghi lại: nếu chỉ cho làm việc tại chỗ ở
          phòng mình được xếp lịch hôm đó, thì lần bấm ấy có bị chặn không. Chức năng của từng phòng sửa ở
          Cấu trúc phòng khám.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1 text-meta text-ink-muted">
          Từ
          <input type="date" value={tu} onChange={(e) => e.target.value && setTu(e.target.value)} className={O} />
        </label>
        <label className="flex items-center gap-1 text-meta text-ink-muted">
          đến
          <input type="date" value={den} onChange={(e) => e.target.value && setDen(e.target.value)} className={O} />
        </label>
        {THEO.map((t) => (
          <Button
            key={t.ma}
            type="button"
            size="sm"
            variant={theo === t.ma ? "primary" : "ghost"}
            onClick={() => setTheo(t.ma)}
          >
            {t.ten}
          </Button>
        ))}
      </div>

      {loi ? <p className="text-body text-danger">{loi}</p> : null}

      {dl ? (
        <>
          <p className="text-body text-ink">
            {so(dl.tong.so_lenh)} lần bấm của {so(dl.tong.so_nguoi)} người ·{" "}
            <span className="font-semibold">{so(dl.tong.so_chan)} lần sẽ bị chặn</span> (
            {so(dl.tong.so_nguoi_bi_chan)} người)
          </p>
          <XuatBangTrongVung tenTep={`thu-luat-${dl.theo}-${dl.tu}-${dl.den}`}>
            <div className="overflow-x-auto rounded-card border border-hairline bg-surface">
              <table className="w-full text-body">
                <thead className="bg-surface-muted text-meta text-ink-muted">
                  <tr>
                    <th scope="col" className="px-3 py-2 text-left">
                      {THEO.find((t) => t.ma === dl.theo)?.ten.replace("Theo ", "")}
                    </th>
                    <th scope="col" className="px-3 py-2 text-right">Lần bấm</th>
                    <th scope="col" className="px-3 py-2 text-right">Sẽ bị chặn</th>
                    <th scope="col" className="px-3 py-2 text-right">Số người</th>
                    <th scope="col" className="px-3 py-2 text-left">Vì sao bị chặn</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-hairline">
                  {dl.dong.length === 0 ? (
                    <tr>
                      <td className="px-3 py-3 text-ink-muted" colSpan={5}>
                        Chưa có lần bấm nào trong khoảng ngày này.
                      </td>
                    </tr>
                  ) : (
                    dl.dong.map((d) => (
                      <tr key={d.khoa ?? "khong"}>
                        <td className="px-3 py-1.5">{d.ten}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{so(d.so_lenh)}</td>
                        <td
                          className={`px-3 py-1.5 text-right tabular-nums ${d.so_chan > 0 ? "font-semibold text-warning" : ""}`}
                        >
                          {so(d.so_chan)}
                        </td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{so(d.so_nguoi)}</td>
                        <td className="px-3 py-1.5 text-meta text-ink-muted">
                          {d.ly_do.map(tenLyDo).join(" · ")}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </XuatBangTrongVung>

          {dl.gan_day.length > 0 ? (
            <div className="space-y-2">
              <h3 className="text-body font-semibold text-ink">Lần bấm sẽ bị chặn gần nhất</h3>
              <ul className="divide-y divide-hairline rounded-card border border-hairline bg-surface">
                {dl.gan_day.map((g, i) => (
                  <li key={`${g.luc}-${i}`} className="flex flex-wrap gap-x-3 px-3 py-1.5 text-body">
                    <span className="tabular-nums text-ink-muted">{fmtDateTime(g.luc)}</span>
                    <span className="font-medium text-ink">{g.nguoi}</span>
                    <span className="text-ink">{g.viec}</span>
                    <span className="text-meta text-ink-muted">
                      {tenLyDo(g.ly_do)}
                      {g.phong ? ` (đang đứng: ${g.phong})` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      ) : !loi ? (
        <p className="text-meta text-ink-muted">Đang tải…</p>
      ) : null}
    </div>
  );
}
