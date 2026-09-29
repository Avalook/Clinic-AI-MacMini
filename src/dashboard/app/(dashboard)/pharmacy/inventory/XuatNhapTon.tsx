"use client";

// Xuất – nhập – tồn theo khoảng ngày (Tuyền 29/09/2026, kiểu KiotViet).
// `GET /api/pharmacy/xuat-nhap-ton?tu=&den=` → `GET /api/v1/pharmacy/xuat-nhap-ton`.
// Máy chủ tính tồn đầu / cuối, giá trị tồn (theo giá nhập của lô) và đọc lại
// khoảng ngày (rác → hôm nay). Ở đây chỉ vẽ + xuất CSV đúng các con số đã nhận.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import ThanhNgay from "@/components/ui/ThanhNgay";
import { congNgay, ngayNgan, type Khoang } from "@/lib/thanh-ngay";
import { homNayVn } from "@/lib/validation";
import { TBL_DIV, TBL_HEAD, TBL_WRAP } from "../../form-ui";
import { soKho, tienVnd } from "./gui-kho";

interface DongXnt {
  drug_catalog_id: string;
  ten: string;
  ma_hang: string | null;
  don_vi_ban: string | null;
  ton_dau: number;
  nhap: number;
  xuat: number;
  dieu_chinh: number;
  huy: number;
  tra_lai: number;
  ton_cuoi: number;
  gia_tri_ton: number | null;
}

interface KetQua {
  tu: string;
  den: string;
  dong: DongXnt[];
}

const COT: { ma: keyof DongXnt; nhan: string }[] = [
  { ma: "ton_dau", nhan: "Tồn đầu" },
  { ma: "nhap", nhan: "Nhập" },
  { ma: "xuat", nhan: "Xuất bán" },
  { ma: "dieu_chinh", nhan: "Điều chỉnh" },
  { ma: "huy", nhan: "Huỷ" },
  { ma: "tra_lai", nhan: "Khách trả" },
  { ma: "ton_cuoi", nhan: "Tồn cuối" },
];

function oCsv(v: unknown): string {
  const s = v == null ? "" : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export default function XuatNhapTon({ onXemThe }: { onXemThe: (id: string) => void }) {
  const [homNay] = useState(homNayVn);
  const [khoang, setKhoang] = useState<Khoang | null>(() => ({
    tu: congNgay(homNayVn(), -29),
    den: homNayVn(),
  }));
  // "Tất cả" = một năm gần nhất (máy chủ cắt khoảng dài hơn 366 ngày).
  const k = khoang ?? { tu: congNgay(homNay, -365), den: homNay };
  const hoi = `${k.tu}|${k.den}`;
  // Kết quả gắn với khoảng đã hỏi — đang tải = kết quả chưa phải của `hoi`
  // (không setState đồng bộ trong effect).
  const [tra, setTra] = useState<{ hoi: string; kq: KetQua | null; loi: string | null } | null>(
    null,
  );
  const dangTai = tra?.hoi !== hoi;
  const kq = tra?.kq ?? null;
  const loi = tra?.hoi === hoi ? tra.loi : null;

  useEffect(() => {
    const [tu, den] = hoi.split("|");
    let bo = false;
    fetch(
      `/api/pharmacy/xuat-nhap-ton?${new URLSearchParams({ tu, den })}`,
      { cache: "no-store" },
    )
      .then(async (r) => {
        const d = (await r.json().catch(() => null)) as (KetQua & { error?: string }) | null;
        if (bo) return;
        if (!r.ok || !d)
          setTra((cu) => ({
            hoi,
            kq: cu?.kq ?? null,
            loi: d?.error ?? "Không đọc được xuất – nhập – tồn.",
          }));
        else setTra({ hoi, kq: d, loi: null });
      })
      .catch(() => {
        if (!bo)
          setTra((cu) => ({
            hoi,
            kq: cu?.kq ?? null,
            loi: "Mất kết nối — chưa đọc được xuất – nhập – tồn.",
          }));
      });
    return () => {
      bo = true;
    };
  }, [hoi]);

  const dong = kq?.dong ?? [];
  const coGiaTri = dong.some((d) => d.gia_tri_ton != null);
  const coTraLai = dong.some((d) => Number(d.tra_lai) !== 0);
  const cot = COT.filter((c) => c.ma !== "tra_lai" || coTraLai);

  const xuatCsv = () => {
    if (!kq) return;
    const dau = ["Mã hàng", "Tên thuốc", "Đơn vị", ...cot.map((c) => c.nhan)];
    if (coGiaTri) dau.push("Giá trị tồn");
    const hang = kq.dong.map((d) => {
      const o: unknown[] = [d.ma_hang ?? "", d.ten, d.don_vi_ban ?? ""];
      for (const c of cot) o.push(Number(d[c.ma]));
      if (coGiaTri) o.push(d.gia_tri_ton == null ? "" : Number(d.gia_tri_ton));
      return o.map(oCsv).join(",");
    });
    // BOM UTF-8 để Excel đọc đúng tiếng Việt.
    const noiDung = `﻿${[dau.map(oCsv).join(","), ...hang].join("\r\n")}`;
    const url = URL.createObjectURL(new Blob([noiDung], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `xuat-nhap-ton_${kq.tu}_${kq.den}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col gap-3">
      <ThanhNgay
        nhan="Khoảng ngày xuất – nhập – tồn"
        khoang={khoang}
        homNay={homNay}
        soNgaySau={0}
        dangTai={dangTai}
        onChon={setKhoang}
      />
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-body text-ink-muted">
          {kq ? `Từ ${ngayNgan(kq.tu)} đến ${ngayNgan(kq.den)} · ${dong.length} thuốc` : ""}
        </p>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          className="sm:ml-auto"
          disabled={!kq || dangTai || dong.length === 0}
          onClick={xuatCsv}
        >
          Xuất Excel
        </Button>
      </div>
      {loi ? (
        <p role="alert" className="text-body text-danger">
          {loi}
        </p>
      ) : null}
      <div className={`${TBL_WRAP} overflow-x-auto`}>
        <table className="w-full min-w-3xl text-left text-body">
          <thead className={TBL_HEAD}>
            <tr>
              <th className="px-3 py-2">Thuốc</th>
              {cot.map((c) => (
                <th key={c.ma} className="px-3 py-2 text-right">
                  {c.nhan}
                </th>
              ))}
              {coGiaTri ? <th className="px-3 py-2 text-right">Giá trị tồn</th> : null}
            </tr>
          </thead>
          <tbody className={TBL_DIV}>
            {dong.length === 0 ? (
              <tr>
                <td colSpan={cot.length + 2} className="px-3 py-6 text-center text-ink-muted">
                  {dangTai ? "Đang tính…" : "Không có thuốc nào."}
                </td>
              </tr>
            ) : (
              dong.map((d) => (
                <tr key={d.drug_catalog_id}>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      onClick={() => onXemThe(d.drug_catalog_id)}
                      className="text-left font-medium text-brand-700 hover:underline"
                    >
                      {d.ten}
                    </button>
                    <span className="block text-meta text-ink-muted">
                      {[d.ma_hang, d.don_vi_ban].filter(Boolean).join(" · ")}
                    </span>
                  </td>
                  {cot.map((c) => (
                    <td
                      key={c.ma}
                      className={`px-3 py-2 text-right tabular-nums ${
                        c.ma === "ton_cuoi" ? "font-semibold text-ink" : "text-ink-muted"
                      }`}
                    >
                      {soKho(d[c.ma] as number)}
                    </td>
                  ))}
                  {coGiaTri ? (
                    <td className="px-3 py-2 text-right tabular-nums text-ink">
                      {d.gia_tri_ton == null ? "—" : tienVnd(Number(d.gia_tri_ton))}
                    </td>
                  ) : null}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
