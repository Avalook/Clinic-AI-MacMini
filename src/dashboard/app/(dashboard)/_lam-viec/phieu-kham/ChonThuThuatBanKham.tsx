"use client";

// KHỐI 1 LƯỢT THỦ THUẬT — "＋ Thủ thuật đã làm" (Tuyền chốt 09/10/2026).
//
// Một nút GỌN gập / mở + ô TÌM ngay cạnh (không bày cả danh mục ra khối 1). Chọn
// một thủ thuật = ghi nhận LÀM TẠI BÀN KHÁM luôn: máy chủ tạo chỉ định rồi Bắt
// đầu tại bàn khám (`/api/ho-so-kham` `thao_tac=chon-thu-thuat`); bác sĩ bấm
// [Xong] riêng ở thẻ bên dưới để có giờ thật. KHÔNG chỉ định sang phòng mình.
// Cửa tiền chặn (chưa thu, chưa tick) thì chỉ định vẫn ghi — thẻ nói "chưa thu"
// và ô tick hiện ngay trên thẻ. Danh sách lọc ở `lib/phieu-kham`
// (`danhSachThuThuatBanKham`); màn chỉ vẽ và gửi lệnh.

import { Search } from "lucide-react";
import { useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import { nhanLoi, type ThanLoi } from "@/lib/loi-api";
import { danhSachThuThuatBanKham, tenHienMuc, tienVn, type MucCls, type NhomCls } from "@/lib/phieu-kham";

function khoaGui(): string {
  return `chon-thu-thuat-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export default function ChonThuThuatBanKham({
  visitId,
  ds,
  daChon,
  choGhi,
  onDaChon,
}: {
  visitId: string;
  /** Danh mục thủ thuật (`nhomThuThuat(tham_chieu.thu_thuat)`). */
  ds: NhomCls[];
  /** Mã dịch vụ đã có thẻ làm tại bàn khám — dòng ấy ghi "đã chọn". */
  daChon: ReadonlySet<string>;
  choGhi: boolean;
  onDaChon: () => void;
}) {
  const [mo, setMo] = useState(false);
  const [tu, setTu] = useState("");
  const [dang, setDang] = useState<string | null>(null);
  const [bao, setBao] = useState<{ loi: boolean; chu: string } | null>(null);
  const ketQua = useMemo(() => danhSachThuThuatBanKham(ds, tu), [ds, tu]);

  if (!choGhi) return null;

  async function chon(m: MucCls) {
    if (dang || !m.service_code) return;
    setDang(m.service_code);
    setBao(null);
    const r = await fetch("/api/ho-so-kham", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": khoaGui() },
      body: JSON.stringify({ thao_tac: "chon-thu-thuat", visit_id: visitId, service_code: m.service_code }),
    }).catch(() => null);
    setDang(null);
    if (!r) {
      setBao({ loi: true, chu: "Mất kết nối — chưa ghi. Thử lại." });
      return;
    }
    const d = (await r.json().catch(() => null)) as (ThanLoi & { bat_dau?: boolean; ly_do?: string | null }) | null;
    if (!r.ok) {
      setBao({ loi: true, chu: nhanLoi(d, "Không ghi được thủ thuật.") });
      return;
    }
    const ten = tenHienMuc(m).chinh;
    setBao({
      loi: false,
      chu: d?.bat_dau
        ? `Đã ghi “${ten}” — đang làm tại bàn khám, bấm Xong ở thẻ khi làm xong.`
        : `Đã ghi “${ten}” — chưa bắt đầu: ${d?.ly_do ?? "xem thẻ bên dưới"}`,
    });
    setMo(false);
    setTu("");
    onDaChon();
  }

  const hienDs = mo || tu.trim() !== "";

  return (
    <section aria-label="Thủ thuật đã làm tại bàn khám" className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="lg" variant={mo ? "secondary" : "primary"} aria-expanded={hienDs} onClick={() => setMo(!mo)}>
          ＋ Thủ thuật đã làm
        </Button>
        <label className="flex min-h-10 min-w-0 flex-1 basis-48 items-center gap-2 rounded-control border border-line bg-surface px-2.5 focus-within:border-brand-500">
          <Search aria-hidden className="size-4 shrink-0 text-ink-muted" />
          <span className="sr-only">Tìm thủ thuật</span>
          <input
            type="search"
            value={tu}
            onChange={(e) => setTu(e.target.value)}
            placeholder="Tìm thủ thuật — vd “tháo vòng”, “que”"
            className="min-w-0 flex-1 bg-transparent text-body text-ink outline-none placeholder:text-ink-faint"
          />
        </label>
      </div>
      {hienDs ? (
        ketQua.length === 0 ? (
          <p className="text-meta text-ink-muted">Không có thủ thuật nào khớp “{tu.trim()}”.</p>
        ) : (
          <ul className="max-h-72 divide-y divide-line overflow-y-auto rounded-control border border-line">
            {ketQua.map((m) => {
              const code = m.service_code ?? "";
              const roi = daChon.has(code);
              return (
                <li key={code}>
                  <button
                    type="button"
                    disabled={Boolean(dang) || roi}
                    onClick={() => void chon(m)}
                    className="flex min-h-10 w-full items-center gap-2 px-3 py-2 text-left text-body text-ink hover:bg-surface-sunken disabled:text-ink-muted disabled:hover:bg-transparent"
                  >
                    <span className="min-w-0 flex-1">{tenHienMuc(m).chinh}</span>
                    <span className="shrink-0 text-meta tabular-nums text-ink-muted">
                      {roi ? "đã chọn" : dang === code ? "đang ghi…" : tienVn(m.gia)}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )
      ) : null}
      {bao ? (
        <p role={bao.loi ? "alert" : "status"} className={`text-meta ${bao.loi ? "text-danger" : "text-ink-soft"}`}>
          {bao.chu}
        </p>
      ) : null}
    </section>
  );
}
