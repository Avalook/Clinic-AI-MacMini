interface KhoanCho {
  so_tien?: number; tong?: number; so_phieu?: number; so_luot?: number;
  so_khach?: number; pham_vi_loai?: string; bi_cat?: boolean;
  ds?: { id?: string; visit_id?: string; khach?: string; ma_bn?: string; so_tien?: number; luc?: string }[];
}

type Tien = { thu: number; huy: number; hoan: number; thuc_thu: number };

type TmCk = { tong: number; tien_mat: number; chuyen_khoan: number };

/** Khối Dòng tiền (14/10/2026) — mọi số do máy chủ tính (`tom_tat_tai_chinh_service`). */
export interface DongTien {
  dong_tien_vao: number;
  tien_thu: TmCk;
  tra_lai: TmCk;
  hoan_cho: number;
  /** Lần chờ CK đã huỷ trong kỳ (G4d, R1) — ghi chú, không cộng vào số nào. */
  ck_cho_da_huy?: { so_lan: number; tong: number };
  no: number;
  giam_gia: number;
  no_thu_duoc: TmCk & { giam_gia: number };
  thuc_thu: TmCk;
  doanh_thu_thuan: number;
  khop: boolean;
}

export interface TaiChinh {
 so_phieu_thu: number; doanh_thu: number; doanh_thu_thuan: number;
 thuc_thu: number; hoan_tien_mat: number; hoan_chuyen_khoan: number;
 giam_gia: number | null;
 dong_tien?: DongTien;
}

/** Bộ lọc đang xem — để link sang danh sách hoá đơn giữ đúng ngày / ca / cơ sở. */
export interface LocBaoCao { tu: string; den: string; ca?: string; co_so?: string }
interface DuLieuTomTat {
 tai_chinh?: TaiChinh;
  tong: Tien & { so_phieu_thu: number; so_phieu_huy: number; so_phieu_hoan: number };
  theo_hinh_thuc: (Tien & { ma: string; ten: string })[];
  /** Chuyển khoản tách theo tài khoản nhận (31/10/2026); cộng lại = dòng Chuyển khoản. */
  theo_tai_khoan?: (Tien & { id: string | null; ten: string })[];
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

/** Một mục Dòng tiền: số tổng, dòng phụ TM / CK (nếu có), link danh sách hoá đơn. */
function MucDongTien({ nhan, tong, tmCk, href, tien, noiBat = false }: {
  nhan: string; tong?: number; tmCk?: TmCk; href?: string;
  tien: (n?: number) => string; noiBat?: boolean;
}) {
  return (
    <div className="border-b border-hairline px-3 py-3 last:border-b-0">
      <div className="flex min-h-5 items-center justify-between gap-4">
        <dt className="min-w-0 text-emph text-ink">{nhan}</dt>
        <dd className={`shrink-0 text-right text-emph tabular-nums ${noiBat ? "font-semibold text-brand-700" : "text-ink"}`}>
          {tien(tong)}
        </dd>
      </div>
      {tmCk || href ? (
        <div className="mt-1 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-meta text-ink-muted">
          {tmCk ? <span className="tabular-nums">Tiền mặt {tien(tmCk.tien_mat)} · Chuyển khoản {tien(tmCk.chuyen_khoan)}</span> : <span />}
          {href ? <a href={href} className="text-brand-700 underline-offset-2 hover:underline print:hidden">Xem hoá đơn</a> : null}
        </div>
      ) : null}
    </div>
  );
}

function linkHoaDon(loc: LocBaoCao | undefined, nhom?: string): string | undefined {
  if (!loc) return undefined;
  const q = new URLSearchParams({ tu: loc.tu, den: loc.den });
  if (loc.ca) q.set("ca", loc.ca);
  if (loc.co_so) q.set("co_so", loc.co_so);
  if (nhom) q.set("nhom", nhom);
  return `/hoa-don?${q}`;
}

/** Khoản NỢ không có phiếu thu (khách ghi nợ chưa trả đồng nào) → danh sách phiếu
 *  rỗng; mở thẳng tab Việc tồn đã lọc đúng nhóm (G4a nối màn, 14/10/2026). */
function linkViecTon(loc: LocBaoCao | undefined, nhom: "no_khach" | "no_phong_kham"): string | undefined {
  if (!loc) return undefined;
  const q = new URLSearchParams({ tab: "viec-ton", viec: nhom });
  if (loc.co_so) q.set("co_so", loc.co_so);
  return `/hoa-don?${q}`;
}

function Nhom({ ten, children }: { ten: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="bg-surface-muted px-3 py-3 text-body font-medium text-ink-muted">{ten}</h3>
      <dl>{children}</dl>
    </section>
  );
}

export default function TomTatCuoiNgay({ data, dangTai, dayDu = false, loc }: {
  data: DuLieuTomTat | null; dangTai: boolean; dayDu?: boolean; loc?: LocBaoCao;
}) {
  const dt = data?.tai_chinh?.dong_tien;
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
        {hinhThuc.map(o => (
          <div key={o.ma}>
            <Dong nhan={o.ten} giaTri={tien("thuc_thu" in o ? o.thuc_thu : undefined)} />
            {o.ma === "TRANSFER" && (data?.theo_tai_khoan?.length ?? 0) > 0 ? (
              <ul aria-label="Chuyển khoản theo tài khoản" className="border-b border-hairline pb-2">
                {data?.theo_tai_khoan?.map(t => (
                  <li key={t.id ?? "chua"} className="flex items-center justify-between gap-4 px-3 py-1 pl-6 text-meta text-ink-muted">
                    <span className="min-w-0">{t.ten}</span>
                    <span className="shrink-0 tabular-nums">{tien(t.thuc_thu)}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ))}
      </Nhom>
      {dayDu ? <Nhom ten="Dòng tiền">
        {/* Thực thu = Dòng tiền vào − Trả lại − Nợ − Giảm giá + Nợ thu được (máy chủ tính). */}
        <MucDongTien nhan="Dòng tiền vào" tong={dt?.dong_tien_vao} tmCk={dt?.tien_thu} href={linkHoaDon(loc)} tien={tien} />
        <MucDongTien nhan="Trả lại tiền khách hàng" tong={dt?.tra_lai.tong} tmCk={dt?.tra_lai} href={linkHoaDon(loc, "tra_lai")} tien={tien} />
        <MucDongTien nhan="Nợ" tong={dt?.no} href={linkViecTon(loc, "no_khach")} tien={tien} />
        <MucDongTien nhan="Giảm giá" tong={dt?.giam_gia} href={linkHoaDon(loc, "giam_gia")} tien={tien} />
        <MucDongTien nhan="Nợ thu được" tong={dt?.no_thu_duoc.tong} tmCk={dt?.no_thu_duoc} tien={tien} />
        <MucDongTien nhan="Thực thu" tong={dt?.thuc_thu.tong} tmCk={dt?.thuc_thu} href={linkHoaDon(loc)} tien={tien} noiBat />
        <MucDongTien nhan="Doanh thu thuần" tong={dt?.doanh_thu_thuan} tien={tien} />
        {dt && dt.hoan_cho > 0 ? (
          <p className="px-3 py-2 text-meta text-ink-muted">Còn {tien(dt.hoan_cho)} hoàn tiền đang chờ — chưa trừ vào Trả lại.</p>
        ) : null}
        {dt?.ck_cho_da_huy && dt.ck_cho_da_huy.so_lan > 0 ? (
          <p className="px-3 py-2 text-meta text-ink-muted">
            {dt.ck_cho_da_huy.so_lan} lần chờ chuyển khoản đã huỷ ({tien(dt.ck_cho_da_huy.tong)}), không tính là đã thu.{" "}
            <a href={linkHoaDon(loc, "ck_da_huy")} className="text-brand-700 underline-offset-2 hover:underline print:hidden">Xem</a>
          </p>
        ) : null}
        {dt ? (
          <p className="px-3 py-2 text-meta text-ink-muted">
            <a href={linkHoaDon(loc, "khong_dung")} className="text-brand-700 underline-offset-2 hover:underline print:hidden">Xem hoá đơn không đúng (huỷ, trả lại, đổi hình thức, còn nợ…)</a>
          </p>
        ) : null}
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
