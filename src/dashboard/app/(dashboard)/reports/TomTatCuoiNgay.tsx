interface KhoanCho {
  so_tien?: number; tong?: number; so_phieu?: number; so_luot?: number;
  so_khach?: number; pham_vi_loai?: string; bi_cat?: boolean;
  ds?: { id?: string; visit_id?: string; khach?: string; ma_bn?: string; so_tien?: number; luc?: string }[];
}

type Tien = { thu: number; huy: number; hoan: number; thuc_thu: number };

export interface TaiChinh {
 so_phieu_thu: number; doanh_thu: number; doanh_thu_thuan: number;
 thuc_thu: number; hoan_tien_mat: number; hoan_chuyen_khoan: number;
 no_chua_thu: number | null; giam_gia: number | null;
}
interface DuLieuTomTat {
 tai_chinh?: TaiChinh;
  tong: Tien & { so_phieu_thu: number; so_phieu_huy: number; so_phieu_hoan: number };
  theo_hinh_thuc: (Tien & { ma: string; ten: string })[];
  theo_loai: (Tien & { ma: string; ten: string })[];
  khach: { so_luot_kham: number; so_luot_da_thu: number; so_khach_da_thu: number };
  can_xu_ly?: {
    tinh_den: string; pham_vi: string;
    cho_xac_minh: KhoanCho; hoan_cho: KhoanCho;
    tien_thua: KhoanCho; khach_con_no: KhoanCho;
  };
}

function Dong({ nhan, giaTri, noiBat = false }: {
  nhan: string; giaTri: string; noiBat?: boolean;
}) {
  return (
    <div className="flex min-h-11 items-center justify-between gap-4 border-b border-hairline px-3 py-3 last:border-b-0">
      <dt className="min-w-0 text-emph text-ink">{nhan}</dt>
      <dd className={`shrink-0 text-right text-emph tabular-nums ${noiBat ? "font-semibold text-brand-700" : "text-ink"}`}>
        {giaTri}
      </dd>
    </div>
  );
}

function Nhom({ ten, children }: { ten: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="bg-surface-muted px-3 py-3 text-body font-medium text-ink-muted">{ten}</h3>
      <dl>{children}</dl>
    </section>
  );
}

export default function TomTatCuoiNgay({ data, dangTai, dayDu = false }: {
  data: DuLieuTomTat | null; dangTai: boolean; dayDu?: boolean;
}) {
  const tien = (n?: number) => n == null ? (dangTai ? "…" : "—") : `${n.toLocaleString("vi-VN")}đ`;
  // Chỉ trình bày các nhóm máy chủ trả về; thiếu dữ liệu thì không giả thành 0.
  const hinhThuc = data?.theo_hinh_thuc.length
    ? data.theo_hinh_thuc
    : [{ ma: "CASH", ten: "Tiền mặt" }, { ma: "TRANSFER", ten: "Chuyển khoản" }];
  return (
    <section aria-label="Tóm tắt báo cáo cuối ngày" aria-busy={dangTai} className="bg-surface">
      {dangTai ? <p role="status" className="px-3 py-2 text-meta text-ink-muted">Đang tải báo cáo…</p> : null}
      <Nhom ten="Tổng kết thu">
        <Dong nhan="Tổng thu" giaTri={tien(data?.tong.thuc_thu)} noiBat />
        {(["dich_vu", "thuoc"] as const).map(ma => {
          const nhom = data?.theo_loai.find(o => o.ma === ma);
          return <Dong key={ma} nhan={ma === "dich_vu" ? "Dịch vụ" : "Thuốc / vật tư"} giaTri={tien(nhom?.thuc_thu)} />;
        })}
      </Nhom>
      <Nhom ten="Phương thức thanh toán">
        {hinhThuc.map(o => <Dong key={o.ma} nhan={o.ten} giaTri={tien("thuc_thu" in o ? o.thuc_thu : undefined)} />)}
      </Nhom>
      {dayDu ? <Nhom ten="Tài chính">
        <Dong nhan="Doanh thu" giaTri={tien(data?.tai_chinh?.doanh_thu)} />
        <Dong nhan="Hoàn tiền mặt" giaTri={tien(data?.tai_chinh?.hoan_tien_mat)} />
        <Dong nhan="Hoàn chuyển khoản" giaTri={tien(data?.tai_chinh?.hoan_chuyen_khoan)} />
        <Dong nhan="Nợ chưa thu trong kỳ" giaTri={tien(data?.tai_chinh?.no_chua_thu ?? undefined)} />
        <Dong nhan="Giảm giá (đã trừ vào doanh thu)" giaTri={data?.tai_chinh?.giam_gia == null ? "Chưa có dữ liệu" : tien(data.tai_chinh.giam_gia)} />
        <Dong nhan="Doanh thu thuần" giaTri={tien(data?.tai_chinh?.doanh_thu_thuan)} />
      </Nhom> : null}
      <Nhom ten="Phiếu thu">
        <Dong nhan="Phiếu thu" giaTri={data?.tong.so_phieu_thu == null ? dangTai ? "…" : "—" : data.tong.so_phieu_thu.toLocaleString("vi-VN")} />
      </Nhom>


      {data && data.tong.so_phieu_thu === 0 && data.tong.thu === 0 && data.tong.huy === 0 && data.tong.hoan === 0 ? (
        <p className="px-3 pb-3 text-body text-ink-muted">Chưa có khoản thu trong khoảng đã chọn.</p>
      ) : null}
    </section>
  );
}
