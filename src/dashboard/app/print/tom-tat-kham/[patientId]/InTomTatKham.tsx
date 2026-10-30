"use client";

// Bản in "TÓM TẮT BỆNH ÁN — N LẦN KHÁM GẦN NHẤT" (Tuyền duyệt bản demo
// 30/10/2026). CHỈ VẼ: máy chủ (`services/tom_tat_kham.py`) chọn lượt (khám đã
// hoàn tất, bỏ lượt chỉ mua thuốc), xếp cũ → mới, đánh dấu số bất thường theo
// ngưỡng của màn đo sinh hiệu (`bat_thuong`) và tính xu hướng (`xu_huong`).
// Ở đây chỉ đổi số lần (1–3), bỏ chọn lượt, ẩn/hiện khối sản khoa — mỗi lần
// đổi là hỏi lại máy chủ.
//
// Các lượt là CỘT cạnh nhau, cũ bên trái → mới bên phải, để bác sĩ cầm một tờ
// là thấy huyết áp, cân nặng, tuổi thai đi lên hay xuống. Ô trống = lượt đó
// không đo / không làm (không tự điền). Hàng mà mọi lượt đều trống thì ẩn.
// Chữ ký bác sĩ của lượt MỚI NHẤT, LUÔN ở cuối cùng.

import { useEffect, useState, type ReactNode } from "react";

import Button from "@/components/ui/Button";

import { INPUT } from "../../../(dashboard)/form-ui";
import { DauTrangIn, KhoiBenhNhanIn, gioIn, ngayIn } from "../../KhoiIn";
import KieuInA4 from "../../KieuInA4";

interface LuotTomTat {
  visit_id: string;
  ngay: string | null;
  dich_vu: string | null;
  bac_si: string | null;
  ly_do: string[];
  sinh_hieu: {
    huyet_ap?: string | null;
    mach?: string | null;
    nhiet?: string | null;
    can_nang?: string | null;
    bmi?: string | null;
    spo2?: string | null;
  };
  /** `truong` máy chủ báo vượt ngưỡng (systolic, diastolic, pulse…). */
  bat_thuong: string[];
  xu_huong: { huyet_ap?: string; can_nang?: string };
  san_khoa: { tuoi_thai: string | null; tim_thai: string | null };
  cls: { sieu_am: string[]; xet_nghiem: string[]; khac: string[] };
  chan_doan: string[];
  xu_ly: string[];
  don: string[];
}

interface GoiTomTat {
  khach: {
    ho_ten: string | null;
    ma: string | null;
    ngay_sinh?: string | null;
    nam_sinh?: number | null;
    tuoi?: number | null;
    gioi?: string | null;
    sdt?: string | null;
    dia_chi?: string | null;
    nghe_nghiep?: string | null;
  };
  dau_trang: { phong_kham?: string | null; co_so?: string | null; dia_chi_co_so?: string | null };
  nen_tang: {
    di_ung: string | null;
    para: string | null;
    tien_su: string[];
    ky_kinh_cuoi: string | null;
    du_sinh: string | null;
  };
  co_thai: boolean;
  tong_lan_kham: number;
  so_lan: number;
  luot: LuotTomTat[];
  chon_duoc: {
    visit_id: string;
    ngay: string;
    dich_vu: string | null;
    nhan_luot: string | null;
    bo: boolean;
  }[];
  bac_si_ky: string | null;
  in_luc: string;
}

const DO = "font-semibold text-danger";

/** Một ô danh sách: một dòng thì chữ thường, nhiều dòng thì gạch đầu dòng. */
function DanhSach({ ds }: { ds: string[] }): ReactNode {
  if (ds.length === 0) return null;
  if (ds.length === 1) return <span className="whitespace-pre-wrap">{ds[0]}</span>;
  return (
    <ul className="list-disc space-y-0.5 pl-4">
      {ds.map((x, i) => (
        <li key={i} className="whitespace-pre-wrap">
          {x}
        </li>
      ))}
    </ul>
  );
}

/** Hai số một ô ("82 · 36,8"): thiếu một bên thì "—", thiếu cả hai thì trống. */
function HaiSo({ a, b }: { a: ReactNode; b: ReactNode }): ReactNode {
  if (!a && !b) return null;
  return (
    <>
      {a || "—"} · {b || "—"}
    </>
  );
}

function XuHuong({ chu }: { chu?: string }) {
  return chu ? <span className="text-label text-ink-muted"> {chu}</span> : null;
}

interface Hang {
  nhan: string;
  /** Lượt này có gì để vẽ ở hàng này — mọi lượt đều trống thì ẩn cả hàng. */
  co: (l: LuotTomTat) => boolean;
  o: (l: LuotTomTat) => ReactNode;
}

interface Nhom {
  ten: string;
  /** Khối sản khoa: ẩn/hiện được, tự ẩn khi khách không có dữ liệu thai. */
  thai?: boolean;
  hang: Hang[];
}

const ds = (x: string[]) => x.length > 0;

const NHOM: Nhom[] = [
  {
    ten: "",
    hang: [{ nhan: "Lý do khám", co: (l) => ds(l.ly_do), o: (l) => <DanhSach ds={l.ly_do} /> }],
  },
  {
    ten: "Sinh hiệu",
    hang: [
      {
        nhan: "Huyết áp",
        co: (l) => Boolean(l.sinh_hieu.huyet_ap),
        o: (l) => (
          <>
            <span
              className={
                l.bat_thuong.includes("systolic") || l.bat_thuong.includes("diastolic") ? DO : ""
              }
            >
              {l.sinh_hieu.huyet_ap}
            </span>
            <XuHuong chu={l.xu_huong.huyet_ap} />
          </>
        ),
      },
      {
        nhan: "Mạch · Nhiệt",
        co: (l) => Boolean(l.sinh_hieu.mach || l.sinh_hieu.nhiet),
        o: (l) => (
          <HaiSo
            a={
              l.sinh_hieu.mach ? (
                <span className={l.bat_thuong.includes("pulse") ? DO : ""}>{l.sinh_hieu.mach}</span>
              ) : null
            }
            b={
              l.sinh_hieu.nhiet ? (
                <span className={l.bat_thuong.includes("temperature") ? DO : ""}>
                  {l.sinh_hieu.nhiet}
                </span>
              ) : null
            }
          />
        ),
      },
      {
        nhan: "Cân nặng · BMI",
        co: (l) => Boolean(l.sinh_hieu.can_nang || l.sinh_hieu.bmi),
        o: (l) => (
          <>
            <HaiSo
              a={l.sinh_hieu.can_nang ? `${l.sinh_hieu.can_nang} kg` : null}
              b={l.sinh_hieu.bmi}
            />
            <XuHuong chu={l.xu_huong.can_nang} />
          </>
        ),
      },
      {
        nhan: "SpO₂",
        co: (l) => Boolean(l.sinh_hieu.spo2),
        o: (l) => (
          <span className={l.bat_thuong.includes("spo2") ? DO : ""}>{l.sinh_hieu.spo2}%</span>
        ),
      },
    ],
  },
  {
    ten: "Sản khoa",
    thai: true,
    hang: [
      { nhan: "Tuổi thai", co: (l) => Boolean(l.san_khoa.tuoi_thai), o: (l) => l.san_khoa.tuoi_thai },
      { nhan: "Tim thai", co: (l) => Boolean(l.san_khoa.tim_thai), o: (l) => l.san_khoa.tim_thai },
    ],
  },
  {
    ten: "Cận lâm sàng",
    hang: [
      { nhan: "Siêu âm", co: (l) => ds(l.cls.sieu_am), o: (l) => <DanhSach ds={l.cls.sieu_am} /> },
      {
        nhan: "Xét nghiệm",
        co: (l) => ds(l.cls.xet_nghiem),
        o: (l) => <DanhSach ds={l.cls.xet_nghiem} />,
      },
      {
        nhan: "Cận lâm sàng khác",
        co: (l) => ds(l.cls.khac),
        o: (l) => <DanhSach ds={l.cls.khac} />,
      },
    ],
  },
  {
    ten: "Kết luận",
    hang: [
      { nhan: "Chẩn đoán", co: (l) => ds(l.chan_doan), o: (l) => <DanhSach ds={l.chan_doan} /> },
      {
        nhan: "Hướng xử lý · đơn",
        co: (l) => ds(l.xu_ly) || ds(l.don),
        o: (l) => <DanhSach ds={[...l.xu_ly, ...l.don]} />,
      },
    ],
  },
];

export default function InTomTatKham({ clinicPatientId }: { clinicPatientId: string }) {
  const [soLan, setSoLan] = useState(3);
  const [bo, setBo] = useState<string[]>([]);
  const [anThai, setAnThai] = useState(false);
  const [moChon, setMoChon] = useState(false);
  const [goi, setGoi] = useState<GoiTomTat | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  const q = new URLSearchParams({
    xem: "tom-tat-kham",
    clinic_patient_id: clinicPatientId,
    so_lan: String(soLan),
  });
  if (bo.length) q.set("bo", bo.join(","));
  const url = `/api/ho-so-kham?${q.toString()}`;

  useEffect(() => {
    let huy = false;
    void fetch(url, { cache: "no-store" })
      .then(async (r) => ({ ok: r.ok, d: (await r.json().catch(() => null)) as GoiTomTat | null }))
      .then(({ ok, d }) => {
        if (huy) return;
        setGoi(ok ? d : null);
        setLoi(ok && d ? null : "Không đọc được hồ sơ khám của khách này.");
      })
      .catch(() => {
        if (!huy) setLoi("Mất kết nối — thử lại.");
      });
    return () => {
      huy = true;
    };
  }, [url]);

  if (loi) return <p className="p-8 text-body text-danger">{loi}</p>;
  if (!goi) return <p className="p-8 text-body text-ink-muted">Đang tải phiếu…</p>;

  const k = goi.khach;
  const nt = goi.nen_tang;
  const hienThai = goi.co_thai && !anThai;
  const luot = goi.luot;
  const [y, m, d] = goi.in_luc.slice(0, 10).split("-");
  const tienSu = nt.tien_su.join(" · ");
  const nenTang: { nhan: string; gia: string | null; canh?: boolean }[] = [
    { nhan: "Dị ứng", gia: nt.di_ung, canh: true },
    { nhan: "PARA", gia: nt.para },
    { nhan: "Tiền sử", gia: tienSu || null },
    {
      nhan: "Kỳ kinh cuối · Dự sinh",
      gia: hienThai && (nt.ky_kinh_cuoi || nt.du_sinh) ? `${nt.ky_kinh_cuoi ?? "—"} · ${nt.du_sinh ?? "—"}` : null,
    },
  ].filter((x) => x.gia);

  const nhomHien = NHOM.filter((n) => !n.thai || hienThai)
    .map((n) => ({ ...n, hang: n.hang.filter((h) => luot.some((l) => h.co(l))) }))
    .filter((n) => n.hang.length > 0);

  return (
    <main className="in-a4 mx-auto w-full max-w-3xl bg-surface p-4 text-body text-ink sm:p-8 print:max-w-none print:p-0">
      <KieuInA4 />
      <div className="mb-6 space-y-3 print:hidden">
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-body">
            Số lần
            <select
              value={soLan}
              onChange={(e) => setSoLan(Number(e.target.value))}
              aria-label="Số lần khám in ra"
              className={`${INPUT} w-20`}
            >
              {[3, 2, 1].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          {goi.co_thai ? (
            <label className="flex items-center gap-2 text-body">
              <input type="checkbox" checked={!anThai} onChange={(e) => setAnThai(!e.target.checked)} />
              Hiện dòng sản khoa
            </label>
          ) : null}
          {goi.chon_duoc.length ? (
            <Button type="button" variant="secondary" aria-expanded={moChon} onClick={() => setMoChon((x) => !x)}>
              Chọn lượt…
            </Button>
          ) : null}
          <Button type="button" variant="primary" onClick={() => window.print()} disabled={luot.length === 0}>
            In / tải PDF
          </Button>
          <Button type="button" variant="ghost" onClick={() => window.close()}>
            Đóng
          </Button>
        </div>
        {moChon ? (
          <fieldset className="rounded-card border border-line p-3">
            <legend className="px-1 text-meta text-ink-muted">
              Bỏ tick lượt không muốn in — lượt cũ hơn tự lấp chỗ
            </legend>
            <ul className="grid gap-1 sm:grid-cols-2">
              {goi.chon_duoc.map((c) => (
                <li key={c.visit_id}>
                  <label className="flex items-baseline gap-2 text-body">
                    <input
                      type="checkbox"
                      checked={!c.bo}
                      onChange={(e) =>
                        setBo((cu) =>
                          e.target.checked ? cu.filter((x) => x !== c.visit_id) : [...cu, c.visit_id],
                        )
                      }
                    />
                    <b className="tabular-nums">{ngayIn(c.ngay)}</b>
                    <span className="text-brand-700">{c.nhan_luot ?? ""}</span>
                    <span className="min-w-0 truncate text-ink-muted">{c.dich_vu ?? ""}</span>
                  </label>
                </li>
              ))}
            </ul>
          </fieldset>
        ) : null}
        <p className="text-meta text-ink-muted">
          Hệ thống tự lấy các lượt khám gần nhất đã hoàn tất, bỏ qua lượt chỉ mua thuốc. Ô trống
          nghĩa là lượt đó không đo hoặc không làm.
        </p>
      </div>

      <DauTrangIn
        phongKham={goi.dau_trang.phong_kham}
        coSo={goi.dau_trang.co_so}
        diaChi={goi.dau_trang.dia_chi_co_so}
        tieuDe={`Tóm tắt bệnh án — ${luot.length || soLan} lần khám gần nhất`}
        phai={[
          k.ma ? `Mã khách ${k.ma}` : null,
          `In lúc ${gioIn(goi.in_luc) ?? ""} ${ngayIn(goi.in_luc) ?? ""}`.trim(),
        ]}
      />
      <p className="mt-1 text-center text-meta text-ink-muted">Lấy tự động từ hồ sơ khám trên hệ thống</p>

      <KhoiBenhNhanIn
        dong={[
          { nhan: "Họ tên", gia: k.ho_ten ? <b>{k.ho_ten}</b> : null },
          {
            nhan: "Ngày sinh",
            gia:
              (k.ngay_sinh ?? k.nam_sinh)
                ? `${k.ngay_sinh ?? k.nam_sinh}${k.tuoi != null ? ` (${k.tuoi} tuổi)` : ""}`
                : null,
          },
          { nhan: "Giới", gia: k.gioi },
          { nhan: "Điện thoại", gia: k.sdt },
          { nhan: "Nghề nghiệp", gia: k.nghe_nghiep },
          { nhan: "Tổng số lần khám", gia: String(goi.tong_lan_kham) },
          { nhan: "Địa chỉ", gia: k.dia_chi, rong: true },
        ]}
      />

      {nenTang.length ? (
        <dl className="in-giu mt-3 grid grid-cols-1 gap-x-4 gap-y-1 rounded-control border border-line p-2 text-meta sm:grid-cols-2 print:grid-cols-2">
          {nenTang.map((x) => (
            <div key={x.nhan} className="flex min-w-0 gap-1.5">
              <dt className={x.canh ? "shrink-0 font-semibold text-warning" : "shrink-0 text-ink-muted"}>
                {x.nhan}:
              </dt>
              <dd className="whitespace-pre-wrap">{x.gia}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {luot.length === 0 ? (
        <p className="mt-6 text-body text-ink-muted">
          {goi.chon_duoc.length
            ? "Đã bỏ hết các lượt — tick lại ít nhất một lượt để in."
            : "Khách chưa có lượt khám nào đã hoàn tất — chưa có gì để in."}
        </p>
      ) : (
        <div className="mt-3 overflow-x-auto print:overflow-visible">
          <table className="w-full min-w-160 table-fixed border-collapse text-meta print:min-w-0">
            <colgroup>
              <col className="w-24" />
              {luot.map((l) => (
                <col key={l.visit_id} />
              ))}
            </colgroup>
            <thead>
              <tr>
                <th className="border border-line bg-surface-muted p-1 text-left font-semibold">Mục</th>
                {luot.map((l, i) => (
                  <th key={l.visit_id} className="border border-line bg-surface-muted p-1 text-left align-top font-semibold">
                    Lần {i + 1}
                    {i === luot.length - 1 && luot.length > 1 ? " (mới nhất)" : ""} · {ngayIn(l.ngay) ?? ""}
                    <span className="block font-normal text-ink-muted">
                      {[l.bac_si, l.dich_vu].filter(Boolean).join(" · ")}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {nhomHien.flatMap((n) => [
                ...(n.ten
                  ? [
                      <tr key={`nhom-${n.ten}`}>
                        <td
                          colSpan={luot.length + 1}
                          className="border border-line bg-brand-50 p-1 text-label font-semibold uppercase tracking-wide"
                        >
                          {n.ten}
                        </td>
                      </tr>,
                    ]
                  : []),
                ...n.hang.map((h) => (
                  <tr key={h.nhan}>
                    <td className="border border-line bg-surface-muted p-1 align-top font-semibold">{h.nhan}</td>
                    {luot.map((l) => (
                      <td key={l.visit_id} className="border border-line p-1 align-top">
                        {h.co(l) ? h.o(l) : null}
                      </td>
                    ))}
                  </tr>
                )),
              ])}
            </tbody>
          </table>
        </div>
      )}

      {/* Chân ký: bác sĩ của lượt MỚI NHẤT — LUÔN Ở CUỐI CÙNG (Tuyền 30/09). */}
      <footer className="in-giu mt-6 flex flex-col gap-4 text-meta sm:flex-row sm:justify-between print:flex-row print:justify-between">
        <p className="max-w-md text-label text-ink-muted">
          Số tô đỏ là số ngoài ngưỡng bình thường.
        </p>
        <div className="min-w-48 self-end text-center">
          <p className="text-ink-muted">
            Ngày {d} tháng {m} năm {y}
          </p>
          <p className="font-semibold">Bác sĩ</p>
          <p className="mt-12 font-semibold">{goi.bac_si_ky ?? " "}</p>
        </div>
      </footer>
    </main>
  );
}
