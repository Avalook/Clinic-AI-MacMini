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
import { guiVatTu, khoaMoi, soVatTu } from "./gui-vat-tu";
import type { DongTon, NoiChua } from "./TonVatTu";

type Cho = null | "noi" | "phong";

interface Kieu {
  nhan: string;
  /** Ô "từ" / "đến": không có · nơi bất kỳ (kho hoặc phòng) · chỉ phòng. */
  tu: Cho;
  den: Cho;
  nhanTu: string;
  nhanDen: string;
  nhanSo: string;
}

export const KIEU_PHIEU: Record<string, Kieu> = {
  NHAP: { nhan: "Nhập hàng vào kho", tu: null, den: "noi", nhanTu: "", nhanDen: "Cất tại", nhanSo: "Số lượng nhận" },
  XUAT_PHONG: {
    nhan: "Cấp vật tư từ kho cho phòng",
    tu: null,
    den: "phong",
    nhanTu: "",
    nhanDen: "Phòng nhận",
    nhanSo: "Số lượng giao",
  },
  TRA_KHO: {
    nhan: "Phòng trả vật tư về kho",
    tu: "phong",
    den: null,
    nhanTu: "Phòng trả",
    nhanDen: "",
    nhanSo: "Số lượng chưa dùng trả",
  },
  TRA_NCC: {
    nhan: "Trả nhà sản xuất",
    tu: "noi",
    den: null,
    nhanTu: "Nơi đang giữ hàng",
    nhanDen: "",
    nhanSo: "Số lượng trả",
  },
  CHUYEN_PHONG: {
    nhan: "Chuyển vật tư giữa hai phòng",
    tu: "phong",
    den: "phong",
    nhanTu: "Từ phòng",
    nhanDen: "Sang phòng",
    nhanSo: "Số lượng chuyển",
  },
  KIEM: { nhan: "Kiểm kê (chỉ lưu số đếm)", tu: "noi", den: null, nhanTu: "Nơi kiểm", nhanDen: "", nhanSo: "Số đếm thực tế" },
  DIEU_CHINH: {
    nhan: "Kiểm kê",
    tu: "noi",
    den: null,
    nhanTu: "Nơi kiểm",
    nhanDen: "",
    nhanSo: "Số đếm thực tế",
  },
  HUY: { nhan: "Ghi nhận vật tư hỏng hoặc huỷ", tu: "noi", den: null, nhanTu: "Nơi có hàng hỏng", nhanDen: "", nhanSo: "Số lượng huỷ" },
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

/** Câu báo sau khi máy chủ nhận phiếu NHẬP có dòng "cần duyệt nhập" (G8b). Máy chủ trả
 *  `cho_duyet` + `trang_thai`; màn chỉ chọn câu chữ, không tự quyết phiếu có cần duyệt. */
function baoYeuCau(d: {
  cho_duyet?: boolean;
  trang_thai?: string;
  ma_yeu_cau?: string;
  ma_phieu?: string;
  gui_lai?: boolean;
}): string | null {
  if (!d.ma_yeu_cau) return null;
  const lai = d.gui_lai ? " (phiếu này đã gửi trước đó)" : "";
  if (d.cho_duyet) {
    return `Phiếu có dòng cần duyệt — đã gửi xin duyệt ${d.ma_yeu_cau}${lai}, chưa vào kho. Người có quyền Duyệt vật tư sẽ duyệt ở tab Chờ duyệt.`;
  }
  if (d.trang_thai === "DA_DUYET" && !d.gui_lai) {
    return `Phiếu có dòng cần duyệt — bạn có quyền Duyệt vật tư nên đã tự duyệt và nhập kho (${d.ma_yeu_cau}${d.ma_phieu ? `, phiếu ${d.ma_phieu}` : ""}). Sai thì bấm Hoàn tác ở danh sách bên dưới.`;
  }
  return `Phiếu này đã gửi xin duyệt trước đó (${d.ma_yeu_cau}) và đã được quyết — xem ở tab Chờ duyệt, không lập thêm phiếu.`;
}

export default function LapPhieuVatTu({
  noiChua,
  vatTu,
  ton,
  xemChoDuyet,
  loaiBanDau,
  initialRoomId = null,
  fixedMaterial,
  fixedMaterialId,
  onHuy,
}: {
  noiChua: NoiChua[];
  vatTu: { id: string; name: string; unit?: string | null; service_code?: string | null }[];
  ton: DongTon[];
  /** Chuyển sang tab Chờ duyệt khi phiếu vừa gửi đang chờ. */
  xemChoDuyet?: () => void;
  loaiBanDau: "NHAP" | "XUAT_PHONG" | "TRA_KHO" | "TRA_NCC" | "CHUYEN_PHONG" | "DIEU_CHINH" | "HUY";
  /** Điền sẵn nơi đang xem trong bảng tồn. */
  initialRoomId?: string | null;
  /** Hành động mở từ một dòng tồn thì khoá mặt hàng để tránh thao tác nhầm dòng. */
  fixedMaterial?: string;
  fixedMaterialId?: string;
  onHuy?: () => void;
}) {
  const router = useRouter();
  const [cachXuLy, setCachXuLy] = useState<"HUY" | "TRA_KHO" | "TRA_NCC">("HUY");
  const [cheDoKiem, setCheDoKiem] = useState<"KIEM" | "DIEU_CHINH">("DIEU_CHINH");
  const loai = loaiBanDau === "HUY" ? cachXuLy : loaiBanDau === "DIEU_CHINH" ? cheDoKiem : loaiBanDau;
  const [ghiChu, setGhiChu] = useState("");
  const [nhaCungCap, setNhaCungCap] = useState("");
  const nhanVatTu = (v: typeof vatTu[number]) => `${v.name} · ${v.service_code || v.id}${v.unit ? ` · ${v.unit}` : ""}`;
  const vatTuDaChon = (ten: string) => {
    if (fixedMaterialId) return vatTu.find((v) => v.id === fixedMaterialId);
    const theoNhan = vatTu.find((v) => nhanVatTu(v) === ten);
    if (theoNhan) return theoNhan;
    const cungTen = vatTu.filter((v) => v.name === ten);
    return cungTen.length === 1 ? cungTen[0] : undefined;
  };
  const taoDongTrongPhamVi = (): Dong => ({
    ...dongMoi(),
    ten: fixedMaterial ?? "",
    tu: loaiBanDau === "NHAP" || loaiBanDau === "XUAT_PHONG" ? "" : initialRoomId ?? "",
    den: loaiBanDau === "NHAP" || loaiBanDau === "XUAT_PHONG" ? initialRoomId ?? "" : "",
  });
  const [dong, setDong] = useState<Dong[]>(() => [taoDongTrongPhamVi()]);
  const [khoa, setKhoa] = useState(khoaMoi);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);
  const [dangCho, setDangCho] = useState(false);

  const kieu = KIEU_PHIEU[loai];
  const phong = noiChua.filter((n) => n.room_id);
  const phongNhan = phong.filter((n) => n.dang_bat);
  const chon = (cho: Cho, nhan: string, gia: string, dat: (v: string) => void, den: boolean) =>
    cho ? (
      <label className="block">
        <span className="mb-1 block text-meta text-ink-soft">{nhan}</span>
        <OChon value={gia} onChange={(e) => dat(e.target.value)} className="w-full">
          {cho === "noi" ? (
            <option value="">Kho</option>
          ) : (
            <option value="">Chọn phòng…</option>
          )}
          {(den ? phongNhan : phong).length === 0 ? (
            <option value="" disabled>
              {den ? "Chưa có phòng đang hoạt động" : "Chưa có phòng đã cấu hình"}
            </option>
          ) : null}
          {(den ? phongNhan : phong).map((n) => (
            <option key={n.room_id} value={n.room_id ?? ""}>
              {n.dang_bat ? n.ten : `${n.ten} (đã tắt)`}
            </option>
          ))}
        </OChon>
        {cho === "phong" && (den ? phongNhan : phong).length === 0 ? (
          <span className="mt-1 block text-meta text-ink-muted">
            Chưa có phòng dùng cho cơ sở này. Nhờ quản lý bật hoặc gán phòng trong Cấu trúc phòng khám.
          </span>
        ) : null}
      </label>
    ) : null;

  const suaDong = (k: number, doi: Partial<Dong>) =>
    setDong((ds) => ds.map((d) => (d.k === k ? { ...d, ...doi } : d)));

  const thieu = dong.some(
    (d) =>
      !d.ten.trim() ||
      !d.so.trim() ||
      (loai === "TRA_NCC" && (nhaCungCap.trim().length < 2 || ghiChu.trim().length < 5)) ||
      (kieu.tu === "phong" && !d.tu) ||
      (kieu.den === "phong" && !d.den),
  );

  const luu = async () => {
    const sai = dong.findIndex((d) => !vatTuDaChon(d.ten));
    if (sai >= 0) {
      setLoi(`Dòng ${sai + 1}: chọn vật tư duy nhất trong danh mục. Nếu trùng tên, cần phân biệt tên hoặc đơn vị trong danh mục trước khi ghi phiếu.`);
      return;
    }
    setDang(true);
    setLoi(null);
    setBao(null);
    setDangCho(false);
    const kq = await guiVatTu(
      "phieu",
      {
        loai,
        ghi_chu: ghiChu.trim() || null,
        nha_cung_cap: loai === "TRA_NCC" ? nhaCungCap.trim() : null,
        dong: dong.map((d) => ({
          vat_tu_id: vatTuDaChon(d.ten)?.id,
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
    const d = kq.data as Parameters<typeof baoYeuCau>[0] | null;
    const yeuCau = d ? baoYeuCau(d) : null;
    setDangCho(d?.cho_duyet === true);
    setBao(
      yeuCau ?? `Đã ghi nhận “${kieu.nhan}”${d?.ma_phieu ? ` · mã ${d.ma_phieu}` : ""}. ${loai === "KIEM" ? "Số đếm đã lưu, tồn chưa thay đổi." : "Tồn đã cập nhật."} Nếu ghi nhầm, mở Lịch sử thao tác để hoàn tác.`,
    );
    setDong([taoDongTrongPhamVi()]);
    setGhiChu("");
    setNhaCungCap("");
    setKhoa(khoaMoi());
    router.refresh();
  };

  return (
    <section aria-label="Ghi nhận thao tác kho" className="space-y-3 rounded-card border border-line bg-surface p-4 shadow-card">
      <datalist id="vat-tu-phieu">
        {vatTu.map((v) => (
          <option key={v.id} value={nhanVatTu(v)} />
        ))}
      </datalist>
      {loaiBanDau === "HUY" ? (
        <label className="block max-w-md">
          <span className="mb-1 block text-meta text-ink-soft">Cách xử lý hàng</span>
          <OChon
            value={cachXuLy}
            onChange={(e) => {
              setCachXuLy(e.target.value as "HUY" | "TRA_KHO" | "TRA_NCC");
              setDong((ds) => ds.map((d) => ({ ...d, tu: initialRoomId ?? "", den: "" })));
            }}
            className="w-full"
          >
            <option value="HUY">Huỷ bỏ hàng hỏng</option>
            <option value="TRA_KHO">Nhập lại kho</option>
            <option value="TRA_NCC">Trả nhà sản xuất</option>
          </OChon>
        </label>
      ) : null}
      {loaiBanDau === "DIEU_CHINH" ? (
        <label className="block max-w-md">
          <span className="mb-1 block text-meta text-ink-soft">Sau khi đếm</span>
          <OChon value={cheDoKiem} onChange={(e) => setCheDoKiem(e.target.value as "KIEM" | "DIEU_CHINH")} className="w-full">
            <option value="KIEM">Chỉ lưu số đếm</option>
            <option value="DIEU_CHINH">Cập nhật tồn theo số đếm</option>
          </OChon>
        </label>
      ) : null}
      {loai === "TRA_NCC" ? (
        <label className="block max-w-md">
          <span className="mb-1 block text-meta text-ink-soft">Nhà sản xuất</span>
          <ONhap value={nhaCungCap} maxLength={200} onChange={(e) => setNhaCungCap(e.target.value)} className="w-full" />
        </label>
      ) : null}
      <ol className="space-y-3">
        {dong.map((d, i) => (
          <li
            key={d.k}
            aria-label={`Dòng ${i + 1}`}
            className="grid grid-cols-2 gap-2 rounded-control border border-line bg-surface-muted p-3 lg:grid-cols-6"
          >
            <label className="col-span-2 block">
              <span className="mb-1 block text-meta text-ink-soft">{i + 1}. Vật tư</span>
              {fixedMaterial ? (
                <div className="flex min-h-10 items-center rounded-control border border-line bg-surface px-3 text-body font-medium text-ink">
                  {fixedMaterial}
                </div>
              ) : (
                <ONhap
                  list="vat-tu-phieu"
                  value={d.ten}
                  placeholder="Gõ tên vật tư…"
                  onChange={(e) => suaDong(d.k, { ten: e.target.value })}
                  className="w-full"
                />
              )}
            </label>
            {chon(kieu.tu, kieu.nhanTu, d.tu, (v) => suaDong(d.k, { tu: v }), false)}
            {chon(kieu.den, kieu.nhanDen, d.den, (v) => suaDong(d.k, { den: v }), true)}
            <label className="block">
              <span className="mb-1 block text-meta text-ink-soft">
                {loai === "DIEU_CHINH" || loai === "KIEM" ? "Số đếm thực tế" : kieu.nhanSo}
              </span>
              <ONhap
                inputMode="decimal"
                value={d.so}
                onChange={(e) => suaDong(d.k, { so: e.target.value })}
                className="w-full text-right tabular-nums"
              />
            </label>
            {(loai === "DIEU_CHINH" || loai === "KIEM") && (() => {
              const vatTuId = vatTuDaChon(d.ten)?.id;
              const roomId = d.tu || null;
              const soTrenSo = ton.find((t) => t.vat_tu_id === vatTuId && t.room_id === roomId)?.so_luong ?? 0;
              const soDem = Number(d.so.trim().replace(",", "."));
              const chenhLech = d.so.trim() && Number.isFinite(soDem) ? soDem - soTrenSo : null;
              const dau = chenhLech !== null && chenhLech > 0 ? "+" : "";
              return (
                <p className="col-span-2 text-meta text-ink-muted">
                  Tồn sổ: {soVatTu(soTrenSo)}. {chenhLech === null
                    ? "Nhập số đếm thực tế để xem chênh lệch."
                    : `Chênh lệch dự kiến: ${dau}${soVatTu(chenhLech)}.`}
                  {loai === "DIEU_CHINH"
                    ? " Khi lưu, tồn sẽ cập nhật bằng số đếm thực tế. Nếu ghi nhầm, có thể hoàn tác trong lịch sử."
                    : " Chế độ này chỉ lưu số đếm, không thay đổi tồn kho."}
                </p>
              );
            })()}
            {loai === "NHAP" ? (
              <label className="block min-w-0 flex-1">
                <span className="mb-1 block text-meta text-ink-soft">Giá mua một đơn vị (đ)</span>
                <ONhap
                  inputMode="numeric"
                  value={d.gia}
                  placeholder="Lấy giá đã cài nếu để trống"
                  onChange={(e) => suaDong(d.k, { gia: e.target.value })}
                  className="w-full text-right tabular-nums"
                />
              </label>
            ) : null}
            {dong.length > 1 ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                aria-label={`Bỏ dòng ${i + 1}`}
                onClick={() => setDong((ds) => ds.filter((x) => x.k !== d.k))}
              >
                Bỏ dòng này
              </Button>
            ) : null}
          </li>
        ))}
      </ol>

      <label className="block">
        <span className="mb-1 block text-meta text-ink-soft">{loai === "TRA_NCC" ? "Lý do trả nhà sản xuất" : "Ghi chú / lý do"}</span>
        <ONhap
          value={ghiChu}
          maxLength={1000}
          placeholder={loai === "TRA_NCC" ? "Ví dụ: hàng lỗi, thu hồi theo yêu cầu…" : loai === "HUY" ? "Vì sao huỷ — vỡ, hỏng…" : "Ghi chú thao tác (tuỳ chọn)"}
          onChange={(e) => setGhiChu(e.target.value)}
          className="w-full"
        />
      </label>

      <div className="flex flex-wrap items-center gap-2">
        {!fixedMaterial ? (
          <Button type="button" size="sm" variant="secondary" onClick={() => setDong((ds) => [...ds, taoDongTrongPhamVi()])}>
            + Thêm dòng
          </Button>
        ) : null}
        {onHuy ? (
          <Button type="button" size="sm" variant="ghost" onClick={onHuy}>
            Đóng
          </Button>
        ) : null}
        <Button type="button" variant="primary" disabled={dang || thieu} onClick={() => void luu()} className="sm:ml-auto">
          {dang ? "Đang lưu…" : loai === "KIEM" ? "Lưu số đếm" : loai === "DIEU_CHINH" ? "Cập nhật tồn kho" : loai === "HUY" || loai === "TRA_NCC" ? kieu.nhan : `Ghi nhận ${kieu.nhan.toLocaleLowerCase("vi")}`}
        </Button>
      </div>
      {loi ? (
        <p role="alert" className="text-body text-danger">
          {loi}
        </p>
      ) : null}
      {bao ? (
        <div className="flex flex-wrap items-center gap-2">
          <p role="status" className="min-w-0 flex-1 basis-64 text-body text-success">
            {bao}
          </p>
          {dangCho && xemChoDuyet ? (
            <Button type="button" size="sm" variant="secondary" onClick={xemChoDuyet}>
              Xem ở Chờ duyệt
            </Button>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
