"use client";

// Ô QUÉT MÃ dùng chung (G3b, 14/10/2026): Nhập kho, Kiểm kho, quầy bán thuốc.
//
// Máy quét ở quầy là loại USB giả bàn phím: gõ cả dãy số rất nhanh rồi Enter.
// Ô quét là Ô RIÊNG (không chiếm ô tìm kiếm thường) nên người gõ tay không bị
// nhầm với máy quét — Enter là dấu hiệu "xong một mã". Cũng nhận dán và camera.
//
// Quét liên tục hai lần cùng một mã trong 800ms bị coi là máy đọc dội và bỏ lần
// sau: không bao giờ tự cộng số lượng ngoài ý muốn (quét thật hai hộp thì cách
// nhau quá 800ms).
//
// Mọi kết luận (mã này là thuốc nào, lô nào, còn bán được không) do MÁY CHỦ trả
// (`/pharmacy/tra-ma`); ở đây chỉ chuyển kết quả cho màn gọi và mở hộp "gắn mã"
// khi mã lạ.

import { useRef, useState, useSyncExternalStore } from "react";

import Button from "@/components/ui/Button";
import { INPUT, LABEL } from "../../form-ui";
import CameraQuet from "./CameraQuet";
import { docKho, guiKho } from "./gui-kho";

const subscribeCamera = () => () => {};
const cameraAvailable = () =>
  typeof window !== "undefined" &&
  window.isSecureContext &&
  typeof navigator !== "undefined" &&
  !!navigator.mediaDevices?.getUserMedia;
const cameraUnavailableOnServer = () => false;

export interface LoQuet {
  id: string;
  batch_code: string;
  expiry_date: string | null;
  quantity_on_hand: number | string;
  unit: string;
  ma_tem: string;
  drug_catalog_id: string;
  ten_thuoc: string | null;
  /** ok | het_han | da_huy | het_ton | khac_co_so */
  trang_thai: string;
}

export interface GS1Quet {
  gtin: string;
  so_lo: string | null;
  han: string | null;
}

export type KetQuaQuet =
  | { loai: "rong" }
  | { loai: "la"; ma: string; gs1?: GS1Quet }
  | { loai: "tem"; lo: LoQuet }
  | {
      loai: "thuoc";
      thuoc: { id: string; ten: string };
      nguon: string;
      ma_vach_id?: string | null;
      goi_y_lo: LoQuet[];
      gs1?: GS1Quet;
      lo_theo_ma?: LoQuet;
    };

export const NHAN_TRANG_THAI_LO: Record<string, string> = {
  het_han: "đã hết hạn — không bán / giao được",
  da_huy: "đã huỷ — không còn trong kho",
  het_ton: "hết tồn",
  khac_co_so: "thuộc kho cơ sở khác",
};

const CUA_SO_DOI_MS = 800;

export default function OQuetMa({
  thuoc,
  ghiDuoc,
  onKetQua,
  nhan = "Quét mã vạch",
}: {
  /** Danh mục thuốc để chọn khi gắn mã cho thuốc. */
  thuoc: { id: string; ten: string }[];
  /** Có quyền kho (`pharmacy.dispense`): được gắn / gỡ mã. Máy chủ vẫn kiểm lại. */
  ghiDuoc: boolean;
  onKetQua: (kq: KetQuaQuet) => void;
  nhan?: string;
}) {
  const [go, setGo] = useState("");
  const [dang, setDang] = useState(false);
  const [bao, setBao] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [la, setLa] = useState<{ ma: string; gs1?: GS1Quet } | null>(null);
  const [tenChon, setTenChon] = useState("");
  const [moCamera, setMoCamera] = useState(false);
  const coCamera = useSyncExternalStore(
    subscribeCamera,
    cameraAvailable,
    cameraUnavailableOnServer,
  );
  // Mã vừa quét ra một thuốc: cho gỡ nếu gắn nhầm (hoàn tác của "Gắn mã").
  const [vua, setVua] = useState<{ id: string; ten: string } | null>(null);
  const cuoi = useRef<{ ma: string; luc: number } | null>(null);
  const oRef = useRef<HTMLInputElement>(null);

  const tra = async (ma: string) => {
    const chu = ma.trim();
    if (!chu) return;
    const bay = Date.now();
    if (cuoi.current && cuoi.current.ma === chu && bay - cuoi.current.luc < CUA_SO_DOI_MS) return;
    cuoi.current = { ma: chu, luc: bay };
    setDang(true);
    setLoi(null);
    setBao(null);
    setLa(null);
    setVua(null);
    const kq = await docKho<KetQuaQuet>("tra-ma", { ma: chu });
    setDang(false);
    setGo("");
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    if (kq.data.loai === "la") {
      setLa({ ma: kq.data.ma, gs1: kq.data.gs1 });
      setTenChon("");
      setBao(`Mã ${kq.data.ma} chưa gắn cho thuốc nào.`);
    } else if (kq.data.loai === "thuoc" && kq.data.ma_vach_id) {
      setVua({ id: kq.data.ma_vach_id, ten: kq.data.thuoc.ten });
    } else if (kq.data.loai === "rong") {
      setLoi("Không đọc được mã — quét lại.");
    }
    onKetQua(kq.data);
    oRef.current?.focus();
  };

  const gan = async () => {
    const t = thuoc.find((x) => x.ten === tenChon);
    if (!la || !t) {
      setLoi("Chọn thuốc có trong danh mục (gõ rồi chọn trong danh sách).");
      return;
    }
    setDang(true);
    setLoi(null);
    const kq = await guiKho("gan-ma-vach", {
      drug_catalog_id: t.id,
      ma: la.gs1?.gtin ?? la.ma,
      nguon: la.gs1 ? "gs1" : "quet",
    });
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    const ma = la.gs1 ? `01${la.gs1.gtin}` : la.ma;
    const goLai = la;
    setLa(null);
    setBao(`Đã gắn mã cho ${t.ten}.`);
    cuoi.current = null;
    // Quét lại chính mã đó để màn nhận kết quả như một lần quét bình thường
    // (kèm gợi ý lô và số lô / hạn của mã vuông nếu có).
    await tra(goLai.gs1 ? ma : goLai.ma);
  };

  const goMa = async () => {
    if (!vua) return;
    setDang(true);
    const kq = await guiKho("go-ma-vach", { ma_vach_id: vua.id });
    setDang(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setBao(`Đã gỡ mã khỏi ${vua.ten}. Quét lại để gắn cho thuốc đúng.`);
    setVua(null);
    cuoi.current = null;
  };

  return (
    <div className="space-y-2">
      <label className="block">
        <span className={LABEL}>{nhan}</span>
        <div className="flex gap-2">
          <input
            ref={oRef}
            value={go}
            onChange={(e) => setGo(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void tra(go);
              }
            }}
            placeholder="Đưa hộp thuốc / tem lô vào máy quét…"
            aria-label="Ô quét mã vạch"
            autoComplete="off"
            inputMode="text"
            className={INPUT}
          />
          <Button
            type="button"
            variant="secondary"
            disabled={dang || !go.trim()}
            onClick={() => void tra(go)}
          >
            Tra
          </Button>
          {coCamera ? (
            <Button type="button" variant="ghost" onClick={() => setMoCamera((m) => !m)}>
              {moCamera ? "Tắt camera" : "Camera"}
            </Button>
          ) : null}
        </div>
      </label>
      {moCamera ? (
        <CameraQuet
          onMa={(ma) => {
            setMoCamera(false);
            void tra(ma);
          }}
          onDong={() => setMoCamera(false)}
        />
      ) : null}
      {bao ? (
        <p role="status" className="text-meta text-ink-soft">
          {bao}
        </p>
      ) : null}
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : null}
      {vua && ghiDuoc ? (
        <p className="flex flex-wrap items-center gap-2 text-meta text-ink-soft">
          Mã này đang gắn cho “{vua.ten}”.
          <Button type="button" size="sm" variant="ghost" disabled={dang} onClick={() => void goMa()}>
            Gỡ mã (gắn nhầm)
          </Button>
        </p>
      ) : null}
      {la ? (
        ghiDuoc ? (
          <div
            role="group"
            aria-label="Gắn mã cho thuốc"
            className="space-y-2 rounded-control border border-line bg-surface-muted p-3"
          >
            <p className="text-body text-ink">
              Mã <span className="font-mono">{la.gs1?.gtin ?? la.ma}</span> chưa có trong hệ thống —
              gắn cho thuốc nào?
            </p>
            <input
              list="o-quet-thuoc"
              value={tenChon}
              onChange={(e) => setTenChon(e.target.value)}
              placeholder="Gõ tên thuốc…"
              aria-label="Thuốc để gắn mã"
              className={INPUT}
            />
            <datalist id="o-quet-thuoc">
              {thuoc.map((t) => (
                <option key={t.id} value={t.ten} />
              ))}
            </datalist>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="primary"
                disabled={dang || !tenChon}
                onClick={() => void gan()}
              >
                Gắn mã
              </Button>
              <Button type="button" variant="ghost" onClick={() => setLa(null)}>
                Thôi
              </Button>
            </div>
          </div>
        ) : (
          <p role="status" className="text-meta text-warning">
            Mã này chưa gắn cho thuốc nào. Tài khoản của bạn không có quyền kho — nhờ người có
            quyền kho gắn mã.
          </p>
        )
      ) : null}
    </div>
  );
}
