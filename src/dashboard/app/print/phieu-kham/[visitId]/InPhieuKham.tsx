"use client";

// Bản in phiếu khám v5 — CHỈ ĐỌC, chữ thường thay cho ô nhập (ô nhập bị khoá in
// ra mờ và cắt chữ đoạn văn dài). Khung, nhãn, giá trị lấy nguyên từ máy chủ.
//
// ĐẦU TRANG (27/09/2026 — Y HỆT bản mẫu `manIn`): HAI BÊN (trái phòng khám +
// cơ sở + địa chỉ; phải tên phiếu, mã khách, Booking / Check-in, ngày khám), rồi
// khối BỆNH NHÂN gọn (họ tên, năm sinh + tuổi, giới, SĐT, địa chỉ) và MỘT dòng
// sinh hiệu. Trước đó in lại cả dải hành chính dài của màn khám (CCCD, dân tộc,
// nghề nghiệp…). Chân ký có TÊN bác sĩ của lượt.
//
// LÁT 5 (26/09/2026 — bản giao diện mẫu Tuyền duyệt): A4 (KieuInA4), ẨN ô /
// nhóm / mục trống (trước in "—" cho từng ô, một phiếu vài chục dòng gạch) và
// KHÔNG in khối tư vấn.
//
// HAI TRANG, BA MỤC (Tuyền 27/09/2026: "cấu trúc thành 2 trang, một trang in
// ảnh và một trang in thông tin … tách thành 3 mục: Tóm tắt bệnh án, Đơn
// thuốc, và kết quả cận lâm sàng (hiển thị luôn ảnh)"):
//   TRANG THÔNG TIN — I. Tóm tắt bệnh án (mọi mục của phiếu trừ danh sách CLS
//     và đơn thuốc: khám, chẩn đoán, thủ thuật, hẹn…) · II. Đơn thuốc ·
//     III. Kết quả cận lâm sàng (từng chỉ định: số đo + KẾT LUẬN).
//   TRANG ẢNH — ảnh kết quả CLS theo từng chỉ định, 2 ảnh / hàng cho đủ to để
//     đọc (ảnh chưa xác nhận / bị từ chối / thu hồi KHÔNG in). Không có ảnh thì
//     không in trang này.
// Mở từ [In phiếu khám] ở phiếu khám VÀ ở Xem lượt (mọi khâu).
//
// 28/09/2026 (Tuyền: "tách thành 3 mục in" — chọn 3 NÚT IN RIÊNG; ảnh CLS "3
// loại: kết quả có ảnh · kết quả không thôi · ảnh không thôi"): đầu trang có
// [In cả phiếu] · [In tóm tắt bệnh án] · [In đơn thuốc] · [In KQ CLS + ảnh] ·
// [In KQ CLS] · [In ảnh CLS]. Mỗi phần in riêng vẫn có đủ đầu trang + bệnh nhân
// (giấy rời vẫn biết của ai). Màn xem trước luôn hiện cả phiếu. Mọi khâu mở
// cùng trang này nên nút có ở mọi khâu.

import { useEffect, useState, type ReactNode } from "react";

import Button from "@/components/ui/Button";
import {
  NHAN_KET_QUA,
  anhInDuoc,
  coNhap,
  dongKetQua,
  dongTuDon,
  giaTriDoc,
  gomNhom,
  hienThi,
  type ChiDinhVaKetQua,
  type DauPhieu,
  type DinhNghiaPhieu,
  type DonViVe,
  type DongDonMayChu,
  type MucPhieu,
  type ONhap,
  type ThuThuatNguon,
} from "@/lib/phieu-kham";

import { duongXemTep } from "../../../(dashboard)/_lam-viec/AnhKetQua";
import { DauTrangIn, KhoiBenhNhanIn, dongSoLuot, ngayIn } from "../../KhoiIn";
import KieuInA4 from "../../KieuInA4";

/** Phần đang in: cả phiếu · một mục · kết quả CLS theo 3 kiểu ảnh. */
export type PhanIn = "ca" | "tom_tat" | "don" | "cls_kem" | "cls" | "cls_anh";

const TIEU_DE_PHAN: Partial<Record<PhanIn, string>> = {
  tom_tat: "Tóm tắt bệnh án",
  don: "Đơn thuốc",
  cls_kem: "Kết quả cận lâm sàng",
  cls: "Kết quả cận lâm sàng",
  cls_anh: "Hình ảnh cận lâm sàng",
};

interface PhieuLuot extends DinhNghiaPhieu {
  du_lieu: Record<string, ONhap>;
}

interface DuLieuIn {
  phieu: PhieuLuot;
  dau: DauPhieu | null;
  chiDinh: ChiDinhVaKetQua[];
  don: DongDonMayChu[];
  maThuThuat: Set<string>;
}

async function doc<T>(url: string): Promise<T | null> {
  const r = await fetch(url, { cache: "no-store" }).catch(() => null);
  if (!r || !r.ok) return null;
  return (await r.json().catch(() => null)) as T | null;
}

/** Các ô CÓ dữ liệu của một mục — không còn gì thì trả null (ẩn cả mục). */
function KhoiO({ m, duLieu }: { m: MucPhieu; duLieu: Record<string, ONhap> }) {
  const nhom = gomNhom(m.block)
    .map((n) => ({
      ...n,
      don_vi: n.don_vi.flatMap((d): DonViVe[] => {
        if (d.loai === "o") return coNhap(duLieu[d.o.ma]) ? [d] : [];
        const hang = d.hang.filter((h) => h.o.some((o) => o && coNhap(duLieu[o.ma])));
        return hang.length ? [{ ...d, hang }] : [];
      }),
    }))
    .filter((n) => n.don_vi.length > 0);
  if (nhom.length === 0) return null;
  return (
    <dl className="space-y-1">
      {nhom.map((n, i) => (
        <div key={`${m.ma}-${i}`} className="space-y-1">
          {n.tieu_de ? <p className="font-semibold text-ink">{n.tieu_de}</p> : null}
          {n.don_vi.map((d) =>
            d.loai === "o" ? (
              <div
                key={d.o.ma}
                className="in-giu grid grid-cols-[minmax(0,14rem)_minmax(0,1fr)] gap-2"
              >
                <dt className="text-ink-muted">{d.o.ten}</dt>
                <dd className="whitespace-pre-wrap">{giaTriDoc(d.o, duLieu[d.o.ma])}</dd>
              </div>
            ) : (
              <table key={d.bang.ma} className="w-full border-collapse text-body">
                <caption className="text-left font-semibold text-ink">{d.bang.ten}</caption>
                <thead>
                  <tr>
                    <th className="border border-line p-1 text-left" />
                    {d.bang.cot.map((c) => (
                      <th key={c} className="border border-line p-1 text-left font-semibold">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {d.hang.map((h) => (
                    <tr key={h.hang}>
                      <td className="border border-line p-1 text-ink-muted">{h.hang}</td>
                      {h.o.map((o, j) => (
                        <td key={o?.ma ?? j} className="border border-line p-1">
                          {o && coNhap(duLieu[o.ma]) ? giaTriDoc(o, duLieu[o.ma]) : ""}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            ),
          )}
        </div>
      ))}
    </dl>
  );
}

function DsChiDinh({ ds }: { ds: ChiDinhVaKetQua[] }) {
  return (
    <ul className="list-disc space-y-1 pl-5">
      {ds.map((c) => (
        <li key={c.service_order_id}>
          {c.ten_hien_thi}
          <span className="text-ink-muted"> · {NHAN_KET_QUA[c.ket_qua_trang_thai]}</span>
        </li>
      ))}
    </ul>
  );
}

/** Mục III — kết quả của từng chỉ định CLS: số đo + kết luận, ghi số ảnh. */
function KetQuaCls({ ds, coTrangAnh }: { ds: ChiDinhVaKetQua[]; coTrangAnh: boolean }) {
  return (
    <ol className="space-y-3">
      {ds.map((c, i) => {
        const phieu = c.ket_qua.filter((k) => k.loai === "PHIEU" && k.trang_thai === "READY" && k.khung);
        const soAnh = anhInDuoc(c).length;
        return (
          <li key={c.service_order_id} className="in-giu space-y-1">
            <p className="font-semibold text-ink">
              {i + 1}. {c.ten_hien_thi}
              <span className="font-normal text-ink-muted">
                {" "}
                · {NHAN_KET_QUA[c.ket_qua_trang_thai]}
                {soAnh ? ` · ${soAnh} ảnh${coTrangAnh ? " (trang hình ảnh)" : ""}` : ""}
              </span>
            </p>
            {phieu.map((k) => {
              const { dong, ketLuan } = dongKetQua(k);
              return (
                <div key={k.phieu_id} className="space-y-1 pl-4">
                  {phieu.length > 1 ? <p className="text-meta text-ink-muted">{k.ten}</p> : null}
                  {dong.length ? (
                    <dl className="grid grid-cols-1 gap-x-6 gap-y-0.5 sm:grid-cols-2 print:grid-cols-2">
                      {dong.map((x, j) => (
                        <div key={`${x.nhan}-${j}`} className="flex min-w-0 gap-2">
                          <dt className="shrink-0 text-ink-muted">{x.nhan}</dt>
                          <dd className="whitespace-pre-wrap">{x.gia}</dd>
                        </div>
                      ))}
                    </dl>
                  ) : null}
                  {ketLuan ? (
                    <p className="whitespace-pre-wrap">
                      <b>Kết luận:</b> {ketLuan}
                    </p>
                  ) : null}
                </div>
              );
            })}
          </li>
        );
      })}
    </ol>
  );
}

/** Trang ẢNH — ảnh kết quả CLS theo từng chỉ định, 2 ảnh / hàng. */
function TrangAnh({
  ds,
  khach,
  trangMoi = true,
  className = "",
}: {
  ds: ChiDinhVaKetQua[];
  khach: string | null;
  /** false: in riêng ảnh — đã có đầu trang ngay trên, không sang trang mới. */
  trangMoi?: boolean;
  className?: string;
}) {
  const coAnh = ds.map((c) => ({ c, anh: anhInDuoc(c) })).filter((x) => x.anh.length > 0);
  if (coAnh.length === 0) return null;
  return (
    <section
      className={`space-y-4 ${trangMoi ? "mt-10 break-before-page print:mt-0" : "mt-5"} ${className}`}
    >
      <h2 className="border-b border-line pb-1 text-emph font-bold uppercase text-ink">
        Hình ảnh kết quả cận lâm sàng
      </h2>
      {/* Trang rời vẫn biết của ai. */}
      {khach ? <p className="text-meta text-ink-muted">{khach}</p> : null}
      {coAnh.map(({ c, anh }) => (
        <div key={c.service_order_id} className="space-y-2">
          <h3 className="font-semibold text-ink">{c.ten_hien_thi}</h3>
          <div className="grid grid-cols-2 gap-3">
            {anh.map((a) => (
              <figure key={a.tep_id} className="space-y-0.5">
                {/* eslint-disable-next-line @next/next/no-img-element -- ảnh đi qua cửa XÁC THỰC; bộ tối ưu ảnh không mang cookie phiên. */}
                <img
                  src={duongXemTep(a.tep_id!)}
                  alt={a.ten ?? "Ảnh kết quả"}
                  className="aspect-4/3 w-full rounded-control border border-line bg-surface-sunken object-contain"
                />
                <figcaption className="truncate text-label text-ink-muted">{a.ten}</figcaption>
              </figure>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}

/** Một trong ba mục của trang thông tin (I · II · III). */
function Muc({
  so,
  ten,
  an = false,
  anCa = false,
  children,
}: {
  so: string | null;
  ten: string;
  /** true: không in mục này (đang in phần khác) — màn vẫn hiện. */
  an?: boolean;
  /** true: ẩn cả trên màn (mở một phần từ CSKH). */
  anCa?: boolean;
  children: ReactNode;
}) {
  return (
    <section className={`mt-5 space-y-3 ${an ? (anCa ? "hidden" : "print:hidden") : ""}`}>
      <h2 className="border-b border-line pb-1 text-emph font-bold uppercase text-ink">
        {so ? `${so}. ` : ""}
        {ten}
      </h2>
      {children}
    </section>
  );
}

function DonThuoc({ dong }: { dong: DongDonMayChu[] }) {
  return (
    <table className="w-full border-collapse text-body">
      <thead>
        <tr>
          <th className="border border-line p-1 text-left font-semibold">Thuốc</th>
          <th className="border border-line p-1 text-left font-semibold">Số lượng</th>
          <th className="border border-line p-1 text-left font-semibold">Cách dùng</th>
          <th className="border border-line p-1 text-left font-semibold">Lưu ý</th>
        </tr>
      </thead>
      <tbody>
        {dong.map((r) => {
          const d = dongTuDon(r);
          return (
            <tr key={r.id}>
              <td className="border border-line p-1">{hienThi(d.ten_thuoc)}</td>
              <td className="border border-line p-1">
                {hienThi([d.so_luong, d.don_vi].filter(Boolean).join(" "))}
              </td>
              <td className="border border-line p-1">
                {hienThi([d.duong_dung, d.cach_dung].filter(Boolean).join(" — "))}
              </td>
              <td className="border border-line p-1">{hienThi(d.luu_y)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export default function InPhieuKham({
  visitId,
  chiPhan,
}: {
  visitId: string;
  /** Mở từ CSKH (`?phan=`): chỉ hiện + in đúng phần này. */
  chiPhan?: Exclude<PhanIn, "ca">;
}) {
  const [dl, setDl] = useState<DuLieuIn | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [phan, setPhan] = useState<PhanIn>(chiPhan ?? "ca");

  // In xong (hoặc huỷ hộp in) → về lại cả phiếu; Ctrl+P in cả phiếu. Mở một
  // phần (CSKH) thì giữ nguyên phần ấy.
  useEffect(() => {
    const ve = () => setPhan(chiPhan ?? "ca");
    window.addEventListener("afterprint", ve);
    return () => window.removeEventListener("afterprint", ve);
  }, [chiPhan]);

  useEffect(() => {
    let huy = false;
    void (async () => {
      const [phieu, dau, kq, don, tc] = await Promise.all([
        doc<PhieuLuot & { form_id: string | null }>(
          `/api/phieu-kham?visit_id=${visitId}&xem=phieu`,
        ),
        doc<DauPhieu>(`/api/phieu-kham?visit_id=${visitId}&xem=dau-phieu`),
        doc<{ chi_dinh: ChiDinhVaKetQua[] }>(`/api/phieu-kham?visit_id=${visitId}`),
        doc<{ dong: DongDonMayChu[] }>(`/api/phieu-kham?visit_id=${visitId}&xem=don-thuoc`),
        doc<{ thu_thuat: ThuThuatNguon[] }>("/api/phieu-kham?xem=tham-chieu"),
      ]);
      if (huy) return;
      if (!phieu) {
        setLoi("Không đọc được phiếu khám của lượt này.");
        return;
      }
      if (!phieu.form_id) {
        setLoi("Lượt này chưa mở phiếu khám nào — chưa có gì để in.");
        return;
      }
      setDl({
        phieu,
        dau,
        chiDinh: kq?.chi_dinh ?? [],
        don: don?.dong ?? [],
        maThuThuat: new Set(
          (tc?.thu_thuat ?? []).flatMap((t) => (t.service_code ? [t.service_code] : [])),
        ),
      });
    })();
    return () => {
      huy = true;
    };
  }, [visitId]);

  if (loi) return <p className="p-8 text-body text-danger">{loi}</p>;
  if (!dl) return <p className="p-8 text-body text-ink-muted">Đang tải phiếu…</p>;
  const { phieu, dau } = dl;
  const cls = dl.chiDinh.filter((c) => !dl.maThuThuat.has(c.service_code));
  const thuThuat = dl.chiDinh.filter((c) => dl.maThuThuat.has(c.service_code));
  const ngayKham = dau?.hanh_chinh["encounter.date"] ?? null;
  const tk = dau?.the_khach;
  const hc = dau?.hanh_chinh;
  const namSinh = typeof hc?.["patient.birth_year"] === "number" ? hc["patient.birth_year"] : null;
  const tuoi =
    namSinh !== null
      ? (typeof ngayKham === "string" ? Number(ngayKham.slice(0, 4)) : new Date().getFullYear()) -
        namSinh
      : null;
  // Sinh hiệu MỘT dòng, chỉ chỉ số đã đo (bản mẫu `in-sh`).
  const sinhHieu = (dau?.the_sinh_hieu ?? []).filter((x) => x.gia_tri);

  // I. TÓM TẮT BỆNH ÁN = mọi mục của phiếu có dữ liệu, TRỪ danh sách chỉ định
  // CLS (sang mục III) và đơn thuốc (mục II). Thủ thuật ở lại mục I.
  const tomTat = phieu.khung
    .filter(
      (m) =>
        m.ma !== "HANH_CHINH" &&
        m.lien_ket?.loai !== "chi_dinh_cls" &&
        m.lien_ket?.loai !== "don_thuoc",
    )
    .flatMap((m) => {
      const coThuThuat = m.lien_ket?.loai === "chi_dinh_thu_thuat" && thuThuat.length > 0;
      const coO = m.block.some((o) => coNhap(phieu.du_lieu[o.ma]));
      if (!coThuThuat && !coO) return [];
      return [
        <div key={m.ma} className="in-giu space-y-1">
          <h3 className="font-semibold text-ink">{m.ten}</h3>
          {coThuThuat ? <DsChiDinh ds={thuThuat} /> : null}
          <KhoiO m={m} duLieu={phieu.du_lieu} />
        </div>,
      ];
    });
  // Ô ghi thêm của mục CLS / đơn thuốc (nếu phòng khám thêm ô vào đó) vẫn in.
  const oCua = (loai: string) =>
    phieu.khung
      .filter((m) => m.lien_ket?.loai === loai)
      .map((m) => <KhoiO key={m.ma} m={m} duLieu={phieu.du_lieu} />);

  const coAnh = cls.some((c) => anhInDuoc(c).length > 0);
  const inPhan = (p: PhanIn) => {
    setPhan(p);
    // Đợi màn vẽ lại (ẩn phần không in) rồi mới mở hộp in.
    window.setTimeout(() => window.print(), 50);
  };
  const ca = phan === "ca";
  const inCls = ca || phan === "cls_kem" || phan === "cls";
  const inAnh = ca || phan === "cls_kem" || phan === "cls_anh";
  // Mở một phần (CSKH): phần khác ẩn cả trên màn, không chỉ khi in.
  const AN = chiPhan ? "hidden" : "print:hidden";
  // Đánh số I · II · III chỉ khi in cả phiếu.
  const so = (x: string) => (ca ? x : null);

  return (
    <main className="in-a4 mx-auto max-w-3xl bg-surface p-8 text-body text-ink print:max-w-none print:p-0">
      <KieuInA4 />
      {chiPhan ? (
        <div className="mb-6 flex flex-wrap gap-2 print:hidden">
          <Button type="button" variant="primary" onClick={() => inPhan(chiPhan)}>
            In / tải PDF
          </Button>
          <Button type="button" variant="ghost" onClick={() => window.close()}>
            Đóng
          </Button>
        </div>
      ) : (
      <div className="mb-6 flex flex-wrap gap-2 print:hidden">
        <Button type="button" variant="primary" onClick={() => inPhan("ca")}>
          In cả phiếu
        </Button>
        <Button type="button" onClick={() => inPhan("tom_tat")}>
          In tóm tắt bệnh án
        </Button>
        <Button type="button" disabled={dl.don.length === 0} onClick={() => inPhan("don")}>
          In đơn thuốc
        </Button>
        <Button type="button" disabled={cls.length === 0 || !coAnh} onClick={() => inPhan("cls_kem")}>
          In KQ CLS + ảnh
        </Button>
        <Button type="button" disabled={cls.length === 0} onClick={() => inPhan("cls")}>
          In KQ CLS
        </Button>
        <Button type="button" disabled={!coAnh} onClick={() => inPhan("cls_anh")}>
          In ảnh CLS
        </Button>
        <Button type="button" variant="ghost" onClick={() => window.close()}>
          Đóng
        </Button>
      </div>
      )}

      {/* ── TRANG THÔNG TIN ── */}
      {/* Đầu trang HAI BÊN + khối BỆNH NHÂN gọn (27/09/2026 — bản mẫu `manIn`):
          không lặp dải hành chính dài của màn khám; sinh hiệu một dòng. */}
      <DauTrangIn
        phongKham={tk?.phong_kham}
        trai={[tk?.co_so, tk?.dia_chi_co_so]}
        tieuDe={TIEU_DE_PHAN[phan] ?? phieu.ten}
        phai={[
          hc?.["patient.code"] ? `Mã khách ${hc["patient.code"]}` : null,
          dongSoLuot(tk?.so_booking, tk?.so_tiep_don),
          ngayIn(ngayKham) ? `Ngày khám ${ngayIn(ngayKham)}` : null,
        ]}
      />
      <KhoiBenhNhanIn
        dong={[
          { nhan: "Họ tên", gia: hc?.["patient.name"] ? <b>{hc["patient.name"]}</b> : null },
          {
            nhan: "Năm sinh",
            gia: namSinh ? `${namSinh}${tuoi !== null ? ` (${tuoi} tuổi)` : ""}` : null,
          },
          { nhan: "Giới", gia: hc?.["patient.gender"] as string | null },
          { nhan: "Điện thoại", gia: hc?.["patient.phone"] as string | null },
          { nhan: "Địa chỉ", gia: hc?.["patient.address"] as string | null, rong: true },
        ]}
      />
      {sinhHieu.length ? (
        <p className="in-giu mt-2 border-y border-hairline py-2 text-meta tabular-nums text-ink">
          {sinhHieu.map((x) => `${x.nhan} ${x.gia_tri}`).join(" · ")}
        </p>
      ) : null}

      <Muc so={so("I")} ten="Tóm tắt bệnh án" anCa={Boolean(chiPhan)} an={!ca && phan !== "tom_tat"}>
        {tomTat.length ? tomTat : <p className="text-ink-muted">Chưa ghi nội dung khám.</p>}
      </Muc>
      <Muc so={so("II")} ten="Đơn thuốc" anCa={Boolean(chiPhan)} an={!ca && phan !== "don"}>
        {dl.don.length ? <DonThuoc dong={dl.don} /> : <p className="text-ink-muted">Không kê đơn.</p>}
        {oCua("don_thuoc")}
      </Muc>
      <Muc so={so("III")} ten="Kết quả cận lâm sàng" anCa={Boolean(chiPhan)} an={!inCls}>
        {cls.length ? (
          <KetQuaCls ds={cls} coTrangAnh={inAnh} />
        ) : (
          <p className="text-ink-muted">Không chỉ định cận lâm sàng.</p>
        )}
        {oCua("chi_dinh_cls")}
      </Muc>

      {/* Chân ký: TÊN bác sĩ của lượt (`the_khach.bac_si`), chừa chỗ ký tay. */}
      <footer className={`in-giu mt-8 flex justify-end ${phan === "cls_anh" ? AN : ""}`}>
        <div className="min-w-48 text-center">
          <p className="text-ink-muted">Bác sĩ khám</p>
          <p className="mt-12 font-semibold">{tk?.bac_si ?? "\u00a0"}</p>
        </div>
      </footer>

      {/* ── TRANG ẢNH ── */}
      <TrangAnh
        ds={cls}
        trangMoi={phan !== "cls_anh"}
        className={inAnh ? "" : AN}
        khach={
          [hc?.["patient.name"], hc?.["patient.code"]].filter(Boolean).join(" · ") || null
        }
      />
    </main>
  );
}
