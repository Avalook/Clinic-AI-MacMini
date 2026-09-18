"use client";

// KẾT QUẢ SIÊU ÂM PHỤ KHOA — Ô CÓ CẤU TRÚC (Tuyền chốt 16/09/2026).
//
// `ultrasound_record.findings` là jsonb có cấu trúc từ đầu, nhưng màn nhập chỉ
// có MỘT ô mô tả rồi gói thành `{mo_ta: "..."}`. Hệ quả: nội mạc 8.5mm, AFC 8,
// buồng trứng 32×24×26 — những con số bác sĩ đọc lại ở lần khám sau, và là đầu
// vào của phác đồ kích thích buồng trứng — nằm lẫn trong một đoạn văn. Không
// so được giữa hai lần, không lọc được, không đếm được.
//
// Bộ ô lấy từ bản thiết kế và tài liệu bàn giao: tử cung, nội mạc, buồng trứng
// hai bên (kèm AFC), phần phụ, dịch ổ bụng.
//
// MỌI Ô ĐỀU CÓ THỂ BỎ TRỐNG. Siêu âm là quan sát: cái gì không nhìn thấy thì
// không ghi, ép nhập là mời người ta gõ một con số cho qua.
//
// Hai phép đổi ô ↔ `findings` nằm ở `ket-qua-phu-khoa-du-lieu.ts` để bài kiểm
// nạp được (node --test không hiểu JSX).

import type { OChu } from "./ket-qua-phu-khoa-du-lieu";

export {
  dungFindings,
  doVaoO,
  type OChu,
  type PhuKhoaFindings,
} from "./ket-qua-phu-khoa-du-lieu";

const TU_THE = ["", "Ngả trước", "Ngả sau", "Trung gian"];

const HINH_DANG = ["", "Bình thường", "Bất thường"];

const HINH_ANH_NM = ["", "Đồng nhất", "Không đồng nhất", "Có polyp", "Dày bất thường"];

const DICH = ["", "Không có", "Ít", "Vừa", "Nhiều"];

function O({
  nhan,
  don,
  value,
  onChange,
  rong,
}: {
  nhan: string;
  don?: string;
  value: string;
  onChange: (v: string) => void;
  rong?: boolean;
}) {
  return (
    <label style={{ display: "grid", gap: 2, minWidth: rong ? 120 : 64 }}>
      <span style={{ fontSize: 11, color: "var(--ink-muted)" }}>
        {nhan}
        {don ? ` (${don})` : ""}
      </span>
      <input
        value={value}
        inputMode="decimal"
        onChange={(e) => onChange(e.target.value)}
        style={{ width: "100%" }}
      />
    </label>
  );
}

function Chon({
  nhan,
  value,
  onChange,
  chon,
}: {
  nhan: string;
  value: string;
  onChange: (v: string) => void;
  chon: string[];
}) {
  return (
    <label style={{ display: "grid", gap: 2, minWidth: 140 }}>
      <span style={{ fontSize: 11, color: "var(--ink-muted)" }}>{nhan}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {chon.map((c) => (
          <option key={c} value={c}>
            {c || "— chưa ghi —"}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function KetQuaPhuKhoa({
  gia_tri,
  onDoi,
}: {
  gia_tri: OChu;
  onDoi: (khoa: string, v: string) => void;
}) {
  const g = (k: string) => gia_tri[k] ?? "";
  const hang: React.CSSProperties = { display: "flex", gap: 8, flexWrap: "wrap" };
  const khoi: React.CSSProperties = {
    border: "1px solid var(--line)",
    borderRadius: 8,
    padding: 8,
    display: "grid",
    gap: 6,
  };
  const ten: React.CSSProperties = { fontSize: 12, fontWeight: 700 };

  return (
    <div style={{ display: "grid", gap: 8 }}>
      <div style={khoi}>
        <span style={ten}>Tử cung</span>
        <div style={hang}>
          <O nhan="Dài" don="mm" value={g("tc_d")} onChange={(v) => onDoi("tc_d", v)} />
          <O nhan="Rộng" don="mm" value={g("tc_r")} onChange={(v) => onDoi("tc_r", v)} />
          <O nhan="Cao" don="mm" value={g("tc_c")} onChange={(v) => onDoi("tc_c", v)} />
          <Chon nhan="Hình dạng" value={g("tc_hinh_dang")} onChange={(v) => onDoi("tc_hinh_dang", v)} chon={HINH_DANG} />
          <Chon nhan="Tư thế" value={g("tc_tu_the")} onChange={(v) => onDoi("tc_tu_the", v)} chon={TU_THE} />
        </div>
      </div>

      <div style={khoi}>
        <span style={ten}>Nội mạc tử cung</span>
        <div style={hang}>
          <O nhan="Độ dày" don="mm" value={g("nm_day")} onChange={(v) => onDoi("nm_day", v)} />
          <Chon nhan="Hình ảnh" value={g("nm_hinh_anh")} onChange={(v) => onDoi("nm_hinh_anh", v)} chon={HINH_ANH_NM} />
        </div>
      </div>

      {(
        [
          ["btp", "Buồng trứng phải"],
          ["btt", "Buồng trứng trái"],
        ] as const
      ).map(([tien, nhan]) => (
        <div key={tien} style={khoi}>
          <span style={ten}>{nhan}</span>
          <div style={hang}>
            <O nhan="Dài" don="mm" value={g(`${tien}_d`)} onChange={(v) => onDoi(`${tien}_d`, v)} />
            <O nhan="Rộng" don="mm" value={g(`${tien}_r`)} onChange={(v) => onDoi(`${tien}_r`, v)} />
            <O nhan="Cao" don="mm" value={g(`${tien}_c`)} onChange={(v) => onDoi(`${tien}_c`, v)} />
            <O nhan="Thể tích" don="ml" value={g(`${tien}_the_tich`)} onChange={(v) => onDoi(`${tien}_the_tich`, v)} />
            {/* AFC = số nang thứ cấp 2–10mm. Đây là con số bác sĩ hiếm muộn
                dùng để chọn phác đồ, nên nó phải là MỘT Ô RIÊNG. */}
            <O nhan="Số nang (AFC)" value={g(`${tien}_afc`)} onChange={(v) => onDoi(`${tien}_afc`, v)} />
          </div>
        </div>
      ))}

      <div style={hang}>
        <O rong nhan="Phần phụ" value={g("phan_phu")} onChange={(v) => onDoi("phan_phu", v)} />
        <Chon nhan="Dịch ổ bụng" value={g("dich")} onChange={(v) => onDoi("dich", v)} chon={DICH} />
      </div>
    </div>
  );
}
