"use client";

// HỒ SƠ MỘT LẦN KHÁM — xem trước ngay trong màn, và TẢI VỀ PDF (Tuyền 16/09/2026:
// *"cskh cũng phải có chỗ preview hồ sơ khám và tải về được bản pdf"*).
//
// Chỉ HIỂN THỊ thứ máy chủ trả về (/api/v1/cskh/ho-so-kham). Nhãn các trường
// phiếu khám lấy từ đúng schema mà bàn khám dùng để nhập (lib/form-schemas) —
// một nguồn nhãn duy nhất, không chép lại tên trường ở đây.
//
// PDF DỰNG TỪ CHÍNH KHUNG ĐANG XEM: thấy gì tải nấy. Chụp khung thành ảnh
// (html-to-image — trình duyệt tự vẽ nên đủ dấu tiếng Việt, không cần nhúng
// font) rồi cắt theo trang A4 (jspdf). Không thêm dịch vụ dựng PDF nào trên máy
// chủ. Kết quả CHƯA được bác sĩ duyệt vẫn in, nhưng mang nhãn "chờ bác sĩ duyệt"
// ngay cạnh — bản PDF không được trông như đã chốt khi chưa chốt.

import { useEffect, useRef, useState } from "react";
import { Download, FileImage, FileText, FileVideo, X } from "lucide-react";
import { getFormSchema } from "@/lib/form-schemas";
import type { FieldValue, FormField } from "@/lib/form-schemas/types";
import { nhanLoi, type ThanLoi } from "@/lib/loi-api";

interface HoSo {
  lich: {
    appointment_id: string;
    slot_start: string;
    status: string;
    dich_vu: string | null;
    bac_si: string | null;
    co_so: string | null;
    ma_bn: string | null;
    ten: string | null;
    ngay_sinh: string | null;
    nam_sinh: number | null;
    gioi_tinh: string | null;
    sdt: string | null;
    dia_chi: string | null;
    van_de_di_kham: string | null;
  };
  luot: {
    status: string;
    checked_in_at: string | null;
    exam_completed_at: string | null;
    bac_si_kham: string | null;
  } | null;
  sinh_hieu: Record<string, number | string | null> | null;
  phien_kham: {
    vong: number;
    loai: string;
    status: string;
    ket_luan: string | null;
    started_at: string | null;
    completed_at: string | null;
    bac_si: string | null;
  }[];
  phieu_kham: {
    form_code: string;
    form_data?: Record<string, FieldValue> | string | null;
    updated_at: string;
    nguoi_ghi: string | null;
    /** Phiếu khám v5 (29/09/2026): máy chủ đã dịch thành chữ theo khung. */
    v5?: boolean;
    ten?: string | null;
    muc?: { ten: string | null; dong: { ma: string; nhan: string; chu: string }[] }[];
  }[];
  chi_dinh: {
    id: string;
    ten: string | null;
    trang_thai: string;
    ket_qua: string | null;
    bac_si_danh_gia: string | null;
    ly_do_khong_lam: string | null;
    finished_at: string | null;
    ket_qua_luc: string | null;
    duyet_luc: string | null;
    nguoi_lam: string | null;
    nguoi_duyet: string | null;
  }[];
  tep: {
    id: string;
    ten_hien_thi: string | null;
    loai_tep: string;
    mime: string;
    so_byte: number;
    tai_len_luc: string;
    service_order_id: string | null;
    duoc_gui: boolean;
  }[];
  xet_nghiem: {
    ten: string;
    ket_qua: string | null;
    don_vi: string | null;
    thap: string | number | null;
    cao: string | number | null;
    co: string | null;
    cho_duyet: boolean;
  }[];
  don_thuoc: {
    ten_thuoc: string | null;
    cach_dung: string | null;
    so_luong: string | null;
    don_vi: string | null;
    ghi_chu_so_luong: string | null;
    luu_y: string | null;
  }[];
}

const TZ = "Asia/Ho_Chi_Minh";

function ngayGio(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("vi-VN", {
    timeZone: TZ,
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function ngay(iso: string | null | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso ?? "");
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "";
}

const TRANG_THAI_CHI_DINH: Record<string, string> = {
  authorized: "Đã duyệt, chờ làm",
  assigned: "Đã xếp phòng",
  in_progress: "Đang làm",
  performed: "Đã làm",
  not_performed: "Không làm được",
};

const SINH_HIEU: { khoa: string; nhan: string; don_vi?: string }[] = [
  { khoa: "huyet_ap", nhan: "Huyết áp", don_vi: "mmHg" },
  { khoa: "pulse", nhan: "Mạch", don_vi: "lần/phút" },
  { khoa: "temperature", nhan: "Nhiệt độ", don_vi: "°C" },
  { khoa: "respiratory_rate", nhan: "Nhịp thở", don_vi: "lần/phút" },
  { khoa: "spo2", nhan: "SpO₂", don_vi: "%" },
  { khoa: "weight_kg", nhan: "Cân nặng", don_vi: "kg" },
  { khoa: "height_cm", nhan: "Chiều cao", don_vi: "cm" },
  { khoa: "bmi", nhan: "BMI" },
  { khoa: "pain_score", nhan: "Thang đau", don_vi: "/10" },
];

function coGiaTri(v: FieldValue): boolean {
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === "boolean") return v;
  if (typeof v === "number") return true;
  return v != null && String(v).trim() !== "";
}

function chuGiaTri(f: FormField, v: FieldValue): string {
  const nhan = (x: string) => f.options?.find((o) => o.value === x)?.label ?? x;
  if (Array.isArray(v)) return v.map(nhan).join(", ");
  if (typeof v === "boolean") return v ? "Có" : "Không";
  if (f.type === "radio" && typeof v === "string") return nhan(v);
  if (f.type === "date" && typeof v === "string") return ngay(v) || v;
  return `${String(v)}${f.unit ? ` ${f.unit}` : ""}`;
}

/** Phiếu v5: chỉ VẼ các mục chữ máy chủ gửi — nhãn, lựa chọn đã theo khung. */
function PhieuKhamV5({ p }: { p: HoSo["phieu_kham"][number] }) {
  const muc = p.muc ?? [];
  return (
    <div className="space-y-2">
      <p className="text-label text-ink-muted">
        {p.ten ?? `Phiếu ${p.form_code}`} · ghi lúc {ngayGio(p.updated_at)}
        {p.nguoi_ghi ? ` · ${p.nguoi_ghi}` : ""}
      </p>
      {muc.length === 0 ? (
        <p className="text-sm italic text-ink-muted">Phiếu chưa điền nội dung.</p>
      ) : null}
      {muc.map((m, i) => (
        <div key={`${m.ten ?? ""}-${i}`}>
          {m.ten ? (
            <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-soft">{m.ten}</h4>
          ) : null}
          <dl className="mt-1 grid gap-x-4 gap-y-1 sm:grid-cols-2">
            {m.dong.map((d) => (
              <div key={d.ma} className="min-w-0">
                <dt className="text-label text-ink-muted">{d.nhan}</dt>
                <dd className="whitespace-pre-wrap break-words text-sm text-ink">{d.chu}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
    </div>
  );
}

function PhieuKham({ p }: { p: HoSo["phieu_kham"][number] }) {
  if (p.v5) return <PhieuKhamV5 p={p} />;
  const data: Record<string, FieldValue> =
    typeof p.form_data === "string"
      ? (JSON.parse(p.form_data) as Record<string, FieldValue>)
      : (p.form_data ?? {});
  const schema = getFormSchema(p.form_code);
  const daDung = new Set<string>();
  const phan = (schema?.sections ?? [])
    .map((s) => ({
      title: s.title,
      dong: s.fields
        .filter((f) => coGiaTri(data[f.key]))
        .map((f) => {
          daDung.add(f.key);
          return { nhan: f.label, chu: chuGiaTri(f, data[f.key]) };
        }),
    }))
    .filter((s) => s.dong.length > 0);
  // Trường không có trong schema hiện hành (schema đổi sau khi ghi): vẫn in,
  // không được lặng lẽ bỏ bớt nội dung hồ sơ.
  const conLai = Object.entries(data).filter(
    ([k, v]) => !daDung.has(k) && coGiaTri(v),
  );
  return (
    <div className="space-y-2">
      <p className="text-label text-ink-muted">
        {schema?.title ?? `Phiếu ${p.form_code}`} · ghi lúc {ngayGio(p.updated_at)}
        {p.nguoi_ghi ? ` · ${p.nguoi_ghi}` : ""}
      </p>
      {phan.length === 0 && conLai.length === 0 ? (
        <p className="text-sm italic text-ink-muted">Phiếu chưa điền nội dung.</p>
      ) : null}
      {phan.map((s) => (
        <div key={s.title}>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-soft">
            {s.title}
          </h4>
          <dl className="mt-1 grid gap-x-4 gap-y-1 sm:grid-cols-2">
            {s.dong.map((d) => (
              <div key={d.nhan} className="min-w-0">
                <dt className="text-label text-ink-muted">{d.nhan}</dt>
                <dd className="whitespace-pre-wrap break-words text-sm text-ink">{d.chu}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
      {conLai.length > 0 ? (
        <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-2">
          {conLai.map(([k, v]) => (
            <div key={k} className="min-w-0">
              <dt className="text-label text-ink-muted">{k}</dt>
              <dd className="whitespace-pre-wrap break-words text-sm text-ink">
                {Array.isArray(v) ? v.join(", ") : String(v)}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}

function Muc({ tieuDe, children }: { tieuDe: string; children: React.ReactNode }) {
  return (
    <section className="break-inside-avoid border-t border-line pt-3">
      <h3 className="mb-2 text-sm font-bold text-ink">{tieuDe}</h3>
      {children}
    </section>
  );
}

function NhanCho({ chu }: { chu: string }) {
  return (
    <span className="ml-1 rounded-chip bg-warning-bg px-1.5 py-0.5 text-label font-semibold text-warning">
      {chu}
    </span>
  );
}

const BIEU_TUONG = { ANH: FileImage, VIDEO: FileVideo } as const;

export function NoiDungHoSo({ hs }: { hs: HoSo }) {
  const l = hs.lich;
  const sh = hs.sinh_hieu;
  const dongSinhHieu = sh
    ? SINH_HIEU.map((m) => {
        const v =
          m.khoa === "huyet_ap"
            ? sh.systolic != null && sh.diastolic != null
              ? `${sh.systolic}/${sh.diastolic}`
              : null
            : sh[m.khoa];
        return v == null || v === "" ? null : { ...m, v: String(v) };
      }).filter((x): x is NonNullable<typeof x> => x !== null)
    : [];
  const anh = hs.tep.filter((t) => t.loai_tep === "ANH");

  return (
    <div className="space-y-3 bg-surface p-5 text-ink">
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-label font-semibold uppercase tracking-wide text-brand-700">
            Dr4Women{l.co_so ? ` · ${l.co_so}` : ""}
          </p>
          <h2 className="text-lg font-bold">Hồ sơ khám bệnh</h2>
        </div>
        <p className="text-right text-label text-ink-muted">
          Lịch khám {ngayGio(l.slot_start)}
          <br />
          In lúc {ngayGio(new Date().toISOString())}
        </p>
      </header>

      <Muc tieuDe="Thông tin khách hàng">
        <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
          <div><dt className="text-label text-ink-muted">Họ tên</dt><dd className="font-semibold">{l.ten ?? "—"}</dd></div>
          <div><dt className="text-label text-ink-muted">Mã khách</dt><dd>{l.ma_bn ?? "—"}</dd></div>
          <div><dt className="text-label text-ink-muted">Ngày sinh / năm sinh</dt><dd>{ngay(l.ngay_sinh) || l.nam_sinh || "—"}</dd></div>
          <div><dt className="text-label text-ink-muted">Giới tính</dt><dd>{l.gioi_tinh ?? "—"}</dd></div>
          <div><dt className="text-label text-ink-muted">Điện thoại</dt><dd>{l.sdt ?? "—"}</dd></div>
          <div><dt className="text-label text-ink-muted">Địa chỉ</dt><dd>{l.dia_chi ?? "—"}</dd></div>
          <div><dt className="text-label text-ink-muted">Dịch vụ khám</dt><dd>{l.dich_vu ?? "—"}</dd></div>
          <div><dt className="text-label text-ink-muted">Bác sĩ</dt><dd>{hs.luot?.bac_si_kham ?? l.bac_si ?? "—"}</dd></div>
          {l.van_de_di_kham ? (
            <div className="sm:col-span-2"><dt className="text-label text-ink-muted">Vấn đề đi khám</dt><dd className="whitespace-pre-wrap">{l.van_de_di_kham}</dd></div>
          ) : null}
        </dl>
        {hs.luot ? (
          <p className="mt-2 text-label text-ink-muted">
            Check-in {ngayGio(hs.luot.checked_in_at)}
            {hs.luot.exam_completed_at ? ` · khám xong ${ngayGio(hs.luot.exam_completed_at)}` : ""}
          </p>
        ) : (
          <p className="mt-2 text-sm italic text-ink-muted">Lịch này chưa check-in — chưa có lượt khám.</p>
        )}
      </Muc>

      {dongSinhHieu.length > 0 ? (
        <Muc tieuDe="Sinh hiệu">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-4">
            {dongSinhHieu.map((d) => (
              <div key={d.khoa}>
                <dt className="text-label text-ink-muted">{d.nhan}</dt>
                <dd className="font-semibold">{d.v}{d.don_vi ? ` ${d.don_vi}` : ""}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-1 text-label text-ink-muted">
            Đo lúc {ngayGio(sh?.created_at as string | null)}
            {sh?.nguoi_do ? ` · ${sh.nguoi_do}` : ""}
            {/* Số đo của lượt khác cùng buổi — nhãn do máy chủ trả (29/09/2026). */}
            {sh?.nguon ? ` · ${sh.nguon}` : ""}
          </p>
        </Muc>
      ) : null}

      <Muc tieuDe="Phiếu khám">
        {hs.phieu_kham.length === 0 ? (
          <p className="text-sm italic text-ink-muted">Chưa có phiếu khám nào được ghi.</p>
        ) : (
          <div className="space-y-4">
            {hs.phieu_kham.map((p) => (
              <PhieuKham key={`${p.form_code}-${p.updated_at}`} p={p} />
            ))}
          </div>
        )}
      </Muc>

      {hs.chi_dinh.length > 0 ? (
        <Muc tieuDe="Chỉ định và kết quả">
          <ul className="space-y-2">
            {hs.chi_dinh.map((c) => {
              const cuaNo = hs.tep.filter((t) => t.service_order_id === c.id);
              const coKetQua = Boolean(c.ket_qua || c.ket_qua_luc || cuaNo.length);
              return (
                <li key={c.id} className="rounded-control border border-line p-2">
                  <p className="text-sm font-semibold">
                    {c.ten ?? "Chỉ định"}
                    <span className="ml-2 text-label font-normal text-ink-muted">
                      {TRANG_THAI_CHI_DINH[c.trang_thai] ?? c.trang_thai}
                      {c.nguoi_lam ? ` · ${c.nguoi_lam}` : ""}
                    </span>
                    {coKetQua && !c.duyet_luc ? <NhanCho chu="Chờ bác sĩ duyệt" /> : null}
                  </p>
                  {c.ket_qua ? (
                    <p className="mt-1 whitespace-pre-wrap text-sm">{c.ket_qua}</p>
                  ) : null}
                  {c.ly_do_khong_lam ? (
                    <p className="mt-1 text-sm text-danger">Không làm được: {c.ly_do_khong_lam}</p>
                  ) : null}
                  {c.bac_si_danh_gia ? (
                    <p className="mt-1 whitespace-pre-wrap text-sm">
                      <span className="font-semibold">Bác sĩ đánh giá: </span>
                      {c.bac_si_danh_gia}
                    </p>
                  ) : null}
                  {c.duyet_luc ? (
                    <p className="mt-1 text-label text-success">
                      Bác sĩ đã duyệt {ngayGio(c.duyet_luc)}
                      {c.nguoi_duyet ? ` · ${c.nguoi_duyet}` : ""}
                    </p>
                  ) : null}
                  {cuaNo.length > 0 ? (
                    <p className="mt-1 text-label text-ink-muted">
                      Tệp kết quả: {cuaNo.map((t) => t.ten_hien_thi ?? t.loai_tep).join(", ")}
                    </p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </Muc>
      ) : null}

      {hs.xet_nghiem.length > 0 ? (
        <Muc tieuDe="Xét nghiệm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-label text-ink-muted">
                  <th className="py-1 pr-2">Xét nghiệm</th>
                  <th className="py-1 pr-2">Kết quả</th>
                  <th className="py-1 pr-2">Tham chiếu</th>
                </tr>
              </thead>
              <tbody>
                {hs.xet_nghiem.map((x, i) => (
                  <tr key={`${x.ten}-${i}`} className="border-t border-line">
                    <td className="py-1 pr-2">{x.ten}</td>
                    <td className="py-1 pr-2 font-semibold">
                      {x.ket_qua ?? "—"}
                      {x.don_vi ? ` ${x.don_vi}` : ""}
                      {x.co && x.co !== "NORMAL" ? ` [${x.co}]` : ""}
                      {x.cho_duyet ? <NhanCho chu="Chờ bác sĩ duyệt" /> : null}
                    </td>
                    <td className="py-1 pr-2 text-ink-muted">
                      {x.thap != null || x.cao != null ? `${x.thap ?? ""} – ${x.cao ?? ""}` : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Muc>
      ) : null}

      {hs.don_thuoc.length > 0 ? (
        <Muc tieuDe="Đơn thuốc">
          <ol className="list-decimal space-y-1 pl-5 text-sm">
            {hs.don_thuoc.map((t, i) => (
              <li key={`${t.ten_thuoc}-${i}`}>
                <span className="font-semibold">{t.ten_thuoc ?? "—"}</span>
                {t.so_luong ? ` · SL ${t.so_luong}${t.don_vi ? ` ${t.don_vi}` : ""}` : ""}
                {t.ghi_chu_so_luong ? ` (${t.ghi_chu_so_luong})` : ""}
                {t.cach_dung ? <span className="block text-ink-soft">{t.cach_dung}</span> : null}
                {t.luu_y ? <span className="block text-warning">Lưu ý: {t.luu_y}</span> : null}
              </li>
            ))}
          </ol>
        </Muc>
      ) : null}

      {hs.tep.length > 0 ? (
        <Muc tieuDe="Tệp kết quả">
          {anh.length > 0 ? (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {anh.map((t) => (
                <figure key={t.id} className="break-inside-avoid">
                  {/* eslint-disable-next-line @next/next/no-img-element -- ảnh qua cửa đã xác thực, không qua bộ tối ưu ảnh */}
                  <img
                    src={`/api/cskh/ket-qua/${t.id}/noi-dung`}
                    alt={t.ten_hien_thi ?? "Ảnh kết quả"}
                    className="aspect-square w-full rounded-control border border-line object-contain"
                  />
                  <figcaption className="truncate text-label text-ink-muted">
                    {t.ten_hien_thi ?? "Ảnh"}
                    {!t.duoc_gui ? " · chưa được phép gửi" : ""}
                  </figcaption>
                </figure>
              ))}
            </div>
          ) : null}
          <ul className="mt-2 space-y-0.5 text-sm">
            {hs.tep
              .filter((t) => t.loai_tep !== "ANH")
              .map((t) => {
                const Icon = BIEU_TUONG[t.loai_tep as keyof typeof BIEU_TUONG] ?? FileText;
                return (
                  <li key={t.id} className="flex items-center gap-1.5">
                    <Icon className="size-4 shrink-0 text-ink-muted" aria-hidden />
                    <a
                      href={`/api/cskh/ket-qua/${t.id}/noi-dung`}
                      target="_blank"
                      rel="noreferrer"
                      className="truncate text-brand-700 underline"
                    >
                      {t.ten_hien_thi ?? t.loai_tep}
                    </a>
                    {!t.duoc_gui ? <NhanCho chu="Chưa được phép gửi" /> : null}
                  </li>
                );
              })}
          </ul>
        </Muc>
      ) : null}
    </div>
  );
}

async function taiPdf(khung: HTMLElement, tenTep: string): Promise<void> {
  const [{ toCanvas }, { jsPDF }] = await Promise.all([
    import("html-to-image"),
    import("jspdf"),
  ]);
  const canvas = await toCanvas(khung, {
    pixelRatio: 2,
    backgroundColor: "#ffffff",
    cacheBust: true,
  });
  const pdf = new jsPDF({ unit: "mm", format: "a4", orientation: "portrait" });
  const le = 8;
  const rong = 210 - le * 2;
  const cao = 297 - le * 2;
  // Cắt canvas theo chiều cao một trang A4 (đổi mm → px theo tỉ lệ bề ngang).
  const pxMoiMm = canvas.width / rong;
  const caoTrangPx = Math.floor(cao * pxMoiMm);
  for (let y = 0, trang = 0; y < canvas.height; y += caoTrangPx, trang += 1) {
    const h = Math.min(caoTrangPx, canvas.height - y);
    const lat = document.createElement("canvas");
    lat.width = canvas.width;
    lat.height = h;
    lat.getContext("2d")?.drawImage(canvas, 0, y, canvas.width, h, 0, 0, canvas.width, h);
    if (trang > 0) pdf.addPage();
    pdf.addImage(lat.toDataURL("image/jpeg", 0.92), "JPEG", le, le, rong, h / pxMoiMm);
  }
  pdf.save(tenTep);
}

function tenTepPdf(hs: HoSo): string {
  const khongDau = (hs.lich.ten ?? "khach")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .replace(/[^A-Za-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(hs.lich.slot_start ?? "");
  return `ho-so-kham_${khongDau || "khach"}_${m ? `${m[3]}${m[2]}${m[1]}` : ""}.pdf`;
}

/** Khung xem hồ sơ nổi trên màn (mở từ lịch sử các lần khám). */
export default function HoSoKhamModal({
  appointmentId,
  onDong,
}: {
  appointmentId: string;
  onDong: () => void;
}) {
  const [hs, setHs] = useState<HoSo | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangTai, setDangTai] = useState(false);
  const khung = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let huy = false;
    void fetch(`/api/cskh/ho-so-kham/${encodeURIComponent(appointmentId)}`, {
      cache: "no-store",
    })
      .then(async (r) => {
        const d = (await r.json().catch(() => null)) as unknown;
        if (huy) return;
        if (!r.ok) {
          setLoi(nhanLoi(d as ThanLoi | null, "Không đọc được hồ sơ khám."));
          return;
        }
        setHs(d as HoSo);
      })
      .catch(() => {
        if (!huy) setLoi("Mất kết nối tới máy chủ.");
      });
    return () => {
      huy = true;
    };
  }, [appointmentId]);

  useEffect(() => {
    const phim = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDong();
    };
    window.addEventListener("keydown", phim);
    return () => window.removeEventListener("keydown", phim);
  }, [onDong]);

  async function bamTai() {
    if (!hs || !khung.current) return;
    setDangTai(true);
    setLoi(null);
    try {
      await taiPdf(khung.current, tenTepPdf(hs));
    } catch {
      setLoi("Không dựng được PDF — thử lại, hoặc báo kỹ thuật nếu lặp lại.");
    } finally {
      setDangTai(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Hồ sơ khám"
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 px-4 py-6"
      onClick={onDong}
    >
      <div
        className="w-full max-w-3xl rounded-card bg-surface shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex items-center justify-between gap-2 rounded-t-card border-b border-line bg-surface px-4 py-2">
          <h2 className="text-sm font-semibold text-ink">Xem trước hồ sơ khám</h2>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void bamTai()}
              disabled={!hs || dangTai}
              className="inline-flex items-center gap-1.5 rounded-control bg-brand-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
            >
              <Download className="size-4" aria-hidden />
              {dangTai ? "Đang dựng PDF…" : "Tải PDF"}
            </button>
            <button
              type="button"
              onClick={onDong}
              aria-label="Đóng"
              className="rounded-control p-1.5 text-ink-muted hover:bg-surface-muted"
            >
              <X className="size-5" aria-hidden />
            </button>
          </div>
        </div>
        {loi ? <p className="px-4 py-3 text-sm text-danger">{loi}</p> : null}
        {!hs && !loi ? (
          <p className="px-4 py-6 text-sm text-ink-muted">Đang mở hồ sơ…</p>
        ) : null}
        {hs ? (
          <div ref={khung}>
            <NoiDungHoSo hs={hs} />
          </div>
        ) : null}
      </div>
    </div>
  );
}
