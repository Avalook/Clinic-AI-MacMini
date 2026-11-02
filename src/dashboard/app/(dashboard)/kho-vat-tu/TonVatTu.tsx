"use client";

// Một phạm vi tồn tại một thời điểm; thao tác mở ngay trên dòng vật tư đó.

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import HopChiTiet from "@/components/ui/HopChiTiet";
import ONhap from "@/components/ui/ONhap";
import { boDauVatTu } from "@/lib/vat-tu";
import { guiVatTu, soVatTu } from "./gui-vat-tu";
import type { DongTieuHao, GoiTieuHao } from "./bao-cao-vat-tu";
import type { DongVatTu } from "../cashier/VatTuBangGia";
import LapPhieuVatTu from "./LapPhieuVatTu";

export interface DongTon {
  id: string;
  vat_tu_id: string;
  room_id: string | null;
  ten: string;
  don_vi: string | null;
  noi_chua: string;
  so_luong: number;
  ton_toi_thieu: number;
  gia_tri_ton?: number | null;
  /** Chữ máy chủ đặt: tồn âm hoặc dưới mức tối thiểu. */
  canh_bao: string;
}

export interface NoiChua {
  room_id: string | null;
  ten: string;
  dang_bat: boolean;
}

type NhomVatTu = "tat_ca" | "VPP" | "VTYT";
type PhamVi = "kho" | "phong";
type LoaiThaoTac = "NHAP" | "XUAT_PHONG" | "TRA_KHO" | "TRA_NCC" | "CHUYEN_PHONG" | "DIEU_CHINH" | "HUY";

const NHOM = [
  { ma: "tat_ca", nhan: "Tất cả vật tư" },
  { ma: "VPP", nhan: "Văn phòng phẩm" },
  { ma: "VTYT", nhan: "Vật tư y tế" },
] as const;

const CAC_THAO_TAC: Record<PhamVi, { loai: LoaiThaoTac; nhan: string }[]> = {
  kho: [
    { loai: "NHAP", nhan: "Nhập bổ sung" },
    { loai: "XUAT_PHONG", nhan: "Cấp cho phòng" },
    { loai: "DIEU_CHINH", nhan: "Kiểm kê" },
    { loai: "HUY", nhan: "Báo hỏng / huỷ" },
    { loai: "TRA_NCC", nhan: "Trả nhà sản xuất" },
  ],
  phong: [
    { loai: "XUAT_PHONG", nhan: "Cấp thêm từ kho" },
    { loai: "TRA_KHO", nhan: "Trả về kho" },
    { loai: "CHUYEN_PHONG", nhan: "Chuyển sang phòng khác" },
    { loai: "DIEU_CHINH", nhan: "Kiểm kê" },
    { loai: "HUY", nhan: "Báo hỏng / huỷ" },
    { loai: "TRA_NCC", nhan: "Trả nhà sản xuất" },
  ],
};

function tienVnd(gia: number): string {
  return `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(gia)} ₫`;
}

function nhanKinhDoanh(vatTu: DongVatTu | undefined): string {
  if (!vatTu) return "Chưa có nhãn";
  if (vatTu.can_ql_duyet) return "Cần duyệt bán";
  return vatTu.kinh_doanh ? "Được kinh doanh" : "Không kinh doanh";
}

export default function TonVatTu({
  ton,
  noiChua,
  vatTu,
  baoCao,
  tuNgay,
  denNgay,
  dangBaoCao,
  loiBaoCao,
}: {
  ton: DongTon[];
  noiChua: NoiChua[];
  vatTu: DongVatTu[];
  baoCao: GoiTieuHao | null;
  tuNgay: string;
  denNgay: string;
  dangBaoCao: boolean;
  loiBaoCao: string | null;
}) {
  const router = useRouter();
  const [phamVi, setPhamVi] = useState<PhamVi>("kho");
  const [phongId, setPhongId] = useState(() =>
    noiChua.find((n) => n.room_id && n.dang_bat)?.room_id ?? "",
  );
  const [nhom, setNhom] = useState<NhomVatTu>("tat_ca");
  const [chiCanChuY, setChiCanChuY] = useState(false);
  const [tim, setTim] = useState("");
  const [mucSua, setMucSua] = useState<Record<string, string>>({});
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);
  const [dongMo, setDongMo] = useState<string | null>(null);
  const [thaoTacMo, setThaoTacMo] = useState<LoaiThaoTac | null>(null);
  const [moNhapHang, setMoNhapHang] = useState(false);

  const vatTuTheoId = useMemo(() => new Map(vatTu.map((v) => [v.id, v])), [vatTu]);
  const thongKeTheoTon = useMemo(
    () => new Map((baoCao?.items ?? []).map((d) => [`${d.room_id}:${d.vat_tu_id}`, d])),
    [baoCao],
  );
  const phongDangXem = noiChua.find((n) => n.room_id === phongId);
  const tonTheoNoi = useMemo(() => {
    if (phamVi === "kho") return ton.filter((t) => t.room_id === null);
    return phongId ? ton.filter((t) => t.room_id === phongId) : [];
  }, [ton, phamVi, phongId]);
  const demTheoNhom = useMemo(() => {
    const dem = { tat_ca: new Set<string>(), VPP: new Set<string>(), VTYT: new Set<string>() };
    for (const dong of tonTheoNoi) {
      dem.tat_ca.add(dong.vat_tu_id);
      const loai = vatTuTheoId.get(dong.vat_tu_id)?.loai_vat_tu;
      if (loai === "VPP" || loai === "VTYT") dem[loai].add(dong.vat_tu_id);
    }
    return { tat_ca: dem.tat_ca.size, VPP: dem.VPP.size, VTYT: dem.VTYT.size };
  }, [tonTheoNoi, vatTuTheoId]);
  const canChuY = tonTheoNoi.filter((t) => t.canh_bao).length;
  const hien = useMemo(() => {
    const khoa = boDauVatTu(tim.trim());
    return tonTheoNoi.filter((t) => {
      const hang = vatTuTheoId.get(t.vat_tu_id);
      const loai = hang?.loai_vat_tu ?? "CHUA_PHAN_LOAI";
      const timDuoc = !khoa || boDauVatTu(`${t.ten} ${hang?.service_code ?? ""}`).includes(khoa);
      return (nhom === "tat_ca" || loai === nhom) && (!chiCanChuY || Boolean(t.canh_bao)) && timDuoc;
    });
  }, [tonTheoNoi, vatTuTheoId, nhom, chiCanChuY, tim]);

  async function luuMuc(dong: DongTon) {
    setDang(true);
    setLoi(null);
    setBao(null);
    const kq = await guiVatTu("muc-toi-thieu", {
      vat_tu_id: dong.vat_tu_id,
      room_id: dong.room_id,
      muc: mucSua[dong.id]?.trim().replace(",", "."),
    });
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setBao(`Đã lưu mức nhắc cho ${dong.ten}.`);
    setMucSua((hienTai) => Object.fromEntries(Object.entries(hienTai).filter(([id]) => id !== dong.id)));
    router.refresh();
  }

  function chonPhamVi(moi: PhamVi) {
    setPhamVi(moi);
    setDongMo(null);
    setThaoTacMo(null);
    setChiCanChuY(false);
    setMoNhapHang(false);
  }

  const nutPhamVi = (ma: PhamVi, nhan: string) => (
    <Button
      type="button"
      size="sm"
      variant={phamVi === ma ? "primary" : "secondary"}
      aria-pressed={phamVi === ma}
      onClick={() => chonPhamVi(ma)}
    >
      {nhan}
    </Button>
  );

  const vatTuDangMo = hien.find((t) => t.id === dongMo);
  const ngayKy = `${tuNgay.split("-").reverse().join("/")}–${denNgay.split("-").reverse().join("/")}`;

  function hienLuongKy(dong: DongTieuHao | undefined): string {
    if (!baoCao) return dangBaoCao ? "Đang tải" : "—";
    return dong ? soVatTu(dong.cap_trong_ky) : "—";
  }

  function hienDaDung(dong: DongTieuHao | undefined): string {
    if (!baoCao) return dangBaoCao ? "Đang tải" : "—";
    if (!dong?.du_du_lieu || dong.da_dung == null) return "Chưa đủ";
    return soVatTu(dong.da_dung);
  }

  function hienThucTe(dong: DongTieuHao | undefined): string {
    if (!baoCao) return dangBaoCao ? "Đang tải" : "—";
    if (!dong || dong.thuc_te_gan_nhat == null) return "Chưa kiểm";
    return soVatTu(dong.thuc_te_gan_nhat);
  }

  return (
    <div className="flex flex-col gap-3">
      <section aria-label="Lọc loại vật tư" className="grid grid-cols-1 gap-2 rounded-card border border-hairline bg-surface p-2 sm:grid-cols-3">
        {NHOM.map((muc) => {
          const dangChon = nhom === muc.ma;
          return (
            <button
              key={muc.ma}
              type="button"
              aria-pressed={dangChon}
              onClick={() => setNhom(muc.ma)}
              className={`flex min-h-14 items-center justify-between gap-2 rounded-control px-3 text-left transition-colors sm:min-h-16 sm:flex-col sm:justify-center sm:text-center ${dangChon ? "bg-brand-50 text-brand-700 ring-1 ring-brand-600" : "bg-surface hover:bg-surface-sunken"}`}
            >
              <span className="text-emph font-medium">{muc.nhan}</span>
              <span className="text-title font-semibold tabular-nums">{demTheoNhom[muc.ma]}</span>
            </button>
          );
        })}
      </section>

      <section aria-label="Chọn nơi xem tồn" className="flex flex-wrap items-end gap-2">
        <div className="flex min-h-10 items-center gap-2" aria-label="Phạm vi tồn">
          {nutPhamVi("kho", "Kho")}
          {nutPhamVi("phong", "Theo phòng")}
        </div>
        {phamVi === "phong" ? (
          <label className="flex min-w-48 flex-col gap-1 text-meta text-ink-muted">
            <span>Phòng đang xem</span>
            <select
              aria-label="Phòng đang xem"
              value={phongId}
              onChange={(e) => {
                setPhongId(e.target.value);
                setDongMo(null);
                setThaoTacMo(null);
                setChiCanChuY(false);
                setMoNhapHang(false);
              }}
              className="min-h-10 rounded-control border border-line-strong bg-surface px-3 text-body text-ink"
            >
              <option value="">Chọn một phòng…</option>
              {noiChua.filter((n) => n.room_id).map((n) => (
                <option key={n.room_id} value={n.room_id ?? ""}>
                  {n.dang_bat ? n.ten : `${n.ten} (đã ngừng hoạt động)`}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <p className="self-center text-meta text-ink-muted">Đang xem riêng tồn tại Kho</p>
        )}
        <ONhap
          type="search"
          aria-label="Tìm vật tư"
          placeholder="Tìm tên vật tư hoặc mã"
          value={tim}
          onChange={(e) => setTim(e.target.value)}
          className="w-full sm:ml-auto sm:w-64"
        />
        <Button type="button" variant="primary" disabled={phamVi === "phong" && !phongDangXem?.dang_bat} onClick={() => {
          setMoNhapHang((m) => !m);
          setDongMo(null);
          setThaoTacMo(null);
        }}>
          {phamVi === "kho" ? "+ Nhập hàng" : "+ Cấp vật tư từ kho"}
        </Button>
      </section>

      {canChuY > 0 ? (
        <div role="status" className="flex flex-wrap items-center justify-between gap-2 rounded-control border border-warning bg-warning-bg px-3 py-2 text-body text-warning">
          <span><strong>Sắp hết / cần kiểm tra</strong> · {canChuY} mặt hàng tại nơi đang xem</span>
          <Button type="button" size="sm" variant="secondary" onClick={() => setChiCanChuY((c) => !c)}>
            {chiCanChuY ? "Bỏ lọc" : "Chỉ xem các mặt hàng này"}
          </Button>
        </div>
      ) : null}
      {loiBaoCao ? (
        <p role="alert" className="text-body text-danger">
          Chưa cập nhật được số liệu cấp và kiểm kê trong kỳ. {loiBaoCao}
        </p>
      ) : null}

      {moNhapHang ? (
        <LapPhieuVatTu
          key={`nhap-${phamVi}-${phongId}`}
          noiChua={noiChua}
          vatTu={vatTu.map((v) => ({ id: v.id, name: v.name, service_code: v.service_code, unit: v.don_vi }))}
          ton={ton}
          loaiBanDau={phamVi === "kho" ? "NHAP" : "XUAT_PHONG"}
          initialRoomId={phamVi === "phong" ? phongId || null : null}
          onHuy={() => setMoNhapHang(false)}
        />
      ) : null}

      {phamVi === "phong" && !phongId ? (
        <p className="rounded-card border border-line bg-surface px-4 py-6 text-center text-body text-ink-muted">
          Chọn một phòng để xem tồn riêng và thao tác tại phòng đó.
        </p>
      ) : hien.length === 0 ? (
        <section className="flex flex-col items-center gap-3 rounded-card border border-line bg-surface p-5 text-center">
          <h3 className="text-emph font-semibold text-ink">
            {tonTheoNoi.length === 0 ? (phamVi === "kho" ? "Kho chưa có tồn" : `Phòng ${phongDangXem?.ten ?? "này"} chưa có tồn`) : "Không có vật tư khớp bộ lọc"}
          </h3>
          <p className="max-w-2xl text-body text-ink-muted">
            {tonTheoNoi.length === 0
              ? "Nhập số lượng để bắt đầu theo dõi. Mặt hàng mới cần được thêm trong Danh mục trước."
              : "Thử đổi nhóm vật tư, bỏ lọc cần kiểm tra hoặc sửa từ khoá tìm kiếm."}
          </p>
          {tonTheoNoi.length === 0 ? (
            <Button type="button" variant="primary" disabled={phamVi === "phong" && !phongDangXem?.dang_bat} onClick={() => setMoNhapHang(true)}>
              {phamVi === "kho" ? "Nhập hàng vào kho" : "Cấp vật tư từ kho"}
            </Button>
          ) : null}
        </section>
      ) : (
        <div className="overflow-x-auto rounded-card border border-hairline bg-surface shadow-card">
          <table className="w-full min-w-max table-fixed text-left">
            <thead className="bg-surface-muted text-label font-semibold text-ink-muted">
              <tr>
                <th className="w-[25%] px-3 py-2">VẬT TƯ</th>
                {phamVi === "phong" ? (
                  <>
                    <th className="px-3 py-2 text-right" title="Cấp từ kho hoặc chuyển từ phòng khác trong khoảng ngày đã chọn.">
                      ĐƯỢC CẤP
                      <span className="block text-meta font-normal normal-case">{ngayKy}</span>
                    </th>
                    <th className="px-3 py-2 text-right" title="Số dùng tính từ hai lần kiểm kê thật; hỏng hoặc huỷ được tách riêng.">ĐÃ DÙNG</th>
                    <th className="px-3 py-2 text-right" title="Số lượng còn lại theo sổ kho.">CÒN LẠI</th>
                    <th className="px-3 py-2 text-right" title="Số đếm thực tế mới nhất; có thể khác tồn theo sổ.">THỰC TẾ</th>
                  </>
                ) : (
                  <th className="px-3 py-2 text-right">SỐ LƯỢNG</th>
                )}
                <th className="px-3 py-2">ĐƠN VỊ</th>
                <th className="px-3 py-2 text-right" title="Theo giá nhập gần nhất; chưa phải giá vốn kế toán">GIÁ TRỊ ƯỚC TÍNH</th>
                <th className="px-3 py-2">NHÃN</th>
                <th className="w-28 px-3 py-2">MỨC NHẮC</th>
                <th data-excel-ignore className="w-28 sticky right-0 bg-surface-muted px-3 py-2">THAO TÁC</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline text-body text-ink">
              {hien.map((t) => {
                const hang = vatTuTheoId.get(t.vat_tu_id);
                const loai = hang?.loai_vat_tu ?? null;
                const giaTri = t.gia_tri_ton == null ? null : Number(t.gia_tri_ton);
                const mo = dongMo === t.id;
                const soLieu = t.room_id ? thongKeTheoTon.get(`${t.room_id}:${t.vat_tu_id}`) : undefined;
                return (
                    <tr key={t.id} className={mo ? "bg-brand-soft" : undefined}>
                      <td className="px-3 py-2.5">
                        <div className="min-w-0 break-words">
                          <p className="font-semibold text-ink">{t.ten}</p>
                          <div className="flex flex-wrap gap-1">
                            <Chip tone={loai === "VTYT" ? "info" : "brand"}>
                              {loai === "VPP" ? "Văn phòng phẩm" : loai === "VTYT" ? "Vật tư y tế" : "Chưa phân loại"}
                            </Chip>
                            {t.canh_bao ? <Chip tone="neutral">{t.canh_bao}</Chip> : null}
                          </div>
                        </div>
                      </td>
                      {phamVi === "phong" ? (
                        <>
                          <td className="whitespace-nowrap px-3 py-2.5 text-right tabular-nums" title="Số lượng được cấp trong kỳ đã chọn">
                            {hienLuongKy(soLieu)}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2.5 text-right tabular-nums" title={soLieu?.du_du_lieu ? "Số dùng theo hai lần kiểm kê thật." : soLieu?.ly_do_thieu ?? "Chưa đủ dữ liệu kiểm kê."}>
                            {hienDaDung(soLieu)}
                          </td>
                          <td className="whitespace-nowrap px-3 py-2.5 text-right font-semibold tabular-nums">{soVatTu(t.so_luong)}</td>
                          <td className="whitespace-nowrap px-3 py-2.5 text-right tabular-nums" title={soLieu?.thuc_te_gan_nhat_luc ? `Đếm lần gần nhất: ${new Date(soLieu.thuc_te_gan_nhat_luc).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" })}` : "Chưa có số đếm thực tế."}>
                            {hienThucTe(soLieu)}
                          </td>
                        </>
                      ) : (
                        <td className="whitespace-nowrap px-3 py-2.5 text-right font-semibold tabular-nums">{soVatTu(t.so_luong)}</td>
                      )}
                      <td className="whitespace-nowrap px-3 py-2.5 text-ink-muted">{t.don_vi ?? "—"}</td>
                      <td className="whitespace-nowrap px-3 py-2.5 text-right tabular-nums">{giaTri == null ? "—" : tienVnd(giaTri)}</td>
                      <td className="px-3 py-2.5">
                        <div className="flex min-w-0 flex-wrap gap-1">
                          <Chip tone={hang?.can_ql_duyet ? "neutral" : hang?.kinh_doanh ? "success" : "neutral"}>{nhanKinhDoanh(hang)}</Chip>
                          {hang?.can_duyet_nhap ? <Chip tone="neutral">Cần duyệt nhập</Chip> : null}
                        </div>
                      </td>
                      <td className="whitespace-nowrap px-3 py-2.5">
                        <div className="flex items-center gap-1.5">
                          <ONhap
                            inputMode="decimal"
                            aria-label={`Mức nhắc khi ${t.ten} còn dưới số lượng tại ${phamVi === "kho" ? "Kho" : phongDangXem?.ten ?? "phòng"}`}
                            value={mucSua[t.id] ?? String(t.ton_toi_thieu)}
                            onChange={(e) => setMucSua((c) => ({ ...c, [t.id]: e.target.value }))}
                            className="w-16 text-right tabular-nums"
                          />
                          {mucSua[t.id] !== undefined ? (
                            <Button type="button" size="sm" variant="secondary" disabled={dang} onClick={() => void luuMuc(t)}>Lưu</Button>
                          ) : null}
                        </div>
                      </td>
                      <td data-excel-ignore className="sticky right-0 whitespace-nowrap bg-surface px-3 py-2.5">
                        <Button
                          type="button"
                          size="sm"
                          variant={mo ? "soft" : "secondary"}
                          aria-expanded={mo}
                          onClick={() => {
                            setDongMo(mo ? null : t.id);
                            setThaoTacMo(null);
                            setMoNhapHang(false);
                          }}
                        >
                          {mo ? "Đóng" : "Thao tác"}
                        </Button>
                      </td>
                    </tr>

                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {vatTuDangMo ? (
        <HopChiTiet
          tieuDe={`${vatTuDangMo.ten} · ${phamVi === "kho" ? "Kho" : phongDangXem?.ten ?? "Phòng"}`}
          onDong={() => { setDongMo(null); setThaoTacMo(null); }}
        >
          <div data-excel-ignore className="space-y-3">
            <div className="flex flex-wrap gap-2">
              {CAC_THAO_TAC[phamVi].map((muc) => (
                <Button key={muc.loai} type="button" size="sm" variant={thaoTacMo === muc.loai ? "soft" : "secondary"} disabled={muc.loai === "XUAT_PHONG" && phamVi === "phong" && !phongDangXem?.dang_bat} onClick={() => setThaoTacMo(muc.loai)}>{muc.nhan}</Button>
              ))}
            </div>
            {thaoTacMo ? <LapPhieuVatTu
              key={`${vatTuDangMo.id}-${thaoTacMo}-${phongId}`}
              noiChua={noiChua}
              vatTu={[{ id: vatTuDangMo.vat_tu_id, name: vatTuDangMo.ten, unit: vatTuDangMo.don_vi }]}
              ton={ton}
              loaiBanDau={thaoTacMo}
              initialRoomId={phamVi === "phong" ? phongId || null : null}
              fixedMaterial={vatTuDangMo.ten}
              fixedMaterialId={vatTuDangMo.vat_tu_id}
              onHuy={() => setThaoTacMo(null)}
            /> : null}
          </div>
        </HopChiTiet>
      ) : null}

      {loi ? <p role="alert" className="text-body text-danger">{loi}</p> : null}
      {bao ? <p role="status" className="text-body text-success">{bao}</p> : null}
    </div>
  );
}
