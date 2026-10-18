"use client";

// Danh sách PHIẾU Kho vật tư (G8a, 14/10/2026): ai lập, lúc nào, lý do, từng dòng.
// Sổ chỉ thêm — KHÔNG có nút sửa / xoá; sai thì [Hoàn tác] = lập phiếu đảo (mỗi
// phiếu đảo được một lần). Phiếu huỷ hay phiếu đảo là việc bình thường → chip
// trung tính, không hộp vàng-đỏ.

import { useRouter } from "next/navigation";
import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import NutHoanTac from "@/components/ui/NutHoanTac";
import { guiVatTu, soVatTu, tienVatTu } from "./gui-vat-tu";
import { KIEU_PHIEU } from "./LapPhieuVatTu";

interface DongPhieu {
  vat_tu_id: string;
  ten: string;
  don_vi: string | null;
  noi_chua: string;
  room_id: string | null;
  so_luong: number;
  thuc_te: number | null;
  gia_nhap: number;
}

export interface PhieuVatTu {
  id: string;
  ma_phieu: string;
  loai: string;
  tao_luc: string;
  ghi_chu: string | null;
  nha_cung_cap: string | null;
  nguoi_tao: string | null;
  nguoi_tao_id: string | null;
  dao_phieu_id: string | null;
  da_dao: boolean;
  dong: DongPhieu[];
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

const tenLoai = (loai: string) => (loai === "HOAN" ? "Đảo thao tác (hoàn tác)" : (KIEU_PHIEU[loai]?.nhan ?? loai));

/** Một dòng sổ: số đếm (kiểm) hoặc số có dấu (+ vào / − ra) tại nơi chứa. */
function chuDong(d: DongPhieu): string {
  const dv = d.don_vi ? ` ${d.don_vi}` : "";
  if (d.thuc_te != null) return `đếm được ${soVatTu(d.thuc_te)}${dv} (sổ ${d.so_luong >= 0 ? "+" : ""}${soVatTu(d.so_luong)})`;
  return `${d.so_luong > 0 ? "+" : ""}${soVatTu(d.so_luong)}${dv}`;
}

function diemPhieu(p: PhieuVatTu): { tu: string[]; den: string[] } {
  const noi = (ds: DongPhieu[]) => [...new Set(ds.map((d) => d.room_id ?? "kho"))];
  const ra = noi(p.dong.filter((d) => d.so_luong < 0));
  const vao = noi(p.dong.filter((d) => d.so_luong > 0));
  const tatCa = noi(p.dong);
  if (p.loai === "NHAP") return { tu: ["ncc"], den: vao };
  if (p.loai === "XUAT_PHONG") return { tu: ["kho"], den: vao.filter((n) => n !== "kho") };
  if (p.loai === "TRA_KHO") return { tu: ra.filter((n) => n !== "kho"), den: ["kho"] };
  if (p.loai === "CHUYEN_PHONG" || p.loai === "HOAN") return { tu: ra, den: vao };
  if (p.loai === "HUY") return { tu: ra, den: ["huy"] };
  if (p.loai === "TRA_NCC") return { tu: ra, den: ["ncc"] };
  return { tu: tatCa, den: tatCa };
}
function huongPhieu(p: PhieuVatTu): string {
  const diem = diemPhieu(p);
  const tenNoi = (ma: string) => ma === "kho" ? "Kho cơ sở" : ma === "ncc" ? "Nhà cung cấp" : ma === "huy" ? "Hỏng / huỷ" : p.dong.find((d) => d.room_id === ma)?.noi_chua ?? "Phòng";
  return `${diem.tu.map(tenNoi).join(", ") || "—"} → ${diem.den.map(tenNoi).join(", ") || "—"}`;
}

export default function DanhSachPhieuVatTu({ ds }: { ds: PhieuVatTu[] }) {
  const router = useRouter();
  const [tatCa, setTatCa] = useState(ds);
  const [nguon, setNguon] = useState(ds);
  const [conTrang, setConTrang] = useState(ds.length >= 50);
  const [dangTai, setDangTai] = useState(false);
  const [loiTai, setLoiTai] = useState<string | null>(null);
  if (nguon !== ds) {
    setNguon(ds);
    setTatCa(ds);
    setConTrang(ds.length >= 50);
  }
  const taiThem = async () => {
    setDangTai(true);
    setLoiTai(null);
    try {
      const res = await fetch(`/api/vat-tu-kho/phieu?gioi_han=50&bo_qua=${tatCa.length}`);
      if (!res.ok) throw new Error("Không tải được lịch sử. Vui lòng thử lại.");
      const data = await res.json() as { items: PhieuVatTu[] };
      if (!Array.isArray(data.items)) throw new Error("Không tải được lịch sử. Vui lòng thử lại.");
      setTatCa((cu) => [...new Map([...cu, ...data.items].map((p) => [p.id, p])).values()]);
      setConTrang(data.items.length >= 50);
    } catch (e) { setLoiTai(e instanceof Error ? e.message : "Không tải được lịch sử."); }
    finally { setDangTai(false); }
  };
  const [mo, setMo] = useState<string | null>(null);
  const [loai, setLoai] = useState("tat_ca");
  const [tuNoi, setTuNoi] = useState("tat_ca");
  const [denNoi, setDenNoi] = useState("tat_ca");
  const [nguoi, setNguoi] = useState("tat_ca");
  const maPhieu = new Map(tatCa.map((p) => [p.id, p.ma_phieu]));
  const cacNoi = [...new Map(tatCa.flatMap((p) => p.dong.filter((d) => d.room_id).map((d) => [d.room_id as string, d.noi_chua] as const))).entries()];
  const nguoiLap = [...new Map(tatCa.filter((p) => p.nguoi_tao_id).map((p) => [p.nguoi_tao_id as string, p.nguoi_tao ?? "Không rõ"] as const)).entries()];
  const hien = tatCa.filter((p) => {
    const diem = diemPhieu(p);
    return (loai === "tat_ca" || p.loai === loai) &&
      (tuNoi === "tat_ca" || diem.tu.includes(tuNoi)) &&
      (denNoi === "tat_ca" || diem.den.includes(denNoi)) &&
      (nguoi === "tat_ca" || p.nguoi_tao_id === nguoi);
  });

  const tuyChonNoi = [
    ["kho", "Kho cơ sở"],
    ["ncc", "Nhà cung cấp"],
    ["huy", "Hỏng / huỷ"],
    ...cacNoi,
  ];

  return (
    <section aria-label="Các lần nhập, cấp và kiểm kê" className="space-y-2">
      <table data-excel-source className="hidden" aria-hidden="true">
        <thead><tr>
          {["Mã phiếu", "Thao tác", "Thời gian", "Người thực hiện", "Nơi chứa", "Vật tư", "Đơn vị", "Số lượng thay đổi", "Số đếm thực tế", "Giá nhập", "Thành tiền có dấu", "Trạng thái", "Nhà sản xuất / nhà cung cấp", "Ghi chú"].map((nhan) => <th key={nhan}>{nhan}</th>)}
        </tr></thead>
        <tbody>{hien.flatMap((p) => p.dong.map((d, i) => (
          <tr key={`${p.id}-${i}`}>
            <td>{p.ma_phieu}</td><td>{tenLoai(p.loai)}</td><td>{gio(p.tao_luc)}</td>
            <td>{p.nguoi_tao ?? ""}</td><td>{d.noi_chua}</td><td>{d.ten}</td><td>{d.don_vi ?? ""}</td>
            <td>{d.so_luong}</td><td>{d.thuc_te ?? ""}</td><td>{d.gia_nhap}</td>
            <td>{Number(d.so_luong) * Number(d.gia_nhap)}</td>
            <td>{p.da_dao ? "Đã hoàn tác" : p.loai === "HOAN" ? "Phiếu đảo" : "Đã ghi nhận"}</td>
            <td>{p.nha_cung_cap ?? ""}</td><td>{p.ghi_chu ?? ""}</td>
          </tr>
        )))}</tbody>
      </table>
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-meta text-ink-soft">
          <span className="mb-1 block">Lọc thao tác</span>
          <select aria-label="Lọc thao tác" className="min-h-10 rounded-control border border-line bg-surface px-3 text-body text-ink" value={loai} onChange={(e) => setLoai(e.target.value)}>
            <option value="tat_ca">Tất cả thao tác</option>
            <option value="NHAP">Nhập hàng</option>
            <option value="XUAT_PHONG">Cấp cho phòng</option>
            <option value="TRA_KHO">Phòng trả về kho</option>
            <option value="CHUYEN_PHONG">Chuyển phòng</option>
            <option value="DIEU_CHINH">Kiểm kê</option>
            <option value="KIEM">Kiểm kê (chỉ lưu số đếm)</option>
            <option value="HUY">Hỏng / huỷ</option>
            <option value="TRA_NCC">Trả nhà sản xuất</option>
            <option value="HOAN">Hoàn tác</option>
          </select>
        </label>
        <label className="text-meta text-ink-soft">
          <span className="mb-1 block">Từ nơi</span>
          <select aria-label="Lọc nơi đi" className="min-h-10 rounded-control border border-line bg-surface px-3 text-body text-ink" value={tuNoi} onChange={(e) => setTuNoi(e.target.value)}>
            <option value="tat_ca">Tất cả nơi đi</option>
            {tuyChonNoi.map(([id, ten]) => <option key={id} value={id}>{ten}</option>)}
          </select>
        </label>
        <label className="text-meta text-ink-soft">
          <span className="mb-1 block">Đến nơi</span>
          <select aria-label="Lọc nơi đến" className="min-h-10 rounded-control border border-line bg-surface px-3 text-body text-ink" value={denNoi} onChange={(e) => setDenNoi(e.target.value)}>
            <option value="tat_ca">Tất cả nơi đến</option>
            {tuyChonNoi.map(([id, ten]) => <option key={id} value={id}>{ten}</option>)}
          </select>
        </label>
        <label className="text-meta text-ink-soft">
          <span className="mb-1 block">Lọc người thực hiện</span>
          <select aria-label="Lọc người thực hiện" className="min-h-10 rounded-control border border-line bg-surface px-3 text-body text-ink" value={nguoi} onChange={(e) => setNguoi(e.target.value)}>
            <option value="tat_ca">Tất cả nhân viên</option>
            {nguoiLap.map(([id, ten]) => <option key={id} value={id}>{ten}</option>)}
          </select>
        </label>
      </div>
      {tatCa.length === 0 ? (
        <p className="rounded-card border border-line bg-surface px-4 py-6 text-center text-body text-ink-muted">
          Chưa ghi nhận thao tác nào.
        </p>
      ) : (
        hien.length === 0 ? (
          <p className="rounded-card border border-line bg-surface px-4 py-6 text-center text-body text-ink-muted">Không có giao dịch khớp bộ lọc.</p>
        ) : <ul className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
          {hien.map((p) => {
            const dangMo = mo === p.id;
            const tong = p.dong.reduce((s, d) => s + Math.abs(Number(d.so_luong)) * Number(d.gia_nhap), 0);
            return (
              <li key={p.id} className="border-b border-hairline px-3 py-2 last:border-b-0">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                  <div className="min-w-0 flex-1 basis-56">
                    <p className="text-emph font-medium text-ink">
                      {p.ma_phieu} <Chip tone="neutral">{tenLoai(p.loai)}</Chip>
                      {p.da_dao ? <Chip tone="neutral" className="ml-1">Đã hoàn tác</Chip> : null}
                    </p>
                    <p className="text-meta text-ink-muted">
                      {gio(p.tao_luc)} · {p.nguoi_tao ?? "—"}
                      {p.dao_phieu_id ? ` · đảo phiếu ${maPhieu.get(p.dao_phieu_id) ?? ""}` : ""}
                      {p.nha_cung_cap ? ` · Nhà sản xuất: ${p.nha_cung_cap}` : ""}
                      {p.ghi_chu ? ` · ${p.ghi_chu}` : ""}
                    </p>
                    <p className="text-meta text-ink-muted">{huongPhieu(p)}</p>
                  </div>
                  <span className="text-meta tabular-nums text-ink-muted">
                    {p.dong.length} dòng
                    {p.loai === "NHAP" || p.loai === "HUY" || p.loai === "TRA_NCC" ? ` · ${tienVatTu(tong)}` : ""}
                  </span>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setMo(dangMo ? null : p.id)}>
                    {dangMo ? "Thu gọn" : "Xem mặt hàng"}
                  </Button>
                  {p.loai !== "HOAN" && !p.da_dao ? (
                    <NutHoanTac
                      tieuDe="Hoàn tác thao tác này?"
                      moTa="Đảo số lượng của phiếu này; các giao dịch sau vẫn được giữ."
                      goi={async () => {
                        const kq = await guiVatTu("hoan", { phieu_id: p.id }, `hoan-${p.id}`);
                        return kq.ok ? { ok: true } : { ok: false, loi: kq.loi };
                      }}
                      onXong={() => router.refresh()}
                    />
                  ) : null}
                </div>
                {dangMo ? (
                  <ul className="mt-2 space-y-1 rounded-control bg-surface-muted px-3 py-2 text-meta text-ink">
                    {p.dong.map((d, i) => (
                      <li key={`${d.vat_tu_id}-${d.noi_chua}-${i}`}>
                        <span className="font-medium">{d.ten}</span> · {d.noi_chua} · {chuDong(d)}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
      <div className="flex flex-wrap items-center gap-2 text-meta text-ink-muted">
        <span>Đang xem {tatCa.length} phiếu gần nhất</span>
        {conTrang ? <Button type="button" size="sm" variant="secondary" disabled={dangTai} onClick={() => void taiThem()}>{dangTai ? "Đang tải…" : "Tải thêm lịch sử"}</Button> : null}
        <span>Bộ lọc áp dụng trong danh sách đã tải.</span>
      </div>
      {loiTai ? <p role="alert" className="text-body text-danger">{loiTai}</p> : null}
    </section>
  );
}
