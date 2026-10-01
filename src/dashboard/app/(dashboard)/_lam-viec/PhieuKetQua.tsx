"use client";

// PHIẾU KẾT QUẢ — một màn điền cho MỌI biểu mẫu.
//
// Không có "màn siêu âm", "màn xét nghiệm", "màn thủ thuật" riêng. Máy chủ trả
// về `khung` (mục → ô), màn này vẽ đúng cái khung ấy. Phòng khám đưa ruột 18
// mẫu sau thì chỉ thêm ô vào dữ liệu — tệp này không phải sửa một dòng nào.
//
// Ba điều màn này phải nói ra, vì chúng là luật chứ không phải chi tiết:
//
//   "Đã lưu 10:32"   nháp tự lưu, và nháp KHÔNG phải kết quả — chưa ai chịu
//                    trách nhiệm về nó.
//   [Hoàn tất]       xác nhận TOÀN BỘ nội dung đang thấy, kể cả câu mẫu không
//                    ai sửa. Đây là lúc người nhận trách nhiệm — và là nút
//                    DUY NHẤT kết thúc: nó đóng luôn dịch vụ đang làm dở và
//                    phát "đã có kết quả" nếu dịch vụ có kết quả ngay tại
//                    phòng (ChatGPT tin số 156, Tuyền tin số 157 "nút chỉ 1").
//   "còn N mục…"     nhắc, KHÔNG chặn. Bắt buộc chuyên môn chỉ bật khi phòng
//                    khám chốt, không phải khi lập trình viên thấy nên thế.
//
// Người gõ ≠ người thực hiện: điều dưỡng nhập thay bác sĩ là chuyện thường
// ngày, nên có ô chọn riêng "người thực hiện" chứ không suy từ ai đăng nhập.
//
// HOÀN TẤT RỒI VẪN SỬA ĐƯỢC (Tuyền 23/09: *"vẫn cho sửa được vì audit log
// được mà"*). [Sửa lại] → gõ → [Xác nhận sửa], kèm LÝ DO bắt buộc. Đổi ý giữa
// chừng thì [Huỷ sửa].
//
// TRONG SUỐT LÚC SỬA, BẢN CŨ VẪN LÀ KẾT QUẢ CHÍNH THỨC — và từ 23/09 câu này
// là sự thật chứ không còn là lời hứa: tự lưu ghi vào `du_lieu_dang_sua`, bản
// chính thức `du_lieu` đứng yên tới lúc chốt. Trước đó tự lưu ghi thẳng vào
// bản chính thức, nên câu trên màn sai ngay từ phím đầu tiên.
//
// TỰ LƯU CHẮC CHẮN (đợt 3, 27/09/2026 — góp ý B8/B9):
//   · Hàng đợi chung `lib/use-tu-luu`: TUẦN TỰ, revision luôn lấy từ lần lưu
//     vừa xong. Trước đây mạng chậm >1,5s thì lần lưu sau mang revision cũ →
//     máy chủ báo "người khác vừa lưu" dù chính mình vừa lưu.
//   · Rời màn / đóng tab → lưu nốt; lỗi mạng tự thử lại; dòng trạng thái có
//     [Lưu ngay] / [Thử lại].
//   · [Hoàn tất] lưu nốt TRƯỚC (cùng hàng đợi, gộp đúng ô bảng `ma::cột`); lưu
//     không được thì KHÔNG hoàn tất và nói lý do NGAY TRÊN nút.
//   · Hoàn tất xong còn ô trống → "Còn N mục trống: …" cạnh nút, mỗi tên là
//     link tới ô. Chỉ nhắc, không chặn (quyết định cũ, giữ nguyên).

import { useCallback, useEffect, useRef, useState } from "react";

import { nhanLoi } from "@/lib/loi-api";
import { ghepConTrong, gopGiaTri, KHOA_BANG, tachGiaTri } from "@/lib/phieu-ket-qua";
import { LOI_MAT_KET_NOI, nenThuLai } from "@/lib/tu-luu";
import { useTuLuu } from "@/lib/use-tu-luu";
import BaoLoiCanhNut from "@/components/ui/BaoLoiCanhNut";
import { tenMucHien } from "@/lib/sua-mau";
import Button, { buttonClass } from "@/components/ui/Button";
import ChipChon from "@/components/ui/ChipChon";
import OSo from "@/components/ui/OSo";
import TrangThaiLuu from "@/components/ui/TrangThaiLuu";

export interface MauKetQua {
  ma: string;
  ten: string;
  nhom?: string | null;
  /** Mẫu của CHÍNH dịch vụ đang làm (máy chủ tính). false = của dịch vụ khác. */
  cua_dich_vu?: boolean;
}

interface O {
  ma: string;
  ten: string;
  kieu: string;
  mac_dinh?: string;
  goi_y?: string;
  chon?: string[];
  /** Cách vẽ ô chọn — "o_tick": ô tích nhanh xếp ngang (29/09/2026, "Kết luận
   *  nhanh" phiếu đo mật độ xương). Chỉ là hiển thị: vẫn CHỌN MỘT, lưu một chuỗi. */
  hien_thi?: string;
}

interface Muc {
  ma: string;
  ten: string;
  block: O[];
  /** Mục dạng BẢNG (mẫu v3, 26/09/2026): Thai A | Thai B, trái | phải… Giá trị
   *  một ô là {ma_cột: giá trị} — lưu theo `ma`, không theo vị trí. */
  cot?: { ma: string; ten: string }[];
}

/** Ô chiếm nửa hàng hay trọn hàng trong lưới hai cột: đoạn văn, hàng ô tích
 *  và ô bảng (nhiều cột ghép một dòng) chiếm trọn hàng. */
function lopCot(o: { kieu: string; hien_thi?: string }, laBang: boolean): string {
  return o.kieu === "doan_van" || laOTick(o) || laBang ? "md:col-span-2" : "";
}

/** Ô chọn vẽ thành hàng ô tích nhanh (mẫu khai `hien_thi: "o_tick"`). */
function laOTick(o: { kieu: string; hien_thi?: string }): boolean {
  return o.kieu === "chon" && o.hien_thi === "o_tick";
}

/** Mã phần tử DOM của một ô — link "còn trống" cuộn về đây. */
const idO = (phieuId: string, ma: string) => `kq-${phieuId}-${ma}`;

interface Phieu {
  id: string;
  form_id: string;
  version: number;
  trang_thai: "DRAFT" | "READY";
  dang_sua: boolean;
  revision: number;
  khung: Muc[];
  du_lieu: Record<string, { gia_tri: unknown; nguon: string }>;
  con_trong: string[];
  /** Người thực hiện của BẢN ĐANG SỬA — tải lại trang không mất lựa chọn. */
  thuc_hien_boi: string | null;
}

/** Khoảng lặng trước khi tự lưu. Gõ liên tục thì không bắn từng phím. */
const CHO_TU_LUU_MS = 1500;

async function goi<T>(
  than: Record<string, unknown>,
  keepalive = false,
): Promise<{ ok: true; data: T } | { ok: false; loi: string; status: number }> {
  try {
    const r = await fetch("/api/phieu", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(than),
      keepalive,
    });
    const d = await r.json().catch(() => null);
    if (!r.ok) return { ok: false, loi: nhanLoi(d, "Không lưu được phiếu."), status: r.status };
    return { ok: true, data: d as T };
  } catch {
    return { ok: false, loi: LOI_MAT_KET_NOI, status: 0 };
  }
}

export default function PhieuKetQua({
  serviceOrderId,
  mau,
  mauMacDinh,
  nguoiCoThe,
  onHoanTat,
  onCacBen,
}: {
  serviceOrderId: string;
  /** Mẫu kết quả để điền — máy chủ chọn: đã gắn, hoặc mặc định (CHUNG nhập tự do). */
  mau: MauKetQua[];
  /** Mẫu chọn sẵn (phiếu đang điền dở, hoặc mẫu gợi ý của phiếu khám v5). */
  mauMacDinh?: string | null;
  /** Mẫu HAI BÊN (mục bảng đầu tiên: Thai A | Thai B, trái | phải…) → tên các
   *  bên, để màn phòng dựng hai ô tải riêng (26/09/2026). null = mẫu một bên. */
  onCacBen?: (ben: string[] | null) => void;
  /** Danh sách chọn "người thực hiện". Bỏ trống thì mặc định là người gõ. */
  nguoiCoThe?: { id: string; ten: string }[];
  /** Phiếu vừa hoàn tất — màn cha nạp lại hàng chờ. */
  onHoanTat?: (ketQua: {
    daDongDichVu: boolean;
    viSao: string | null;
    laLanSua: boolean;
    /** Tên các ô còn trống — chỉ để nhắc. */
    conTrong: string[];
  }) => void;
}) {
  const [chonMau, setChonMau] = useState<string | null>(
    mauMacDinh && mau.some((m) => m.ma === mauMacDinh)
      ? mauMacDinh
      : mau.length === 1
        ? mau[0].ma
        : null,
  );
  const [phieu, setPhieu] = useState<Phieu | null>(null);
  const [gia, setGia] = useState<Record<string, string>>({});
  const [thucHienBoi, setThucHienBoi] = useState<string>("");
  // Sửa một kết quả ĐÃ IN RA GIẤY VÀ GIAO CHO KHÁCH mà không nói vì sao là để
  // lại một câu hỏi không ai trả lời được. Máy chủ cũng từ chối nếu bỏ trống.
  const [lyDoSua, setLyDoSua] = useState("");
  const [dangHoanTat, setDangHoanTat] = useState(false);
  /** Lỗi MỞ phiếu — ở đầu phiếu, cạnh ô chọn mẫu. */
  const [loi, setLoi] = useState<string | null>(null);
  /** Lỗi của [Hoàn tất] / [Sửa lại] / [Huỷ sửa] — NGAY TRÊN hàng nút (B8). */
  const [loiNut, setLoiNut] = useState<string | null>(null);
  /** Ô còn trống sau Hoàn tất — nhắc cạnh nút, không chặn. */
  const [conTrong, setConTrong] = useState<{ ma: string; ten: string }[]>([]);
  // Chọn mẫu của dịch vụ KHÁC (Tuyền 24/09/2026): không chuyển phiếu, báo khách
  // chưa thanh toán dịch vụ ấy — muốn làm thì bác sĩ chỉ định + khách trả tiền.
  const [baoKhacDv, setBaoKhacDv] = useState<string | null>(null);

  // Revision giữ trong ref: mỗi lần tự lưu phải gửi số MỚI NHẤT, không phải số
  // mà closure của lần gõ trước nhìn thấy. Hàng đợi tuần tự bảo đảm "mới nhất"
  // là số của lần lưu VỪA XONG (không có lần nào đang bay song song).
  const revision = useRef(0);
  // Bản mới nhất cho hàng đợi đọc lúc gửi.
  const phieuRef = useRef<Phieu | null>(null);
  const giaRef = useRef<Record<string, string>>({});
  const nguoiRef = useRef("");

  const guiLuu = useCallback(async (keepalive: boolean) => {
    const p = phieuRef.current;
    if (!p) return { ok: true } as const;
    const kq = await goi<{ revision: number; luu_luc: string }>(
      {
        thao_tac: "luu",
        phieu_id: p.id,
        du_lieu: {
          expected_revision: revision.current,
          thuc_hien_boi: nguoiRef.current || null,
          du_lieu: gopGiaTri(giaRef.current),
        },
      },
      keepalive,
    );
    if (!kq.ok) return { ok: false, loi: kq.loi, thuLai: nenThuLai(kq.status) } as const;
    revision.current = kq.data.revision;
    return { ok: true } as const;
  }, []);
  const tuLuu = useTuLuu({ gui: guiLuu, choMs: CHO_TU_LUU_MS });
  const lamSach = tuLuu.lamSach;

  const nhan = useCallback(
    (p: Phieu) => {
      revision.current = p.revision;
      phieuRef.current = p;
      setPhieu(p);
      // Máy chủ là nguồn: đang sửa thì trả lựa chọn của bản nháp, chưa sửa thì
      // trả lựa chọn của bản chính thức.
      nguoiRef.current = p.thuc_hien_boi ?? "";
      setThucHienBoi(nguoiRef.current);
      giaRef.current = tachGiaTri(p.du_lieu);
      setGia(giaRef.current);
      // Bản máy chủ vừa về thay cho màn — không còn gì "chưa lưu".
      lamSach();
    },
    [lamSach],
  );

  useEffect(() => {
    const bang = phieu?.khung.find((m) => m.cot && m.cot.length > 1);
    onCacBen?.(bang?.cot ? bang.cot.map((c) => c.ten) : null);
  }, [phieu, onCacBen]);

  useEffect(() => {
    if (!chonMau) return;
    let huy = false;
    void goi<Phieu>({
      thao_tac: "mo",
      du_lieu: { service_order_id: serviceOrderId, form_id: `KQ_${chonMau}` },
    }).then((kq) => {
      if (huy) return;
      if (kq.ok) {
        setLoi(null);
        nhan(kq.data);
      } else setLoi(kq.loi);
    });
    return () => {
      huy = true;
    };
  }, [chonMau, serviceOrderId, nhan]);

  // (Trước đợt 3: hẹn lưu bị XOÁ lúc rời màn — gõ xong đóng khung ngay là mất
  // chữ. Nay `useTuLuu` lưu nốt khi rời màn / đóng tab.)

  const doi = (maO: string, v: string) => {
    if (!phieu) return;
    const moi = { ...giaRef.current, [maO]: v };
    giaRef.current = moi;
    setGia(moi);
    tuLuu.danhDau();
  };

  const denO = (ma: string) => {
    if (!phieu) return;
    const el = document.getElementById(idO(phieu.id, ma));
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
    el?.querySelector<HTMLElement>("input, textarea, select")?.focus({ preventScroll: true });
  };

  const hoanTat = async () => {
    if (!phieu) return;
    setDangHoanTat(true);
    setLoiNut(null);
    setConTrong([]);
    // LƯU NỐT trước khi chốt, qua CHÍNH hàng đợi tự lưu: đợi lần đang bay, gửi
    // phần còn lại, revision lấy từ lần vừa xong. Lưu không được thì KHÔNG chốt
    // — chốt thiếu đúng câu vừa viết là tệ hơn chưa chốt.
    if (!(await tuLuu.luuNgay())) {
      setDangHoanTat(false);
      setLoiNut(
        "Nội dung vừa gõ CHƯA lưu được nên phiếu CHƯA hoàn tất. Xem lý do ở dòng trạng thái lưu, bấm [Thử lại] rồi bấm lại.",
      );
      return;
    }

    const kq = await goi<{
      con_trong: string[];
      revision: number;
      la_lan_sua?: boolean;
      dich_vu?: { da_dong: boolean; vi_sao: string | null };
    }>({
      thao_tac: "hoan-tat",
      phieu_id: phieu.id,
      du_lieu: {
        expected_revision: revision.current,
        thuc_hien_boi: nguoiRef.current || null,
        ly_do_sua: lyDoSua.trim() || null,
      },
    });
    setDangHoanTat(false);
    if (!kq.ok) {
      setLoiNut(kq.loi);
      return;
    }
    revision.current = kq.data.revision;
    const xong: Phieu = {
      ...phieu,
      trang_thai: "READY",
      dang_sua: false,
      revision: kq.data.revision,
    };
    phieuRef.current = xong;
    setPhieu(xong);
    const trong = ghepConTrong(phieu.khung, kq.data.con_trong);
    setConTrong(trong);
    onHoanTat?.({
      daDongDichVu: kq.data.dich_vu?.da_dong ?? false,
      viSao: kq.data.dich_vu?.vi_sao ?? null,
      laLanSua: kq.data.la_lan_sua ?? false,
      conTrong: (Array.isArray(kq.data.con_trong) ? kq.data.con_trong : []).filter(
        (x): x is string => typeof x === "string",
      ),
    });
  };

  // NHẬN TOÀN BỘ PHIẾU TỪ MÁY CHỦ, không tự suy ra từ state đang có.
  //
  // Bản trước chỉ lấy `revision` rồi giữ nguyên nội dung trên màn. Khoảng hở ấy
  // chết người: A mở sửa và gõ vài ô; B vẫn đang nhìn bản cũ, bấm [Sửa lại],
  // nhận SỐ mới nhưng NỘI DUNG cũ — rồi lần tự lưu kế tiếp của B ghi đè những
  // gì A vừa gõ, bằng đúng một số hợp lệ nên không lớp nào bắt được.
  const moSua = async () => {
    if (!phieu) return;
    setDangHoanTat(true);
    setLoiNut(null);
    setConTrong([]);
    const kq = await goi<Phieu>({ thao_tac: "mo-sua", phieu_id: phieu.id });
    setDangHoanTat(false);
    if (!kq.ok) {
      setLoiNut(kq.loi);
      return;
    }
    nhan(kq.data);
  };

  const huySua = async () => {
    if (!phieu) return;
    setDangHoanTat(true);
    setLoiNut(null);
    // Đợi lần lưu đang bay (nếu có) để revision là số mới nhất — huỷ bằng số
    // cũ là máy chủ từ chối oan.
    await tuLuu.luuNgay();
    const kq = await goi<{ revision: number }>({
      thao_tac: "huy-sua",
      phieu_id: phieu.id,
      // Bản nháp là của CHUNG: huỷ bằng số cũ là xoá cái người khác vừa gõ.
      du_lieu: { expected_revision: revision.current },
    });
    setDangHoanTat(false);
    if (!kq.ok) {
      setLoiNut(kq.loi);
      return;
    }
    revision.current = kq.data.revision;
    setLyDoSua("");
    // Quay về bản chính thức — nó chưa từng bị đụng tới.
    void goi<Phieu>({
      thao_tac: "mo",
      du_lieu: { service_order_id: serviceOrderId, form_id: `KQ_${chonMau}` },
    }).then((r) => {
      if (r.ok) nhan(r.data);
    });
  };

  if (mau.length === 0) {
    return (
      <p className="rounded-control border border-line bg-surface-muted px-3 py-2 text-body text-ink-soft">
        Chưa có mẫu kết quả nào để điền (kể cả mẫu “Kết quả chung”). Báo quản
        lý kiểm tra danh mục mẫu kết quả.
      </p>
    );
  }

  const daChot = phieu?.trang_thai === "READY" && !phieu.dang_sua;
  const dangSuaLai = phieu?.trang_thai === "READY" && phieu.dang_sua;

  return (
    <section aria-label="Phiếu kết quả" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-body font-semibold text-ink">Phiếu kết quả</h3>
        {mau.length > 1 ? (
          <label className="min-w-0 max-w-full text-body">
            <span className="sr-only">Chọn mẫu kết quả</span>
            <select
              value={chonMau ?? ""}
              onChange={(e) => {
                const ma = e.target.value || null;
                const m = mau.find((x) => x.ma === ma);
                if (m && m.cua_dich_vu === false) {
                  setBaoKhacDv(
                    `“${m.ten}” là dịch vụ khác — khách chưa thanh toán dịch vụ này. ` +
                      "Muốn làm thì bác sĩ chỉ định và khách thanh toán trước.",
                  );
                  return;
                }
                setBaoKhacDv(null);
                // Lưu nốt phiếu đang điền TRƯỚC khi mở mẫu khác — mở mẫu mới
                // là nạp bản máy chủ, phần chưa lưu của phiếu cũ sẽ mất.
                void tuLuu.luuNgay().then((ok) => {
                  if (ok) setChonMau(ma);
                  else setLoi("Phiếu đang điền CHƯA lưu được — chưa đổi mẫu. Bấm [Thử lại] ở dòng trạng thái lưu.");
                });
              }}
              className="min-h-10 w-full max-w-full rounded-control border border-line bg-surface px-3 text-body text-ink"
            >
              <option value="">— chọn mẫu —</option>
              {mau.map((m) => (
                <option key={m.ma} value={m.ma}>
                  {m.ten}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <span className="text-body text-ink-muted">{mau[0].ten}</span>
        )}
        {dangSuaLai ? (
          <span className="text-label font-semibold text-warning">
            Đang sửa lại — bản cũ vẫn là kết quả chính thức
          </span>
        ) : null}
        {phieu && !daChot ? (
          <TrangThaiLuu
            tt={tuLuu.trangThai}
            onLuuNgay={() => void tuLuu.luuNgay()}
            phu="nháp, chưa phải kết quả"
          />
        ) : null}
      </div>

      {baoKhacDv ? (
        <p
          role="alert"
          className="rounded-control border border-warning bg-warning-bg px-3 py-2 text-body text-warning"
        >
          {baoKhacDv}
        </p>
      ) : null}
      {loi ? (
        <p
          role="alert"
          className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-body text-danger"
        >
          {loi}
        </p>
      ) : null}

      {!chonMau ? (
        <p className="text-body text-ink-muted">Chọn mẫu để bắt đầu điền.</p>
      ) : phieu === null ? (
        <p className="text-body text-ink-muted">Đang mở phiếu…</p>
      ) : daChot ? (
        <div className="space-y-2">
          <p className="rounded-control border border-success bg-success-bg px-3 py-2 text-body text-success">
            Phiếu đã hoàn tất — đây là kết quả chính thức.
          </p>
          <dl className="grid gap-x-4 gap-y-2 rounded-control bg-surface-muted px-3 py-2 text-body md:grid-cols-2">
            {phieu.khung.map((muc) =>
              (muc.block ?? []).map((o) => (
                <div key={o.ma} id={idO(phieu.id, o.ma)} className={lopCot(o, !!muc.cot)}>
                  <dt className="text-meta font-semibold text-ink-muted">{o.ten}</dt>
                  <dd className="whitespace-pre-line text-ink">
                    {muc.cot
                      ? muc.cot
                          .map((c) => `${c.ten}: ${gia[`${o.ma}${KHOA_BANG}${c.ma}`] || "—"}`)
                          .join(" · ")
                      : gia[o.ma] || "—"}
                  </dd>
                </div>
              )),
            )}
          </dl>
          {conTrong.length > 0 ? (
            <BaoLoiCanhNut muc="nhac">
              Còn {conTrong.length} mục trống:{" "}
              {conTrong.map((o, i) => (
                <span key={o.ma}>
                  {i > 0 ? ", " : ""}
                  <button type="button" className="font-semibold underline" onClick={() => denO(o.ma)}>
                    {o.ten}
                  </button>
                </span>
              ))}
              . Chỉ nhắc — phiếu đã hoàn tất; cần bổ sung thì bấm [Sửa lại].
            </BaoLoiCanhNut>
          ) : null}
          <BaoLoiCanhNut>{loiNut}</BaoLoiCanhNut>
          <Button
            size="md"
            variant="secondary"
            disabled={dangHoanTat}
            onClick={() => void moSua()}
          >
            {dangHoanTat ? "Đang mở…" : "Sửa lại"}
          </Button>
          <a
            href={`/print/ket-qua/${serviceOrderId}`}
            target="_blank"
            rel="noopener"
            className={`ml-2 ${buttonClass("ghost", "md")}`}
          >
            In phiếu
          </a>
          <p className="text-label text-ink-muted">
            Sửa được, và mỗi lần sửa đều được ghi lại — ai sửa, lúc nào, bản thứ
            mấy.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {phieu.khung.map((muc) => (
            <fieldset key={muc.ma} className="min-w-0">
              {/* Tên mục giữ chỗ / rỗng (mẫu cũ) thì không vẽ tiêu đề — 27/09. */}
              {tenMucHien(muc.ten) ? (
                <legend className="text-body font-semibold text-ink">
                  {tenMucHien(muc.ten)}
                </legend>
              ) : null}
              {muc.cot ? (
                <BangMuc muc={muc} cot={muc.cot} gia={gia} onDoi={doi} />
              ) : (
                // HAI CỘT ở màn rộng, MỘT cột ở 375 (27/09/2026 — bản mẫu
                // `luoi hai`); đoạn văn chiếm trọn hàng.
                <div className="mt-1 grid gap-3 md:grid-cols-2">
                  {(muc.block ?? []).map((o) => (
                    <OPhieu
                      key={o.ma}
                      id={idO(phieu.id, o.ma)}
                      o={o}
                      giaTri={gia[o.ma] ?? ""}
                      nguon={phieu.du_lieu[o.ma]?.nguon ?? null}
                      onDoi={(v) => doi(o.ma, v)}
                    />
                  ))}
                </div>
              )}
            </fieldset>
          ))}

          {nguoiCoThe && nguoiCoThe.length > 0 ? (
            <label className="block">
              <span className="text-meta font-semibold text-ink">
                Người thực hiện (khác người đang gõ thì chọn lại)
              </span>
              <select
                value={thucHienBoi}
                onChange={(e) => {
                  const ai = e.target.value;
                  nguoiRef.current = ai;
                  setThucHienBoi(ai);
                  // Người thực hiện là DỮ LIỆU NGHIỆP VỤ, không phải trạng
                  // thái màn hình. Không lưu thì đổi lựa chọn rồi tải lại
                  // trang là mất — tự lưu mới lưu nửa cái phiếu.
                  tuLuu.danhDau();
                }}
                className="mt-1 min-h-10 w-full max-w-sm rounded-control border border-line bg-surface px-3 text-body text-ink"
              >
                <option value="">— tôi, người đang gõ —</option>
                {nguoiCoThe.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.ten}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          {/* Trạng thái lưu + lỗi của nút NGAY TRÊN hàng nút (B8/B9, đợt 3) — người
              bấm ở cuối phiếu thấy ngay, không phải cuộn lên đầu. */}
          <TrangThaiLuu
            tt={tuLuu.trangThai}
            onLuuNgay={() => void tuLuu.luuNgay()}
            phu="nháp, chưa phải kết quả"
          />
          <BaoLoiCanhNut>{loiNut}</BaoLoiCanhNut>
          <div className="flex flex-wrap items-center gap-3">
            {dangSuaLai ? (
              <label className="w-full">
                <span className="text-meta font-semibold text-ink">
                  Vì sao sửa kết quả này
                </span>
                <input
                  value={lyDoSua}
                  onChange={(e) => setLyDoSua(e.target.value)}
                  placeholder="Ví dụ: nhầm bên phải/trái khi gõ kết luận"
                  className="mt-1 min-h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink"
                />
              </label>
            ) : null}
            <Button
              size="md"
              variant="primary"
              // KHÔNG khoá nút khi chưa gõ lý do. Máy chủ hỏi "có đổi gì
              // không" TRƯỚC rồi mới đòi lý do; khoá ở đây là bắt người ta gõ
              // lý do cho một thay đổi không tồn tại, rồi mới được nghe câu
              // "thực ra không thay gì". Frontend không dựng bộ so thứ hai.
              disabled={dangHoanTat}
              onClick={() => void hoanTat()}
            >
              {dangHoanTat
                ? "Đang chốt…"
                : dangSuaLai
                  ? "Xác nhận sửa"
                  : "Hoàn tất phiếu"}
            </Button>
            {dangSuaLai ? (
              <Button
                size="md"
                variant="ghost"
                disabled={dangHoanTat}
                onClick={() => void huySua()}
              >
                Huỷ sửa
              </Button>
            ) : null}
            {/* In được cả khi chưa Hoàn tất — trang in ghi rõ BẢN NHÁP. */}
            <a
              href={`/print/ket-qua/${serviceOrderId}`}
              target="_blank"
              rel="noopener"
              className={buttonClass("ghost", "md")}
            >
              In phiếu
            </a>
          </div>
        </div>
      )}
    </section>
  );
}

function OPhieu({
  id,
  o,
  giaTri,
  nguon,
  onDoi,
}: {
  /** Mã DOM để link "còn trống" cuộn tới. */
  id: string;
  o: O;
  giaTri: string;
  nguon: string | null;
  onDoi: (v: string) => void;
}) {
  const nhan = (
    <span className="text-meta font-semibold text-ink">
      {o.ten}
      {nguon === "TEMPLATE_DEFAULT" ? (
        <span className="ml-2 font-normal text-ink-muted">(câu điền sẵn)</span>
      ) : null}
    </span>
  );

  // Ô TÍCH NHANH (29/09/2026): cùng ô chọn một, vẽ bằng `ChipChon` radio như
  // phiếu khám — tích ô này bỏ ô kia, bấm lại ô đang tích thì bỏ tích.
  if (laOTick(o) && Array.isArray(o.chon)) {
    return (
      <fieldset id={id} className="min-w-0 md:col-span-2">
        <legend>{nhan}</legend>
        <div className="mt-1 flex flex-wrap gap-2">
          {o.chon.map((c) => (
            <ChipChon
              key={c}
              kieu="mot"
              ten={id}
              chon={giaTri === c}
              onDoi={() => onDoi(c)}
              onBoChon={() => onDoi("")}
            >
              {c}
            </ChipChon>
          ))}
        </div>
      </fieldset>
    );
  }

  if (o.kieu === "chon" && Array.isArray(o.chon)) {
    return (
      <label id={id} className="block min-w-0">
        {nhan}
        <select
          value={giaTri}
          onChange={(e) => onDoi(e.target.value)}
          className="mt-1 min-h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink"
        >
          <option value="">— chưa chọn —</option>
          {o.chon.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>
    );
  }

  if (o.kieu === "doan_van") {
    return (
      <label id={id} className="block min-w-0 md:col-span-2">
        {nhan}
        <textarea
          value={giaTri}
          onChange={(e) => onDoi(e.target.value)}
          rows={4}
          placeholder={o.goi_y ?? ""}
          className="mt-1 w-full rounded-control border border-line bg-surface px-3 py-2 text-body text-ink"
        />
      </label>
    );
  }

  // Ô số (27/09/2026, `components/ui/OSo`): trước là `type="number"` — chặn
  // "12 x 8", lăn chuột lướt qua đổi số, bước 1 làm sai số thập phân. Phiếu kết
  // quả lưu chữ nguyên văn nên cho gõ kích thước.
  if (o.kieu === "so") {
    const donVi = o.goi_y && o.goi_y.length <= 16 ? o.goi_y : null;
    return (
      <label id={id} className="block">
        {nhan}
        <span className="mt-1 flex">
          <OSo
            kichThuoc
            value={giaTri}
            onChange={onDoi}
            donVi={donVi}
            placeholder={donVi ? undefined : (o.goi_y ?? "")}
          />
        </span>
      </label>
    );
  }

  return (
    <label id={id} className="block min-w-0">
      {nhan}
      <span className="mt-1 flex items-center gap-2">
        <input
          type={o.kieu === "ngay" ? "date" : "text"}
          value={giaTri}
          onChange={(e) => onDoi(e.target.value)}
          placeholder={o.goi_y ?? ""}
          className="min-h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink"
        />
        {o.goi_y && o.goi_y.length <= 16 ? (
          <span className="shrink-0 text-meta text-ink-muted">{o.goi_y}</span>
        ) : null}
      </span>
    </label>
  );
}

/** Mục dạng BẢNG (mẫu v3): hàng = ô của mục, cột = Thai A | Thai B, trái | phải… */
function BangMuc({
  muc,
  cot,
  gia,
  onDoi,
}: {
  muc: Muc;
  cot: { ma: string; ten: string }[];
  gia: Record<string, string>;
  onDoi: (ma: string, v: string) => void;
}) {
  const oNhap = (o: O, c: { ma: string; ten: string }) => {
    const khoa = `${o.ma}${KHOA_BANG}${c.ma}`;
    const nhanO = `${o.ten} — ${c.ten}`;
    if (o.kieu === "chon" && Array.isArray(o.chon)) {
      return (
        <select
          aria-label={nhanO}
          value={gia[khoa] ?? ""}
          onChange={(e) => onDoi(khoa, e.target.value)}
          className="min-h-10 w-full rounded-control border border-line bg-surface px-2 text-body text-ink"
        >
          <option value="">—</option>
          {o.chon.map((x) => (
            <option key={x} value={x}>
              {x}
            </option>
          ))}
        </select>
      );
    }
    if (o.kieu === "doan_van") {
      return (
        <textarea
          aria-label={nhanO}
          value={gia[khoa] ?? ""}
          onChange={(e) => onDoi(khoa, e.target.value)}
          rows={2}
          className="w-full rounded-control border border-line bg-surface px-2 py-1.5 text-body text-ink"
        />
      );
    }
    if (o.kieu === "so") {
      return (
        <OSo
          kichThuoc
          rong="day"
          aria-label={nhanO}
          value={gia[khoa] ?? ""}
          onChange={(v) => onDoi(khoa, v)}
        />
      );
    }
    return (
      <input
        aria-label={nhanO}
        value={gia[khoa] ?? ""}
        onChange={(e) => onDoi(khoa, e.target.value)}
        placeholder={o.goi_y ?? ""}
        className="min-h-10 w-full rounded-control border border-line bg-surface px-2 text-body text-ink"
      />
    );
  };
  return (
    <div className="mt-1 overflow-x-auto">
      <table className="w-full min-w-[28rem] border-collapse text-body">
        <thead>
          <tr className="text-left text-meta text-ink-muted">
            <th className="py-1.5 pr-3 font-medium">{muc.ten}</th>
            {cot.map((c) => (
              <th key={c.ma} className="py-1.5 pr-3 font-medium">
                {c.ten}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {(muc.block ?? []).map((o) => (
            <tr key={o.ma}>
              <td className="py-1.5 pr-3 align-top text-ink">
                {o.ten}
                {o.goi_y ? <span className="ml-1 text-meta text-ink-muted">({o.goi_y})</span> : null}
              </td>
              {cot.map((c) => (
                <td key={c.ma} className="py-1.5 pr-3 align-top">
                  {oNhap(o, c)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
