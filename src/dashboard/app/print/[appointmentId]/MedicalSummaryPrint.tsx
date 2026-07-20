"use client";

// PHIẾU "TÓM TẮT KHÁM BỆNH / MEDICAL SUMMARY" — khổ A4, in được (window.print()
// → Lưu PDF). Chuyển từ in.tsx (form mẫu) sang nhận DỮ LIỆU THẬT của bệnh nhân
// (prefill từ server qua prop `initial`) + thay logo "4W" bằng ảnh logo.png thật.
// Lễ tân mở từ trang chủ (BN đã khám xong) → bấm "In phiếu / Xuất PDF".
// Các ô vẫn sửa được trước khi in (lễ tân chỉnh nhanh nếu cần).
//
// LƯU Ý: các component con (Field/Area/Barcode…) khai báo Ở NGOÀI hàm render +
// nhận d/set qua prop — nếu khai báo trong render thì mỗi lần gõ phím sẽ tạo lại
// component → input MẤT FOCUS (và vi phạm react-hooks/static-components).

import React, { useState } from "react";

export type FormData = {
  maHoSo: string;
  maNB: string;
  maHS: string;
  phongKham: string;
  hoTen: string;
  ngaySinh: string;
  gioiTinh: string;
  danToc: string;
  quocTich: string;
  ngheNghiep: string;
  doiTuong: string;
  diaChi: string;
  nguoiBaoLanh: string;
  soDienThoai: string;
  denKhamLuc: string;
  lyDoVaoKham: string;
  tienSuDiUng: string;
  para: string;
  tienSu: string;
  benhSu: string;
  tuoiThai: string;
  duKienSinh: string;
  chieuCaoTuCung: string;
  conCoTuCung: string;
  nhipTimThai: string;
  // sinh hiệu
  mach: string;
  nhietDo: string;
  huyetAp: string;
  nhipTho: string;
  spo2: string;
  canNang: string;
  chieuCao: string;
  bmi: string;
  // cận lâm sàng
  congThucMau: string;
  sinhHoaMau: string;
  cdha: string;
  chanDoan: string;
  huongXuLy: string;
  // chân ký
  thanhPho: string;
  nguoiKy: string;
  ngayKyDuyet: string;
};

type SetFn = (
  k: keyof FormData,
) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;

const serif = '"Times New Roman", Times, serif';

const fieldStyle: React.CSSProperties = {
  border: "none",
  borderBottom: "1px dotted #bbb",
  outline: "none",
  background: "transparent",
  fontFamily: serif,
  fontSize: "13px",
  padding: "0 2px",
};
const sectionTitle: React.CSSProperties = { fontWeight: 700, fontSize: 13.5 };
const roman: React.CSSProperties = {
  fontWeight: 700,
  fontSize: 13.5,
  minWidth: 28,
  display: "inline-block",
};

export default function MedicalSummaryPrint({ initial }: { initial: FormData }) {
  const [d, setD] = useState<FormData>(initial);
  const set: SetFn = (k) => (e) => setD((p) => ({ ...p, [k]: e.target.value }));

  return (
    <div
      className="screen-bg"
      style={{
        background: "#e9e9e9",
        padding: 24,
        fontFamily: serif,
        color: "#111",
        minHeight: "100vh",
      }}
    >
      {/* CSS in ấn khổ A4 */}
      <style>{`
        @page { size: A4; margin: 9mm; }
        /* textarea TỰ CO theo nội dung (Chrome) → hết khoảng trắng thừa, gọn 1 trang. */
        textarea { field-sizing: content; }
        @media print {
          .screen-bg { background: #fff !important; padding: 0 !important; min-height: auto !important; }
          .sheet { box-shadow: none !important; width: auto !important; min-height: auto !important;
                   padding: 0 !important; margin: 0 !important; font-size: 11px !important; line-height: 1.22 !important; }
          .no-print { display: none !important; }
          input, textarea { border-bottom: none !important; resize: none !important; }
        }
      `}</style>

      {/* Nút in (ẩn khi in) */}
      <div
        className="no-print"
        style={{
          width: 794,
          margin: "0 auto 12px",
          display: "flex",
          justifyContent: "flex-end",
          gap: 10,
        }}
      >
        <button
          onClick={() => window.print()}
          style={{
            fontFamily: serif,
            fontSize: 13,
            padding: "8px 18px",
            background: "#1b5e20",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            cursor: "pointer",
            boxShadow: "0 1px 4px rgba(0,0,0,.2)",
          }}
        >
          In phiếu / Xuất PDF
        </button>
      </div>

      <div
        className="sheet"
        style={{
          width: 794, // ~A4 @ 96dpi
          minHeight: 1123,
          margin: "0 auto",
          background: "#fff",
          padding: "20px 32px",
          boxShadow: "0 2px 12px rgba(0,0,0,.25)",
          fontSize: 12,
          lineHeight: 1.3,
        }}
      >
        {/* ===== HEADER ===== */}
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
            {/* Logo phòng khám thật (public/logo.png). */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/logo.png"
              alt="Logo Dr4Women"
              style={{
                width: 50,
                height: 50,
                borderRadius: "50%",
                objectFit: "contain",
                flexShrink: 0,
              }}
            />
            <div style={{ textAlign: "center" }}>
              <div style={{ fontWeight: 700, fontSize: 13, marginTop: 2 }}>
                PHÒNG KHÁM 4WOMEN CLINIC
              </div>
              <div style={{ fontStyle: "italic", fontSize: 9.5 }}>
                Obstetrics &amp; Gynecology Clinic
              </div>
              <div style={{ fontSize: 10, marginTop: 2 }}>
                Mã HS: <Field d={d} set={set} k="maHS" width={90} bold />
              </div>
            </div>
          </div>

          <div style={{ textAlign: "right" }}>
            <Barcode code={d.maHoSo} />
            <div style={{ fontSize: 11.5, marginTop: 4, textAlign: "left" }}>
              <div>
                Mã Hồ sơ: <Field d={d} set={set} k="maHoSo" width={110} bold />
              </div>
              <div>
                Mã NB: <Field d={d} set={set} k="maNB" width={130} bold />
              </div>
              <div>
                Phòng khám: <Field d={d} set={set} k="phongKham" width={120} bold />
              </div>
            </div>
          </div>
        </div>

        {/* ===== TITLE ===== */}
        <div style={{ textAlign: "center", margin: "8px 0 6px" }}>
          <div style={{ fontWeight: 700, fontSize: 17, letterSpacing: 1 }}>
            PHIẾU KHÁM BỆNH
          </div>
          <div style={{ fontWeight: 700, fontStyle: "italic", fontSize: 13 }}>
            MEDICAL SUMMARY
          </div>
        </div>

        {/* ===== I. HÀNH CHÍNH ===== */}
        <div style={{ marginBottom: 4 }}>
          <span style={roman}>I.</span>
          <span style={sectionTitle}>Hành chính (administration)</span>
        </div>

        <div style={{ paddingLeft: 28 }}>
          <Row n="1." label="Họ và tên" en="Full name">
            <Field d={d} set={set} k="hoTen" width={220} bold />
          </Row>

          {/* hàng 2 cột */}
          <TwoCol
            left={
              <Row n="2." label="Ngày sinh" en="D.O.B">
                <Field d={d} set={set} k="ngaySinh" width={110} />
              </Row>
            }
            right={
              <Row n="3." label="Giới tính" en="Gender">
                <Field d={d} set={set} k="gioiTinh" width={70} />
              </Row>
            }
          />
          <TwoCol
            left={
              <Row n="4." label="Dân tộc" en="Ethnic">
                <Field d={d} set={set} k="danToc" width={110} />
              </Row>
            }
            right={
              <Row n="5." label="Quốc tịch" en="Nation">
                <Field d={d} set={set} k="quocTich" width={90} />
              </Row>
            }
          />
          <TwoCol
            left={
              <Row n="6." label="Nghề nghiệp" en="Occupation">
                <Field d={d} set={set} k="ngheNghiep" width={110} />
              </Row>
            }
            right={
              <Row n="7." label="Đối tượng" en="Objection">
                <Field d={d} set={set} k="doiTuong" width={70} />
              </Row>
            }
          />
          <Row n="8." label="Địa chỉ" en="Address">
            <Field d={d} set={set} k="diaChi" width={440} />
          </Row>
          <Row n="9." label="Họ tên Người bảo lãnh" en="Full name of Father/ Mother">
            <Field d={d} set={set} k="nguoiBaoLanh" width={120} />
          </Row>
          <div style={{ paddingLeft: 22 }}>
            <span>
              Số điện thoại <i>(Phone number)</i>:{" "}
            </span>
            <Field d={d} set={set} k="soDienThoai" width={140} />
          </div>
          <Row n="10." label="Đến khám bệnh lúc" en="Time of consulting">
            <Field d={d} set={set} k="denKhamLuc" width={160} />
          </Row>
        </div>

        {/* ===== II + box sinh hiệu ===== */}
        <div style={{ display: "flex", gap: 16, marginTop: 8 }}>
          <div style={{ flex: 1 }}>
            <SimpleSec n="II." vi="Lý do vào khám" en="Reason for hospitalization">
              <Field d={d} set={set} k="lyDoVaoKham" width={200} />
            </SimpleSec>

            <SimpleSec n="III." vi="Tiền sử dị ứng" en="Allergy history">
              <Field d={d} set={set} k="tienSuDiUng" width={200} />
            </SimpleSec>
          </div>

          {/* HỘP SINH HIỆU */}
          <div
            style={{
              width: 300,
              border: "1px solid #000",
              padding: "6px 8px",
              fontSize: 12,
              alignSelf: "flex-start",
            }}
          >
            <VitalRow vi="Mạch" en="Pulse" k="mach" unit="(Lần/phút)" set={set} d={d} />
            <VitalRow vi="Nhiệt độ" en="Tempurature" k="nhietDo" unit="(°C)" set={set} d={d} />
            <VitalRow vi="Huyết áp" en="Blood pressure" k="huyetAp" unit="(mmHg)" set={set} d={d} />
            <VitalRow vi="Nhịp thở" en="Breath" k="nhipTho" unit="(Lần/phút)" set={set} d={d} />
            <VitalRow vi="SP02" en="" k="spo2" unit="(%)" set={set} d={d} />
            <VitalRow vi="Cân nặng" en="Weight" k="canNang" unit="(Kg)" set={set} d={d} />
            <VitalRow vi="Chiều cao" en="Height" k="chieuCao" unit="(cm)" set={set} d={d} />
            <VitalRow vi="BMI" en="" k="bmi" unit="" set={set} d={d} />
          </div>
        </div>

        {/* ===== IV. TIỀN SỬ ===== */}
        <div style={{ marginTop: 4 }}>
          <span style={roman}>IV.</span>
          <span style={sectionTitle}>Tiền sử (Medical history): </span>
          <span>PARA: </span>
          <Field d={d} set={set} k="para" width={60} />
          <div style={{ paddingLeft: 28 }}>
            <Area d={d} set={set} k="tienSu" rows={2} />
          </div>
        </div>

        {/* ===== V. BỆNH SỬ ===== */}
        <div style={{ marginTop: 4 }}>
          <span style={roman}>V.</span>
          <span style={sectionTitle}>Bệnh sử (Pathological process): </span>
          <div style={{ paddingLeft: 28 }}>
            <Area d={d} set={set} k="benhSu" rows={2} />
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>
                - Tuổi thai: <Field d={d} set={set} k="tuoiThai" width={90} />
              </span>
              <span>
                Dự kiến sinh: <Field d={d} set={set} k="duKienSinh" width={110} />
              </span>
            </div>
            <div>
              - Chiều cao tử cung/VB (Cm):{" "}
              <Field d={d} set={set} k="chieuCaoTuCung" width={120} />
            </div>
            <div>
              - Cơn co tử cung: <Field d={d} set={set} k="conCoTuCung" width={120} />
            </div>
            <div>
              - Nhịp tim thai: <Field d={d} set={set} k="nhipTimThai" width={120} />
            </div>
          </div>
        </div>

        {/* ===== VI. CẬN LÂM SÀNG ===== */}
        <div style={{ marginTop: 4 }}>
          <span style={roman}>VI.</span>
          <span style={sectionTitle}>
            Kết quả cận lâm sàng (Subclinical result):
          </span>
          <div style={{ paddingLeft: 28 }}>
            <Area d={d} set={set} k="congThucMau" rows={2} />
            <Area d={d} set={set} k="sinhHoaMau" rows={2} />
            <Area d={d} set={set} k="cdha" rows={1} />
          </div>
        </div>

        {/* ===== VII. Chuẩn đoán ===== */}
        <div style={{ marginTop: 4 }}>
          <span style={roman}>VII.</span>
          <span style={sectionTitle}>Chuẩn đoán (Diagnosis):</span>
          <div style={{ paddingLeft: 28 }}>
            <Area d={d} set={set} k="chanDoan" rows={2} />
          </div>
        </div>

        {/* ===== VIII. HƯỚNG XỬ LÝ ===== */}
        <div style={{ marginTop: 4 }}>
          <span style={roman}>VIII.</span>
          <span style={sectionTitle}>
            Hướng xử lý và lời dặn (Solution and instruction):
          </span>
          <div style={{ paddingLeft: 28 }}>
            <Area d={d} set={set} k="huongXuLy" rows={2} />
          </div>
        </div>

        {/* ===== CHÂN KÝ ===== */}
        <div style={{ marginTop: 18, display: "flex", justifyContent: "flex-end" }}>
          <div style={{ textAlign: "center", width: 300 }}>
            <div style={{ fontStyle: "italic" }}>
              <Field d={d} set={set} k="thanhPho" width={90} />,
            </div>
            <div style={{ fontWeight: 700 }}>BÁC SĨ KHÁM BỆNH</div>
            <div style={{ fontStyle: "italic", fontSize: 11 }}>
              (Ký, ghi rõ họ tên)
            </div>
            <div style={{ fontSize: 10, marginTop: 2, color: "#333" }}>
              Người ký duyệt: {d.nguoiKy}
            </div>
            <div style={{ fontSize: 10, color: "#333" }}>
              Ngày ký duyệt: <Field d={d} set={set} k="ngayKyDuyet" width={150} />
            </div>
            <div style={{ height: 42 }} />
            <div style={{ fontWeight: 700 }}>
              <Field d={d} set={set} k="nguoiKy" width={180} bold />
            </div>
          </div>
        </div>

        {/* ===== FOOTER ===== */}
        <div
          style={{
            marginTop: 24,
            borderTop: "1px solid #999",
            paddingTop: 4,
            display: "flex",
            justifyContent: "space-between",
            fontSize: 10,
            color: "#444",
          }}
        >
          <span>
            {d.nguoiKy.replace("BSCKII ", "")}
            {d.ngayKyDuyet ? ` - ${d.ngayKyDuyet}` : ""}
          </span>
          <span>Trang 1/ 1</span>
        </div>
      </div>
    </div>
  );
}

/* ---------- helper components (khai báo NGOÀI render) ---------- */

function Field({
  d,
  set,
  k,
  width = "auto",
  bold = false,
}: {
  d: FormData;
  set: SetFn;
  k: keyof FormData;
  width?: string | number;
  bold?: boolean;
}) {
  return (
    <input
      value={d[k]}
      onChange={set(k)}
      style={{ ...fieldStyle, width, fontWeight: bold ? 700 : 400 }}
    />
  );
}

function Area({
  d,
  set,
  k,
  rows = 2,
}: {
  d: FormData;
  set: SetFn;
  k: keyof FormData;
  rows?: number;
}) {
  return (
    <textarea
      value={d[k]}
      onChange={set(k)}
      rows={rows}
      style={{
        ...fieldStyle,
        width: "100%",
        borderBottom: "none",
        resize: "none", // bỏ tay nắm kéo giãn — nó bị in ra làm hỏng phiếu
        lineHeight: 1.45,
        whiteSpace: "pre-wrap",
      }}
    />
  );
}

// thanh barcode giả lập từ chuỗi mã
function Barcode({ code }: { code: string }) {
  const bars = Array.from(code).flatMap((ch) => {
    const n = (ch.charCodeAt(0) % 4) + 1;
    return [n, ((ch.charCodeAt(0) >> 2) % 3) + 1];
  });
  return (
    <div style={{ display: "flex", alignItems: "flex-end", height: 38, gap: 1 }}>
      {bars.map((w, i) => (
        <div
          key={i}
          style={{
            width: w,
            height: "100%",
            background: i % 2 === 0 ? "#000" : "transparent",
          }}
        />
      ))}
    </div>
  );
}

function Row({
  n,
  label,
  en,
  children,
}: {
  n: string;
  label: string;
  en: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: 2 }}>
      <span style={{ display: "inline-block", width: 22 }}>{n}</span>
      <span>
        {label} <i>({en})</i>:{" "}
      </span>
      {children}
    </div>
  );
}

function TwoCol({
  left,
  right,
}: {
  left: React.ReactNode;
  right: React.ReactNode;
}) {
  return (
    <div style={{ display: "flex" }}>
      <div style={{ flex: 1 }}>{left}</div>
      <div style={{ flex: 1 }}>{right}</div>
    </div>
  );
}

function SimpleSec({
  n,
  vi,
  en,
  children,
}: {
  n: string;
  vi: string;
  en: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: 4 }}>
      <span style={{ fontWeight: 700, minWidth: 30, display: "inline-block" }}>
        {n}
      </span>
      <span style={{ fontWeight: 700 }}>
        {vi} ({en}):{" "}
      </span>
      {children}
    </div>
  );
}

function VitalRow({
  vi,
  en,
  k,
  unit,
  set,
  d,
}: {
  vi: string;
  en: string;
  k: keyof FormData;
  unit: string;
  set: SetFn;
  d: FormData;
}) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "baseline",
        padding: "1px 0",
      }}
    >
      <span style={{ fontStyle: "italic", fontSize: 11.5 }}>
        {vi} {en && <>({en})</>}
      </span>
      <span style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
        <input
          value={d[k]}
          onChange={set(k)}
          style={{
            border: "none",
            borderBottom: "1px dotted #ccc",
            outline: "none",
            width: 50,
            textAlign: "right",
            fontWeight: 700,
            fontFamily: serif,
            fontSize: 12,
            background: "transparent",
          }}
        />
        <span style={{ fontStyle: "italic", fontSize: 10.5, width: 56 }}>
          {unit}
        </span>
      </span>
    </div>
  );
}
