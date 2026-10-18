"use client";

// Tab CHỜ DUYỆT của Kho vật tư (G8b, 15/10/2026): phiếu NHẬP có dòng "cần duyệt nhập"
// không vào sổ ngay mà thành YÊU CẦU chờ người có lego "Duyệt vật tư". Màn chỉ vẽ và
// gửi lệnh qua proxy; MÁY CHỦ quyết quyền (nút hiện theo `duoc_duyet` / `cua_toi` máy
// chủ trả, bấm sai vẫn bị 403), lý do 5–500 ký tự, "chỉ quyết một lần", giá nhập chụp
// lúc xin. Chờ duyệt / từ chối / rút lại là việc BÌNH THƯỜNG → chip trung tính, KHÔNG
// hộp vàng-đỏ (Tuyền 14/10); đỏ chỉ ở câu lỗi máy chủ trả.

import { useRouter } from "next/navigation";
import { useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import ONhap from "@/components/ui/ONhap";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";
import { useNgheBang } from "../dung-nghe-bang";
import { guiVatTu, soVatTu, tienVatTu } from "./gui-vat-tu";
import type { NoiChua } from "./TonVatTu";

type TrangThai = "CHO_DUYET" | "DA_DUYET" | "TU_CHOI" | "RUT_LAI";

interface DongYeuCau {
  vat_tu_id: string;
  ten: string | null;
  don_vi: string | null;
  den_room_id: string | null;
  so_luong: string;
  gia_nhap: string;
  thanh_tien: string;
}

export interface YeuCauNhap {
  id: string;
  ma_yeu_cau: string;
  trang_thai: TrangThai;
  /** Nhãn tiếng Việt do máy chủ trả ("Chờ duyệt", "Đã duyệt"…). */
  nhan: string;
  nguoi_lap: string | null;
  cua_toi: boolean;
  tao_luc: string;
  ghi_chu: string | null;
  dong: DongYeuCau[];
  tong_tien: string;
  nguoi_quyet: string | null;
  quyet_luc: string | null;
  quyet_ly_do: string | null;
  phieu_id: string | null;
}

export interface GoiChoDuyet {
  items: YeuCauNhap[];
  /** Người xem có lego Duyệt vật tư (máy chủ trả) — chỉ để hiện / ẩn nút. */
  duoc_duyet: boolean;
}

type Lenh = "duyet" | "tu-choi" | "rut-lai";

const gio = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

const THAO_TAC = { duyet: "nhap-duyet", "tu-choi": "nhap-tu-choi", "rut-lai": "nhap-rut-lai" } as const;

export default function ChoDuyetVatTu({
  goi,
  noiChua,
}: {
  /** null = đọc máy chủ hỏng (hiện câu báo, không chặn các tab khác). */
  goi: GoiChoDuyet | null;
  noiChua: NoiChua[];
}) {
  const router = useRouter();
  const [mo, setMo] = useState<{ id: string; lenh: Lenh } | null>(null);
  const [lyDo, setLyDo] = useState("");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<{ id: string; chu: string } | null>(null);
  const [bao, setBao] = useState<string | null>(null);

  // Người khác duyệt / rút xong, hoặc có yêu cầu mới → tự vẽ lại, không cần F5.
  useNgheBang(["vat_tu_nhap_cho_duyet"], () => router.refresh());

  if (!goi) {
    return (
      <p role="alert" className="text-body text-danger">
        Không đọc được danh sách chờ duyệt (máy chủ không trả lời). Tải lại trang; nếu vẫn vậy
        thì báo quản trị.
      </p>
    );
  }

  const tenNoi = (roomId: string | null) =>
    roomId ? (noiChua.find((n) => n.room_id === roomId)?.ten ?? "Phòng khác") : "Kho";
  const cho = goi.items.filter((y) => y.trang_thai === "CHO_DUYET");
  const daQuyet = goi.items.filter((y) => y.trang_thai !== "CHO_DUYET");

  const dong = () => {
    setMo(null);
    setLyDo("");
    setLoi(null);
  };

  const gui = async (y: YeuCauNhap, lenh: Lenh) => {
    setDang(true);
    setLoi(null);
    const kq = await guiVatTu(THAO_TAC[lenh], { yeu_cau_id: y.id, ly_do: lenh === "tu-choi" ? lyDo : null });
    setDang(false);
    if (!kq.ok) {
      setLoi({ id: y.id, chu: kq.loi });
      return;
    }
    setBao(
      lenh === "duyet"
        ? `Đã duyệt ${y.ma_yeu_cau} — phiếu nhập đã lập, tồn đã cập nhật.`
        : lenh === "tu-choi"
          ? `Đã từ chối ${y.ma_yeu_cau} — không có gì vào kho.`
          : `Đã rút lại ${y.ma_yeu_cau}.`,
    );
    dong();
    router.refresh();
  };

  const moLenh = (id: string, lenh: Lenh) => {
    setBao(null);
    setLoi(null);
    setLyDo("");
    setMo({ id, lenh });
  };

  const the = (y: YeuCauNhap) => {
    const dangCho = y.trang_thai === "CHO_DUYET";
    const duocRut = dangCho && (y.cua_toi || goi.duoc_duyet);
    const lenh = mo?.id === y.id ? mo.lenh : null;
    return (
      <li key={y.id} aria-label={y.ma_yeu_cau} className="space-y-2 border-b border-hairline px-3 py-3 last:border-b-0">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <p className="min-w-0 flex-1 basis-56 text-emph font-medium text-ink">
            {y.ma_yeu_cau} <Chip tone="neutral">{y.nhan}</Chip>
            {y.cua_toi ? (
              <Chip tone="brand" className="ml-1">
                Của bạn
              </Chip>
            ) : null}
          </p>
          <span className="text-meta tabular-nums text-ink-muted">
            {y.dong.length} dòng · {tienVatTu(y.tong_tien)}
          </span>
        </div>
        <p className="text-meta text-ink-muted">
          {y.nguoi_lap ?? "—"} xin lúc {gio(y.tao_luc)}
          {y.ghi_chu ? ` · Lý do / ghi chú: ${y.ghi_chu}` : ""}
        </p>
        <ul className="space-y-1 rounded-control bg-surface-muted px-3 py-2 text-meta text-ink">
          {y.dong.map((d, i) => (
            <li key={`${d.vat_tu_id}-${d.den_room_id ?? "kho"}-${i}`}>
              <span className="font-medium">{d.ten ?? "Vật tư đã đổi tên"}</span> · {soVatTu(d.so_luong)}
              {d.don_vi ? ` ${d.don_vi}` : ""} → {tenNoi(d.den_room_id)} · giá nhập {tienVatTu(d.gia_nhap)} ·{" "}
              <span className="tabular-nums">{tienVatTu(d.thanh_tien)}</span>
            </li>
          ))}
        </ul>
        {!dangCho ? (
          <p className="text-meta text-ink-muted">
            {y.trang_thai === "DA_DUYET"
              ? `Duyệt bởi ${y.nguoi_quyet ?? "—"}${y.quyet_luc ? ` lúc ${gio(y.quyet_luc)}` : ""} — phiếu nhập đã vào kho.`
              : y.trang_thai === "TU_CHOI"
                ? `Từ chối bởi ${y.nguoi_quyet ?? "—"}${y.quyet_luc ? ` lúc ${gio(y.quyet_luc)}` : ""}${y.quyet_ly_do ? ` — ${y.quyet_ly_do}` : ""}.`
                : `Rút lại bởi ${y.nguoi_quyet ?? "—"}${y.quyet_luc ? ` lúc ${gio(y.quyet_luc)}` : ""}${y.quyet_ly_do ? ` — ${y.quyet_ly_do}` : ""}.`}
          </p>
        ) : null}
        {dangCho && lenh === null ? (
          <div className="flex flex-wrap items-center gap-2">
            {goi.duoc_duyet ? (
              <>
                <Button type="button" size="sm" variant="primary" onClick={() => moLenh(y.id, "duyet")}>
                  Duyệt
                </Button>
                <Button type="button" size="sm" variant="secondary" onClick={() => moLenh(y.id, "tu-choi")}>
                  Từ chối
                </Button>
              </>
            ) : (
              <p className="text-meta text-ink-muted">Chờ người có quyền Duyệt vật tư quyết.</p>
            )}
            {duocRut ? (
              <Button type="button" size="sm" variant="ghost" onClick={() => moLenh(y.id, "rut-lai")}>
                Rút lại
              </Button>
            ) : null}
          </div>
        ) : null}
        {lenh === "duyet" ? (
          <XacNhanTaiCho
            cau={`Duyệt ${y.ma_yeu_cau} — lập phiếu nhập thật, tồn tăng theo số đã xin?`}
            nhanDongY="Duyệt và nhập kho"
            dangGui={dang}
            onDongY={() => void gui(y, "duyet")}
            onThoi={dong}
          />
        ) : null}
        {lenh === "tu-choi" ? (
          <XacNhanTaiCho
            cau={`Từ chối ${y.ma_yeu_cau} — không có gì vào kho.`}
            nhanDongY="Từ chối yêu cầu"
            dangGui={dang}
            choDongY={lyDo.trim().length >= 5}
            onDongY={() => void gui(y, "tu-choi")}
            onThoi={dong}
          >
            <label className="block">
              <span className="mb-1 block text-meta text-ink-soft">Lý do từ chối (ít nhất 5 ký tự)</span>
              <ONhap
                value={lyDo}
                maxLength={500}
                autoFocus
                onChange={(e) => setLyDo(e.target.value)}
                className="w-full"
              />
            </label>
          </XacNhanTaiCho>
        ) : null}
        {lenh === "rut-lai" ? (
          <XacNhanTaiCho
            cau={`Rút lại ${y.ma_yeu_cau}? Yêu cầu sẽ không được duyệt nữa; muốn nhập thì lập phiếu mới.`}
            nhanDongY="Rút lại yêu cầu"
            dangGui={dang}
            onDongY={() => void gui(y, "rut-lai")}
            onThoi={dong}
          />
        ) : null}
        {loi?.id === y.id ? (
          <p role="alert" className="text-body text-danger">
            {loi.chu}
          </p>
        ) : null}
      </li>
    );
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="text-body text-ink-muted">
        Phiếu nhập có mặt hàng đặt “cần duyệt nhập” chưa vào kho cho tới khi người có quyền Duyệt vật tư
        (Trưởng ca / Quản lý) duyệt.
        {goi.duoc_duyet ? "" : " Bạn xem được tình trạng và rút lại yêu cầu của mình; duyệt do người có quyền làm."}
      </p>
      {bao ? (
        <p role="status" className="text-body text-success">
          {bao}
        </p>
      ) : null}
      <section aria-label="Đang chờ duyệt" className="space-y-2">
        <h3 className="text-title text-ink">Đang chờ duyệt ({cho.length})</h3>
        {cho.length === 0 ? (
          <p className="rounded-card border border-line bg-surface px-4 py-6 text-center text-body text-ink-muted">
            Không có yêu cầu nào đang chờ.
          </p>
        ) : (
          <ul className="overflow-hidden rounded-card border border-line bg-surface shadow-card">{cho.map(the)}</ul>
        )}
      </section>
      {daQuyet.length > 0 ? (
        <section aria-label="Đã quyết gần đây" className="space-y-2">
          <h3 className="text-title text-ink">Đã quyết gần đây</h3>
          <ul className="overflow-hidden rounded-card border border-line bg-surface shadow-card">{daQuyet.map(the)}</ul>
        </section>
      ) : null}
    </div>
  );
}
