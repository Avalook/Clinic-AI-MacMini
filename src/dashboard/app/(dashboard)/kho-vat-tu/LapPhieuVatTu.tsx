"use client";

// Lập PHIẾU Kho vật tư (G8a, 14/10/2026): Nhập kho · Xuất kho → phòng · Phòng trả
// kho · Chuyển phòng → phòng · Kiểm đếm · Huỷ hỏng. Màn chỉ gom ô nhập (ô nào hiện
// theo loại phiếu) và gửi; số rác → 422 có lời do MÁY CHỦ trả, vật tư hết trên sổ
// vẫn xuất được (tồn âm = việc bình thường, kiểm đếm sau). Idempotency-Key: bấm
// hai lần / mạng chập = MỘT phiếu.

import { useRouter } from "next/navigation";
import { useState } from "react";

import Button from "@/components/ui/Button";
import OChon from "@/components/ui/OChon";
import ONhap from "@/components/ui/ONhap";
import { guiVatTu, khoaMoi } from "./gui-vat-tu";
import type { NoiChua } from "./TonVatTu";

type Cho = null | "noi" | "phong";

interface Kieu {
  nhan: string;
  /** Ô "từ" / "đến": không có · nơi bất kỳ (kho hoặc phòng) · chỉ phòng. */
  tu: Cho;
  den: Cho;
  nhanTu: string;
  nhanDen: string;
  nhanSo: string;
  /** Ghi chú ngầm khi kho cơ sở là đầu còn lại. */
  goiY?: string;
}

export const KIEU_PHIEU: Record<string, Kieu> = {
  NHAP: { nhan: "Nhập kho", tu: null, den: "noi", nhanTu: "", nhanDen: "Nhập vào", nhanSo: "Số lượng nhập" },
  XUAT_PHONG: {
    nhan: "Xuất kho → phòng",
    tu: null,
    den: "phong",
    nhanTu: "",
    nhanDen: "Phòng nhận",
    nhanSo: "Số lượng xuất",
    goiY: "Lấy từ Kho cơ sở. Kho hết trên sổ vẫn xuất được — tồn âm sẽ nhắc kiểm đếm.",
  },
  TRA_KHO: {
    nhan: "Phòng trả kho",
    tu: "phong",
    den: null,
    nhanTu: "Phòng trả",
    nhanDen: "",
    nhanSo: "Số lượng trả",
    goiY: "Trả về Kho cơ sở.",
  },
  CHUYEN_PHONG: {
    nhan: "Chuyển phòng → phòng",
    tu: "phong",
    den: "phong",
    nhanTu: "Từ phòng",
    nhanDen: "Sang phòng",
    nhanSo: "Số lượng chuyển",
  },
  DIEU_CHINH: {
    nhan: "Kiểm đếm — chỉnh tồn theo số đếm",
    tu: "noi",
    den: null,
    nhanTu: "Nơi kiểm",
    nhanDen: "",
    nhanSo: "Số đếm thực tế",
    goiY: "Tồn trên sổ được chỉnh đúng bằng số đếm; có thể hoàn tác bằng phiếu đảo.",
  },
  KIEM: {
    nhan: "Kiểm đếm — chỉ ghi số đếm",
    tu: "noi",
    den: null,
    nhanTu: "Nơi kiểm",
    nhanDen: "",
    nhanSo: "Số đếm thực tế",
    goiY: "Chỉ ghi lại số đếm, tồn trên sổ chưa đổi.",
  },
  HUY: { nhan: "Huỷ hỏng", tu: "noi", den: null, nhanTu: "Huỷ ở", nhanDen: "", nhanSo: "Số lượng huỷ" },
};

interface Dong {
  k: number;
  ten: string;
  tu: string;
  den: string;
  so: string;
  gia: string;
}

let dem = 0;
const dongMoi = (): Dong => ({ k: ++dem, ten: "", tu: "", den: "", so: "", gia: "" });

export default function LapPhieuVatTu({
  noiChua,
  vatTu,
}: {
  noiChua: NoiChua[];
  vatTu: { id: string; name: string }[];
}) {
  const router = useRouter();
  const [loai, setLoai] = useState("XUAT_PHONG");
  const [ghiChu, setGhiChu] = useState("");
  const [dong, setDong] = useState<Dong[]>(() => [dongMoi()]);
  const [khoa, setKhoa] = useState(khoaMoi);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);

  const kieu = KIEU_PHIEU[loai];
  const phong = noiChua.filter((n) => n.room_id);
  const phongNhan = phong.filter((n) => n.dang_bat);
  const chon = (cho: Cho, nhan: string, gia: string, dat: (v: string) => void, den: boolean) =>
    cho ? (
      <label className="block">
        <span className="mb-1 block text-meta text-ink-soft">{nhan}</span>
        <OChon value={gia} onChange={(e) => dat(e.target.value)} className="w-full">
          {cho === "noi" ? (
            <option value="">Kho cơ sở</option>
          ) : (
            <option value="">Chọn phòng…</option>
          )}
          {(den ? phongNhan : phong).map((n) => (
            <option key={n.room_id} value={n.room_id ?? ""}>
              {n.dang_bat ? n.ten : `${n.ten} (đã tắt)`}
            </option>
          ))}
        </OChon>
      </label>
    ) : null;

  const suaDong = (k: number, doi: Partial<Dong>) =>
    setDong((ds) => ds.map((d) => (d.k === k ? { ...d, ...doi } : d)));

  const thieu = dong.some(
    (d) =>
      !d.ten.trim() ||
      !d.so.trim() ||
      (kieu.tu === "phong" && !d.tu) ||
      (kieu.den === "phong" && !d.den),
  );

  const luu = async () => {
    const sai = dong.findIndex((d) => !vatTu.some((v) => v.name === d.ten));
    if (sai >= 0) {
      setLoi(`Dòng ${sai + 1}: chọn vật tư có trong danh mục (gõ rồi chọn trong danh sách).`);
      return;
    }
    setDang(true);
    setLoi(null);
    setBao(null);
    const kq = await guiVatTu(
      "phieu",
      {
        loai,
        ghi_chu: ghiChu.trim() || null,
        dong: dong.map((d) => ({
          vat_tu_id: vatTu.find((v) => v.name === d.ten)?.id,
          tu_room_id: kieu.tu ? d.tu || null : null,
          den_room_id: kieu.den ? d.den || null : null,
          so_luong: d.so.trim().replace(",", "."),
          gia_nhap: d.gia.trim() || null,
        })),
      },
      khoa,
    );
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    const ma = (kq.data as { ma_phieu?: string } | null)?.ma_phieu;
    setBao(`Đã lập phiếu ${ma ?? ""} — tồn đã cập nhật. Sai thì bấm Hoàn tác ở danh sách bên dưới.`);
    setDong([dongMoi()]);
    setGhiChu("");
    setKhoa(khoaMoi());
    router.refresh();
  };

  return (
    <section aria-label="Lập phiếu" className="space-y-3 rounded-card border border-line bg-surface p-4 shadow-card">
      <div className="flex flex-wrap items-end gap-3">
        <h3 className="text-title text-ink">Lập phiếu</h3>
        <label className="block min-w-0 flex-1 basis-56">
          <span className="mb-1 block text-meta text-ink-soft">Loại phiếu</span>
          <OChon
            value={loai}
            onChange={(e) => {
              setLoai(e.target.value);
              setDong([dongMoi()]);
              setKhoa(khoaMoi());
            }}
            className="w-full"
          >
            {Object.entries(KIEU_PHIEU).map(([ma, k]) => (
              <option key={ma} value={ma}>
                {k.nhan}
              </option>
            ))}
          </OChon>
        </label>
      </div>
      {kieu.goiY ? <p className="text-meta text-ink-muted">{kieu.goiY}</p> : null}

      <datalist id="vat-tu-phieu">
        {vatTu.map((v) => (
          <option key={v.id} value={v.name} />
        ))}
      </datalist>
      <ol className="space-y-3">
        {dong.map((d, i) => (
          <li
            key={d.k}
            aria-label={`Dòng ${i + 1}`}
            className="grid grid-cols-2 gap-2 rounded-control border border-line bg-surface-muted p-3 lg:grid-cols-6"
          >
            <label className="col-span-2 block">
              <span className="mb-1 block text-meta text-ink-soft">{i + 1}. Vật tư</span>
              <ONhap
                list="vat-tu-phieu"
                value={d.ten}
                placeholder="Gõ tên vật tư…"
                onChange={(e) => suaDong(d.k, { ten: e.target.value })}
                className="w-full"
              />
            </label>
            {chon(kieu.tu, kieu.nhanTu, d.tu, (v) => suaDong(d.k, { tu: v }), false)}
            {chon(kieu.den, kieu.nhanDen, d.den, (v) => suaDong(d.k, { den: v }), true)}
            <label className="block">
              <span className="mb-1 block text-meta text-ink-soft">{kieu.nhanSo}</span>
              <ONhap
                inputMode="decimal"
                value={d.so}
                onChange={(e) => suaDong(d.k, { so: e.target.value })}
                className="w-full text-right tabular-nums"
              />
            </label>
            <div className="flex items-end gap-2">
              <label className="block min-w-0 flex-1">
                <span className="mb-1 block text-meta text-ink-soft">Giá nhập (đ)</span>
                <ONhap
                  inputMode="numeric"
                  value={d.gia}
                  placeholder="theo danh mục"
                  onChange={(e) => suaDong(d.k, { gia: e.target.value })}
                  className="w-full text-right tabular-nums"
                />
              </label>
              {dong.length > 1 ? (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  aria-label={`Bỏ dòng ${i + 1}`}
                  onClick={() => setDong((ds) => ds.filter((x) => x.k !== d.k))}
                >
                  Bỏ
                </Button>
              ) : null}
            </div>
          </li>
        ))}
      </ol>

      <label className="block">
        <span className="mb-1 block text-meta text-ink-soft">Lý do / ghi chú</span>
        <ONhap
          value={ghiChu}
          maxLength={1000}
          placeholder={loai === "HUY" ? "Vì sao huỷ — vỡ, hết hạn…" : "Ghi chú cho phiếu (tuỳ chọn)"}
          onChange={(e) => setGhiChu(e.target.value)}
          className="w-full"
        />
      </label>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="secondary" onClick={() => setDong((ds) => [...ds, dongMoi()])}>
          + Thêm dòng
        </Button>
        <Button type="button" variant="primary" disabled={dang || thieu} onClick={() => void luu()} className="sm:ml-auto">
          {dang ? "Đang lưu…" : "Lưu phiếu"}
        </Button>
      </div>
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
    </section>
  );
}
