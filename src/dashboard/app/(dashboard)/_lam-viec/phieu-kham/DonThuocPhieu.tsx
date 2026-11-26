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
// Mỗi thuốc có ĐƠN GIÁ của kho (máy chủ trả — `don_gia`) + thành tiền DỰ TÍNH (chỉ
// hiển thị; quầy thu mới tính tiền); ĐVT là CHỮ khi kho có ĐVT.
//
// 26/11/2026 (kế hoạch đơn vị mẹ/con mục 12, 13): KHÔNG còn dòng gõ tự do — chỉ chọn
// thuốc trong danh mục. Máy chủ trả sẵn tồn của cơ sở ("còn 3 hộp" / "hết hàng"),
// thuốc còn hàng xếp trước, thuốc chưa có giá không chọn được. Tên lạ → `GoiYThuocLa`.

import { useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { INPUT } from "../../form-ui";
import ODonVi from "../../ODonVi";
import GoiYThuocLa from "./GoiYThuocLa";
import {
  dongTuMau,
  locMauThuoc,
  thanhTienDong,
  tienVn,
  type DongThuoc,
  type MauThuoc,
} from "@/lib/phieu-kham";

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

const bo = (x: string) => x.trim().toLowerCase();

export default function DonThuocPhieu({
  dong,
  mauThuoc,
  onDoi,
  ngoaiDanhMuc = true,
  tuKhoaDau,
}: {
  dong: DongThuoc[];
  mauThuoc: MauThuoc[];
  /** Không truyền = chỉ đọc (hồ sơ đã chốt, hoặc chưa nối đường ghi đơn). */
  onDoi?: (dong: DongThuoc[]) => void;
  /** Quầy thu tắt (false): ĐVT luôn chọn được — khách đòi mua hộp thì đổi được. */
  ngoaiDanhMuc?: boolean;
  /** Mở sẵn danh mục với từ khoá này (quầy bán lẻ: chọn thuốc kho thay cho dòng đơn
   *  cũ chưa gắn thuốc kho). Đổi từ khoá = dựng lại component bằng `key`. */
  tuKhoaDau?: string;
}) {
  const [tu, setTu] = useState(tuKhoaDau ?? "");
  const [moDanhMuc, setMoDanhMuc] = useState(!!tuKhoaDau);
  const loc = useMemo(() => locMauThuoc(mauThuoc, tu), [mauThuoc, tu]);
  const chiDoc = !onDoi;

  const sua = (i: number, ma: keyof DongThuoc, v: string) =>
    onDoi?.(dong.map((d, j) => (j === i ? { ...d, [ma]: v } : d)));

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
              Danh mục thuốc ({mauThuoc.length})
            </Button>
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
                      // Máy chủ quyết: chưa có giá thì không kê được (quầy không thu được).
                      disabled={m.chon_duoc === false}
                      title={m.ly_do_khong_chon ?? undefined}
                      onClick={() => onDoi?.([...dong, dongTuMau(m)])}
                    >
                      <span className="min-w-0 flex-1 truncate text-left font-medium text-ink">
                        {m.nhan_nguon}
                        <span className="ml-2 font-normal text-ink-muted">{m.type}</span>
                      </span>
                      {/* Tồn của cơ sở + giá kho cạnh tên ("còn 3 hộp · 12.000 đ/hộp"). */}
                      <span className="shrink-0 text-right tabular-nums text-meta">
                        {m.ton_chu ? (
                          <span className={m.con_hang ? "text-success" : "text-ink-faint"}>{m.ton_chu} · </span>
                        ) : null}
                        <span className="text-ink-muted">
                          {m.gia != null ? `${tienVn(m.gia)}${m.unit ? `/${m.unit}` : ""}` : "chưa có giá"}
                        </span>
                      </span>
                    </Button>
                  </li>
                ))}
              </ul>
              {loc.length === 0 ? (
                <GoiYThuocLa
                  ten={tu}
                  onChon={(ma) => {
                    const m = mauThuoc.find((x) => x.drug_catalog_id === ma);
                    if (m) onDoi?.([...dong, dongTuMau(m)]);
                  }}
                />
              ) : null}
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
            // ĐVT là CHỮ khi kho có ĐVT và dòng đang dùng đúng ĐVT ấy; đơn cũ
            // ghi ĐVT khác thì vẫn cho sửa (để bác sĩ chữa cho khớp kho).
            const dvtChu = !!d.dvt_kho && (!d.don_vi.trim() || bo(d.don_vi) === bo(d.dvt_kho));
            // Thuốc nhiều đơn vị bán: chọn đơn vị ngay ở dòng, giá theo đơn vị đó (máy
            // chủ trả sẵn trong danh mục; tiền thật vẫn do quầy thu tính). Quầy luôn
            // được chọn: khách đòi mua hộp thì gõ được.
            const cacDv = coKho
              ? (mauThuoc.find((m) => m.drug_catalog_id === d.drug_catalog_id)?.cac_don_vi ?? [])
              : [];
            const chonDv = !chiDoc && coKho && (cacDv.length > 1 || !ngoaiDanhMuc);
            const dv = cacDv.find((x) => bo(x.don_vi) === bo(d.don_vi));
            const giaDv = dv ? dv.gia : d.don_gia;
            const tien = thanhTienDong(dv ? { ...d, don_gia: dv.gia, dvt_kho: dv.don_vi } : d);
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
                  {/* Tên là của kho, không gõ lại (đổi thuốc = bỏ dòng, chọn thuốc khác). */}
                  <div className={`${NHAN} sm:col-span-4`}>
                    Thuốc
                    <p className={`${O_CHU} font-medium`}>{d.ten_thuoc}</p>
                  </div>
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
                    </div>
                  ) : dvtChu ? (
                    <div className={`${NHAN} sm:col-span-2`}>
                      ĐVT
                      <p className={O_CHU}>{d.dvt_kho}</p>
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
                </div>
              </li>
            );
          })}
        </ol>
      ) : null}
    </div>
  );
}
