"use client";

// Mục E — CHỈ ĐỊNH ĐIỀU TRỊ (đơn thuốc).
//
// Nguồn: *"E là nơi duy nhất ghi thuốc thực tế của đơn"*. Đơn thuốc đã có chỗ
// giữ riêng (bảng `prescription`, có luồng bác sĩ duyệt bản nháp của thư ký và
// có kho cấp phát). Phiếu KHÔNG giữ bản sao thứ hai — nên component này ĐIỀU
// KHIỂN TỪ NGOÀI: nó nhận `dong` và báo `onDoi`, còn ghi xuống đâu là việc của
// Bàn khám (đường ghi đơn thuốc sẵn có). Không truyền `onDoi` = chỉ đọc.
//
// Chọn thuốc từ danh mục gợi ý thì cách dùng / lưu ý được điền sẵn, bác sĩ sửa
// được. Danh mục gợi ý là NHÃN của tài liệu nguồn: dòng nào chưa gắn thuốc kho
// (`drug_catalog_id` trống) thì nói ra — chưa thu tiền, chưa cấp được — chứ
// không tự dò tên để gắn.
//
// Mỗi thuốc có ĐƠN GIÁ + THÀNH TIỀN do máy chủ trả (`don_gia`, `thanh_tien` — cùng
// hàm với hoá đơn); ĐVT là CHỮ khi kho có ĐVT (đơn vị mẹ, chưa khai mẹ thì gốc); nút
// "+ Thuốc ngoài danh mục" thêm dòng gõ tự do.

import { useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { INPUT } from "../../form-ui";
import ODonVi from "../../ODonVi";
import { useTinhCachDung } from "./useTinhCachDung";
import KyKinh, { type Kinh, type Moc } from "./KyKinh";
import { dongKetQua, type CachDungCT } from "@/lib/cach-dung";
import {
  dongNgoaiDanhMuc,
  dongTuMau,
  locMauThuoc,
  tienVn,
  type DongThuoc,
  type MauThuoc,
} from "@/lib/phieu-kham";
import { boTienCu } from "@/lib/tien-dong-thuoc";

// CÁCH DÙNG CẦN CHỖ (Tuyền 27/09/2026: "cho thêm không gian cho cách dùng
// thuốc"). Bảng sáu cột chia đều cắt "Uống 1 viên sau ăn sáng, 1 viên sau ăn
// tối, trong 7 ngày" còn vài chữ — và cột trái phiếu khám chỉ rộng ~600–780px
// nên bảng MỘT hàng không bao giờ đủ chỗ. Mỗi thuốc nay HAI hàng: trên là thuốc
// · đường dùng · số lượng · ĐVT · đơn giá; dưới là Cách dùng (⅔) + Lưu ý (⅓), ô
// nhiều dòng tự giãn theo chữ. Điện thoại: mọi ô xếp dọc.

/** Ô nhiều dòng tự giãn theo chữ (CSS field-sizing) — tối thiểu 2 dòng. */
const O_DAI = `${INPUT} min-h-16 resize-y [field-sizing:content] sm:min-h-16`;
/** Ô chữ (không gõ) cao bằng ô nhập ở cùng hàng. */
const O_CHU = "flex min-h-9 items-center text-body text-ink";
const NHAN = "block text-meta text-ink-muted";
/** Kinh lần cuối + chu kỳ: để trống = máy chủ lấy từ phiếu khám. */
const KINH_TU_PHIEU = { kinh_lan_cuoi: "", chu_ky: "" };

const bo = (x: string) => x.trim().toLowerCase();

/**
 * Tên thuốc GÕ TỰ DO: chỉ báo lên khi rời ô / Enter. Máy chủ tạo mục kho "chờ
 * duyệt" cho mỗi tên lạ (một kho thuốc, 24/09) — báo từng nhịp gõ thì mỗi lần
 * ngừng tay 1,5 giây đẻ một mục kho rác ("Vita", "Vitam"…).
 */
function OTenTuDo({ ten, disabled, onChot }: { ten: string; disabled: boolean; onChot: (v: string) => void }) {
  const [chu, setChu] = useState(ten);
  const chot = () => {
    if (chu.trim() !== ten.trim()) onChot(chu);
  };
  return (
    <input
      value={chu}
      disabled={disabled}
      placeholder="Tên thuốc"
      onChange={(e) => setChu(e.target.value)}
      onBlur={chot}
      onKeyDown={(e) => {
        if (e.key === "Enter") chot();
      }}
      className={INPUT}
    />
  );
}

export default function DonThuocPhieu({
  dong,
  mauThuoc,
  onDoi,
  ngoaiDanhMuc = true,
  tuKhoaDau,
  visitId,
}: {
  /** Có = màn bác sĩ: hiện cách dùng có cấu trúc + số ngày / ngày hết (PR E). */
  visitId?: string;
  dong: DongThuoc[];
  mauThuoc: MauThuoc[];
  /** Không truyền = chỉ đọc (hồ sơ đã chốt, hoặc chưa nối đường ghi đơn). */
  onDoi?: (dong: DongThuoc[]) => void;
  /** Cho thêm dòng gõ tự do. Quầy thu tắt: đơn bán chỉ nhận thuốc có trong kho. */
  ngoaiDanhMuc?: boolean;
  /** Mở sẵn danh mục với từ khoá này (quầy bán lẻ: chọn thuốc kho thay cho dòng đơn
   *  cũ chưa gắn thuốc kho). Đổi từ khoá = dựng lại component bằng `key`. */
  tuKhoaDau?: string;
}) {
  const [tu, setTu] = useState(tuKhoaDau ?? "");
  const [moDanhMuc, setMoDanhMuc] = useState(!!tuKhoaDau);
  // Ô chọn chỉ có thuốc đang có hàng ở kho / quầy của cơ sở (Tuyền 26/11). Thuốc khác
  // bác sĩ vẫn kê được bằng "+ Thuốc ngoài danh mục" như cũ.
  const coHang = useMemo(() => mauThuoc.filter((m) => m.con_hang), [mauThuoc]);
  const loc = useMemo(() => locMauThuoc(coHang, tu), [coHang, tu]);
  const chiDoc = !onDoi;

  const sua = (i: number, ma: keyof DongThuoc, v: string | CachDungCT | null) =>
    onDoi?.(dong.map((d, j) => (j === i ? boTienCu({ ...d, [ma]: v }, ma) : d)));
  // Số ngày dùng / ngày hết: máy chủ tính từ cách dùng của danh mục × số lượng bán
  // (Tuyền 26/11: bác sĩ không khai thêm gì). Lệch số dòng = chờ lượt hỏi sau.
  // Thuốc theo chu kỳ kinh: khung "Tính ngày uống theo kỳ kinh" (Tuyền 26/11). Đóng = không
  // gửi kỳ kinh, không hiện ngày (không bịa); mở = bác sĩ nhập/sửa kỳ kinh + mốc từng dòng.
  const [moKy, setMoKy] = useState(false);
  const [kinh, setKinh] = useState<Kinh>(KINH_TU_PHIEU);
  const [moc, setMoc] = useState<Record<number, Moc>>({});
  const tinh = useTinhCachDung(visitId, dong, moKy ? kinh : KINH_TU_PHIEU, moKy ? moc : {});
  const kqDong = tinh && tinh.dong.length === dong.length ? tinh.dong : null;
  const moKhungKy = (mo: boolean) => {
    if (mo && !kinh.kinh_lan_cuoi && tinh?.kinh.kinh_lan_cuoi) {
      setKinh({ kinh_lan_cuoi: tinh.kinh.kinh_lan_cuoi, chu_ky: tinh.kinh.chu_ky ?? "" });
    }
    setMoKy(mo);
  };

  const oNhap = (i: number, d: DongThuoc, ma: keyof DongThuoc, ten: string, lop: string, dai = false) => (
    <label key={ma} className={`${NHAN} ${lop}`}>
      {ten}
      {dai ? (
        <textarea
          rows={2}
          value={String(d[ma] ?? "")}
          disabled={chiDoc}
          onChange={(e) => sua(i, ma, e.target.value)}
          className={O_DAI}
        />
      ) : (
        <input
          value={String(d[ma] ?? "")}
          disabled={chiDoc}
          onChange={(e) => sua(i, ma, e.target.value)}
          className={INPUT}
        />
      )}
    </label>
  );

  return (
    <div className="space-y-3">
      {!chiDoc ? (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="secondary"
              aria-expanded={moDanhMuc}
              onClick={() => setMoDanhMuc(!moDanhMuc)}
            >
              Thuốc có ở kho / quầy ({coHang.length})
            </Button>
            {ngoaiDanhMuc ? (
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => onDoi?.([...dong, dongNgoaiDanhMuc()])}
              >
                + Thuốc ngoài danh mục
              </Button>
            ) : null}
          </div>
          {moDanhMuc ? (
            <div className="space-y-2 rounded-card border border-hairline p-3">
              <input
                type="search"
                value={tu}
                onChange={(e) => setTu(e.target.value)}
                placeholder="Tìm tên thuốc / đường dùng…"
                className={INPUT}
              />
              <ul className="grid max-h-64 grid-cols-1 gap-1 overflow-y-auto sm:grid-cols-2">
                {loc.map((m) => (
                  <li key={m.ma}>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="w-full"
                      onClick={() => onDoi?.([...dong, dongTuMau(m)])}
                    >
                      <span className="min-w-0 flex-1 truncate text-left font-medium text-ink">
                        {m.ten_kho || m.nhan_nguon}
                        <span className="ml-2 font-normal text-ink-muted">{m.type}</span>
                      </span>
                      {/* Tồn cơ sở + giá kho cạnh tên ("còn 3 hộp · 12.000 đ/hộp", 26/11). */}
                      <span className="shrink-0 tabular-nums text-ink-muted">
                        {m.ton_chu ? <span className={m.con_hang ? "text-success" : "text-ink-faint"}>{m.ton_chu} · </span> : null}
                        {m.drug_catalog_id && m.gia != null
                          ? `${tienVn(m.gia)}${m.unit ? `/${m.unit}` : ""}`
                          : "chưa có giá"}
                      </span>
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}

      {dong.length === 0 ? (
        <p className="text-body text-ink-faint">Chưa chọn thuốc.</p>
      ) : null}
      {dong.length > 0 ? (
        <ol className="space-y-2">
          {dong.map((d, i) => {
            const coKho = !!d.drug_catalog_id;
            // Tên KHOÁ chỉ khi là thuốc kho thật (có giá / ĐVT). Tên gõ tự do đã
            // lưu thì máy chủ gắn mục kho "chờ duyệt" (không giá) — vẫn sửa được.
            // Quầy thu (không cho thuốc ngoài danh mục) thì tên kho luôn khoá.
            const khoaTen = coKho && (!ngoaiDanhMuc || d.don_gia != null || !!d.dvt_kho);
            // ĐVT là CHỮ khi kho có ĐVT và dòng đang dùng đúng ĐVT ấy; đơn cũ
            // ghi ĐVT khác thì vẫn cho sửa (để bác sĩ chữa cho khớp kho).
            const dvtChu = !!d.dvt_kho && (!d.don_vi.trim() || bo(d.don_vi) === bo(d.dvt_kho));
            // Thuốc nhiều đơn vị bán: chọn đơn vị ngay ở dòng, giá theo đơn vị đó (máy
            // chủ trả sẵn trong danh mục). Thành tiền: máy chủ tính cho dòng đã lưu
            // (`thanh_tien`) — màn không nhân giá. Quầy luôn chọn được đơn vị.
            const mauKho = coKho ? mauThuoc.find((m) => m.drug_catalog_id === d.drug_catalog_id) : undefined;
            const cacDv = mauKho?.cac_don_vi ?? [];
            // "hộp (60 viên)": quy cách từ khối đơn vị con của Danh mục (Tuyền 26/11).
            const qc = mauKho?.quy_cach ? ` (${mauKho.quy_cach})` : "";
            const chonDv = !chiDoc && coKho && (cacDv.length > 1 || !ngoaiDanhMuc);
            const dv = cacDv.find((x) => bo(x.don_vi) === bo(d.don_vi));
            const giaDv = d.thanh_tien != null ? d.don_gia : (dv?.gia ?? d.don_gia);
            const tien = d.thanh_tien ?? null;
            return (
              <li
                key={`${d.mau_ma ?? "tu-do"}-${i}`}
                className="rounded-card border border-hairline bg-surface p-3"
              >
                <div className="mb-2 flex items-center gap-2">
                  <span className="grid size-6 shrink-0 place-items-center rounded-full bg-brand-50 text-meta font-semibold text-brand-700">
                    {i + 1}
                  </span>
                  {d.so_luong_do_thu_ngan ? (
                    <Chip
                      tone="brand"
                      title={
                        d.so_luong_ke_goc
                          ? `Bác sĩ kê ${d.so_luong_ke_goc} — quầy thu thuốc đã sửa lúc thu`
                          : "Bác sĩ để trống số lượng — quầy thu thuốc đã điền lúc thu"
                      }
                    >
                      {d.so_luong_ke_goc
                        ? `SL do thu ngân sửa (bác sĩ kê ${d.so_luong_ke_goc})`
                        : "SL do thu ngân điền"}
                    </Chip>
                  ) : null}
                  {!coKho ? (
                    d.mau_ma ? (
                      <Chip tone="warning">Chưa gắn thuốc kho</Chip>
                    ) : (
                      <Chip tone="neutral" title="Không có trong kho — quầy chưa thu / cấp được">
                        Ngoài danh mục
                      </Chip>
                    )
                  ) : null}
                  {!chiDoc ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="ml-auto"
                      onClick={() => onDoi?.(dong.filter((_, j) => j !== i))}
                    >
                      Bỏ thuốc này
                    </Button>
                  ) : null}
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-12">
                  {khoaTen ? (
                    // Thuốc kho: tên là của kho, không gõ lại (đổi thuốc = bỏ
                    // dòng, chọn thuốc khác).
                    <div className={`${NHAN} sm:col-span-4`}>
                      Thuốc
                      <p className={`${O_CHU} font-medium`}>{d.ten_thuoc}</p>
                    </div>
                  ) : (
                    <label className={`${NHAN} sm:col-span-4`}>
                      Thuốc
                      <OTenTuDo
                        key={d.ten_thuoc}
                        ten={d.ten_thuoc}
                        disabled={chiDoc}
                        // Đổi tên = bỏ mã kho cũ để máy chủ ghép lại theo tên mới.
                        onChot={(v) =>
                          onDoi?.(
                            dong.map((x, j) =>
                              j === i
                                ? { ...x, ten_thuoc: v, drug_catalog_id: null, don_gia: null, dvt_kho: null }
                                : x,
                            ),
                          )
                        }
                      />
                    </label>
                  )}
                  {oNhap(i, d, "duong_dung", "Đường dùng", "sm:col-span-2")}
                  {oNhap(i, d, "so_luong", "Số lượng", "sm:col-span-2")}
                  {chonDv ? (
                    <div className={`${NHAN} sm:col-span-2`}>
                      ĐVT
                      <ODonVi
                        value={d.don_vi}
                        onChange={(v) => sua(i, "don_vi", v)}
                        cuaThuoc={cacDv.map((x) => x.don_vi)}
                        ariaLabel={`Đơn vị ${d.ten_thuoc}`}
                      />
                      {qc && bo(d.don_vi || d.dvt_kho || "") === bo(d.dvt_kho || "") ? (
                        <span className="text-meta text-ink-muted">1 {d.dvt_kho}{qc.replace(/[()]/g, " = ")}</span>
                      ) : null}
                    </div>
                  ) : dvtChu ? (
                    <div className={`${NHAN} sm:col-span-2`}>
                      ĐVT
                      <p className={O_CHU}>
                        {d.dvt_kho}
                        {qc}
                      </p>
                    </div>
                  ) : (
                    oNhap(i, d, "don_vi", d.dvt_kho ? `ĐVT (kho: ${d.dvt_kho})` : "ĐVT", "sm:col-span-2")
                  )}
                  <div className={`${NHAN} sm:col-span-2 sm:text-right`}>
                    Đơn giá
                    <p className="flex min-h-9 flex-col justify-center tabular-nums">
                      {giaDv != null ? (
                        <>
                          <span className="text-body text-ink">{tienVn(giaDv)}</span>
                          {tien != null ? (
                            <span className="text-meta text-ink-muted">= {tienVn(tien)}</span>
                          ) : null}
                        </>
                      ) : (
                        <span className="text-body text-ink-faint">chưa có giá</span>
                      )}
                    </p>
                  </div>
                  {oNhap(i, d, "cach_dung", "Cách dùng", "sm:col-span-8", true)}
                  {oNhap(i, d, "luu_y", "Lưu ý", "sm:col-span-4", true)}
                  {visitId && coKho && (kqDong?.[i]?.theo_chu_ky || /kinh/i.test(d.cach_dung)) ? (
                    <KyKinh
                      mo={moKy}
                      onMo={moKhungKy}
                      kinh={kinh}
                      onKinh={setKinh}
                      moc={moc[i] ?? (kqDong?.[i]?.tu_ngay ? { tu_ngay: kqDong[i].tu_ngay!, den_ngay: kqDong[i].den_ngay! } : null)}
                      onMoc={(m) => setMoc({ ...moc, [i]: m })}
                      ngayKe={tinh?.ngay_ke ?? null}
                      ketQua={moKy && kqDong?.[i]?.uoc_tinh ? dongKetQua(kqDong[i]) : null}
                      chiDoc={chiDoc}
                    />
                  ) : visitId && coKho && kqDong?.[i]?.tinh_duoc ? (
                    <p className="text-meta text-success sm:col-span-12" role="status">
                      Đủ dùng {dongKetQua(kqDong[i])}
                    </p>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ol>
      ) : null}
    </div>
  );
}
