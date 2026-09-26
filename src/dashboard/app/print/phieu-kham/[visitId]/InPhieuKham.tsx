"use client";

// Bản in phiếu khám v5 — CHỈ ĐỌC, chữ thường thay cho ô nhập (ô nhập bị khoá in
// ra mờ và cắt chữ đoạn văn dài). Khung, nhãn, giá trị lấy nguyên từ máy chủ;
// dải hành chính + sinh hiệu dùng lại ĐÚNG khối của Bàn khám để giấy in và màn
// hình không lệch nhau.
//
// LÁT 5 (26/09/2026 — bản giao diện mẫu Tuyền duyệt): A4 (KieuInA4), in đủ BA
// KHỐI như màn khám nhưng ẨN ô / nhóm / mục trống (trước in "—" cho từng ô, một
// phiếu vài chục dòng gạch) và KHÔNG in khối tư vấn.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import {
  KHOI_PHIEU,
  NHAN_KET_QUA,
  coNhap,
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

import { KhoiHanhChinh } from "../../../(dashboard)/_lam-viec/phieu-kham/KhoiDauPhieu";
import KieuInA4 from "../../KieuInA4";

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

export default function InPhieuKham({ visitId }: { visitId: string }) {
  const [dl, setDl] = useState<DuLieuIn | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

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

  // Một mục: phần liên kết (chỉ định / đơn) + các ô có dữ liệu; rỗng hết = ẩn.
  const noiDungMuc = (m: MucPhieu) => {
    const lk = m.lien_ket?.loai;
    const phan = [
      lk === "chi_dinh_cls" && cls.length ? <DsChiDinh key="cls" ds={cls} /> : null,
      lk === "chi_dinh_thu_thuat" && thuThuat.length ? (
        <DsChiDinh key="tt" ds={thuThuat} />
      ) : null,
      lk === "don_thuoc" && dl.don.length ? <DonThuoc key="don" dong={dl.don} /> : null,
      <KhoiO key="o" m={m} duLieu={phieu.du_lieu} />,
    ];
    const coGi =
      phan.slice(0, 3).some(Boolean) ||
      m.block.some((o) => coNhap(phieu.du_lieu[o.ma]));
    return coGi ? phan : null;
  };
  const trongKhoi = new Set(KHOI_PHIEU.flatMap((k) => k.muc));
  const khoi = [
    ...KHOI_PHIEU.map((k) => ({
      ten: `${k.so} · ${k.ten}`,
      muc: phieu.khung.filter((m) => k.muc.includes(m.ma)),
    })),
    // Mục không thuộc ba khối (phòng khám thêm sau): vẫn in, không lặng lẽ mất.
    {
      ten: "Khác",
      muc: phieu.khung.filter((m) => m.ma !== "HANH_CHINH" && !trongKhoi.has(m.ma)),
    },
  ]
    .map((k) => ({
      ten: k.ten,
      muc: k.muc.flatMap((m) => {
        const nd = noiDungMuc(m);
        return nd ? [{ m, nd }] : [];
      }),
    }))
    .filter((k) => k.muc.length > 0);
  const hanhChinh = phieu.khung.find((m) => m.ma === "HANH_CHINH");

  return (
    <main className="in-a4 mx-auto max-w-3xl bg-surface p-8 text-body text-ink print:max-w-none print:p-0">
      <KieuInA4 />
      <div className="mb-6 flex gap-2 print:hidden">
        <Button type="button" variant="primary" onClick={() => window.print()}>
          In phiếu
        </Button>
        <Button type="button" variant="ghost" onClick={() => window.close()}>
          Đóng
        </Button>
      </div>
      <header className="border-b border-line pb-3">
        <h1 className="text-title font-bold text-ink">{phieu.ten}</h1>
      </header>
      {hanhChinh && dau ? (
        <section className="mt-4">
          <KhoiHanhChinh dau={dau} truong={hanhChinh.lien_ket?.truong ?? []} />
        </section>
      ) : null}
      {khoi.map((k) => (
        <section key={k.ten} className="mt-5 space-y-3">
          <h2 className="border-b border-line pb-1 text-emph font-bold text-ink">{k.ten}</h2>
          {k.muc.map(({ m, nd }) => (
            <div key={m.ma} className="space-y-1">
              <h3 className="font-semibold text-ink">{m.ten}</h3>
              {nd}
            </div>
          ))}
        </section>
      ))}
      <footer className="in-giu mt-10 flex justify-end">
        <div className="text-center">
          <p className="text-meta text-ink-muted">
            {ngayKham ? `Ngày khám ${hienThi(ngayKham)}` : "Ngày …/…/……"}
          </p>
          <p className="font-semibold">Bác sĩ khám</p>
          <p className="mt-12">&nbsp;</p>
        </div>
      </footer>
    </main>
  );
}
