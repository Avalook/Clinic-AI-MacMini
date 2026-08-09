"use client";

// HÀNH ĐỘNG ỨNG VỚI TRẠNG THÁI ĐANG CHỌN — khối bên phải màn Quản lý khách hàng.
//
// Đặc tả chị Thu qua Quang (09/08/2026): mỗi trạng thái có một bộ nút RIÊNG,
// không phải bốn nút chung cho mọi trạng thái. Bấm xong thì node bên trái tích
// xanh. Bảng dưới đây là bản dịch trực tiếp của đặc tả ấy, từng dòng một.
//
// MỌI NÚT ĐỀU GHI SỔ. Không nút nào chỉ đổi màu trên màn hình: tất cả đi qua
// POST /api/cskh/tuong-tac → `tuong_tac_cskh` + `event_log`, nên node tích xanh
// vì có một dòng THẬT trong database, không vì một biến trong trình duyệt.
// Đó cũng là lý do tích xanh sống qua F5 và người ca sau nhìn thấy.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Phone, Upload, Send, Check, X, CalendarPlus } from "lucide-react";
import TepKetQua, { type TepKetQuaRow } from "./TepKetQua";

/** Ba lý do huỷ có sẵn — đúng ba trường hợp chị Thu liệt kê, và khớp
 *  `LY_DO_HUY` ở booking_service.py để hai đầu không nói hai bộ từ. */
const LY_DO_HUY_SAN: string[] = [
  "Chờ xác nhận lịch trước 7 ngày: BN báo luôn là không đến được",
  "Khi nhắc hẹn BN báo không đến được, dù trước đó đã xác nhận có đến",
  "Vào giờ khám, lễ tân gọi điện BN mới báo là không đến",
];

interface Props {
  trangThai: string | null;
  clinicPatientId: string;
  patientCode: string;
  appointmentId: string | null;
  phone: string | null;
  tepKetQua: TepKetQuaRow[];
  /** Trạng thái này đã có dấu vết xử lý chưa — để nút nói "làm lại". */
  daXong: boolean;
}

export default function HanhDongTrangThai({
  trangThai,
  clinicPatientId,
  patientCode,
  appointmentId,
  phone,
  tepKetQua,
  daXong,
}: Props) {
  const router = useRouter();
  const [dangLuu, setDangLuu] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [xong, setXong] = useState(false);
  const [ghiChu, setGhiChu] = useState("");
  const [lyDo, setLyDo] = useState("");
  const [moLyDoSan, setMoLyDoSan] = useState(false);

  /** Ghi một lần chạm. `loai`/`ket_qua` phải nằm trong bộ từ backend canh
   *  (LOAI_HOP_LE, KET_QUA_HOP_LE ở tuong_tac_cskh_service.py). */
  async function ghi(
    ma: string,
    loai: string,
    ketQua: string,
    noiDung?: string,
  ) {
    // MỐC QUẦY có luật riêng ở backend: kênh phải là TRUC_TIEP và kết quả phải
    // là GHI_NHAN (chúng là việc XẢY RA, không phải cuộc gọi). Gửi sai là 422.
    const mocQuay = ["CHECK_IN", "CHECK_OUT", "THANH_TOAN", "MUA_THUOC"].includes(
      loai,
    );
    setDangLuu(ma);
    setLoi(null);
    try {
      const res = await fetch("/api/cskh/tuong-tac", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          clinic_patient_id: clinicPatientId,
          // Ba loại này bắt buộc gắn lịch hẹn (CHECK ở database). Gửi null cho
          // các loại khác thay vì gửi bừa một id không liên quan.
          appointment_id: ["XAC_NHAN_LICH", "NHAC_HEN", "HOI_LY_DO_HUY"].includes(
            loai,
          )
            ? appointmentId
            : null,
          loai,
          kenh: mocQuay ? "TRUC_TIEP" : "GOI",
          ket_qua: mocQuay ? "GHI_NHAN" : ketQua,
          noi_dung: (noiDung ?? ghiChu).trim() || null,
          // MÃ TRẠNG THÁI mà thao tác này đóng lại. Đây là thứ timeline dò để
          // tích xanh — không dò theo `loai` nữa, vì nhiều trạng thái dùng
          // chung một loại (xem migration 20260810000002).
          trang_thai_ma: trangThai,
        }),
      });
      if (!res.ok) {
        const d = (await res.json().catch(() => null)) as {
          error?: string;
          message?: string;
        } | null;
        setLoi(d?.message ?? d?.error ?? "Không ghi được.");
        return false;
      }
      setXong(true);
      setGhiChu("");
      router.refresh();
      return true;
    } finally {
      setDangLuu(null);
    }
  }

  const soDienThoai = phone ? (
    // "hiện số của khách ở đây luôn" — CSKH không phải quay về cột hồ sơ để
    // đọc số rồi quay lại đây bấm.
    <a
      href={`tel:${phone}`}
      className="block rounded-xl border border-brand-300 bg-white px-3 py-2 text-center font-mono text-sm font-bold text-brand-700 hover:bg-brand-50"
    >
      📞 {phone}
    </a>
  ) : (
    <p className="rounded-xl border border-line bg-surface-muted px-3 py-2 text-center text-xs text-ink-muted">
      Khách chưa có số điện thoại
    </p>
  );

  function NutChinh({
    ma,
    nhan,
    onClick,
    Icon = Check,
  }: {
    ma: string;
    nhan: string;
    onClick: () => void;
    Icon?: typeof Check;
  }) {
    return (
      <button
        type="button"
        onClick={onClick}
        disabled={dangLuu !== null}
        className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl bg-brand-600 py-2 px-3 text-xs font-bold text-white hover:bg-brand-700 disabled:opacity-50"
      >
        <Icon size={14} />
        {dangLuu === ma ? "Đang ghi…" : nhan}
      </button>
    );
  }

  function NutPhu({
    ma,
    nhan,
    onClick,
    Icon,
  }: {
    ma: string;
    nhan: string;
    onClick: () => void;
    Icon?: typeof Check;
  }) {
    return (
      <button
        type="button"
        onClick={onClick}
        disabled={dangLuu !== null}
        className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-line bg-surface py-2 px-3 text-xs font-semibold text-ink-soft hover:bg-surface-muted disabled:opacity-50"
      >
        {Icon ? <Icon size={13} /> : null}
        {dangLuu === ma ? "Đang ghi…" : nhan}
      </button>
    );
  }

  const oGhiChu = (
    <input
      value={ghiChu}
      onChange={(e) => setGhiChu(e.target.value)}
      placeholder="Ghi chú (không bắt buộc)"
      className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-[11px] text-ink"
    />
  );

  function than() {
    switch (trangThai) {
      // ── TRƯỚC KHÁM ────────────────────────────────────────────────────────
      case "CHO_XAC_NHAN":
        return (
          <>
            {soDienThoai}
            {oGhiChu}
            <NutChinh
              ma="xn"
              nhan="Đã gọi xác nhận lịch"
              Icon={Phone}
              onClick={() => void ghi("xn", "XAC_NHAN_LICH", "DA_LIEN_HE")}
            />
          </>
        );

      case "NHAC_HEN_MAI":
        return (
          <>
            {soDienThoai}
            {oGhiChu}
            <NutChinh
              ma="nh"
              nhan="Đã gọi nhắc hẹn"
              Icon={Phone}
              onClick={() => void ghi("nh", "NHAC_HEN", "DA_LIEN_HE")}
            />
          </>
        );

      // ── SAU KHÁM ──────────────────────────────────────────────────────────
      case "DA_CHECKIN":
        return (
          <>
            <p className="text-[11px] leading-snug text-ink-soft">
              Xem tình trạng sau khám rồi chọn việc tiếp theo.
            </p>
            <div className="flex gap-2">
              <NutPhu
                ma="trakq"
                nhan="Trả kết quả xét nghiệm"
                onClick={() =>
                  void ghi(
                    "trakq",
                    // CHECK_OUT chứ không phải KHAC: nó đi qua đúng máy trạng
                    // thái (BookingService.apply_action "complete") nên lịch
                    // hẹn chuyển sang COMPLETED — khách này ĐÃ KHÁM. Ghi
                    // "KHAC" thì mọi màn khác vẫn đọc họ là chưa khám xong.
                    "CHECK_OUT",
                    "GHI_NHAN",
                    "Sau khám: đi hướng trả kết quả xét nghiệm",
                  )
                }
              />
              <NutPhu
                ma="taikham"
                nhan="Đặt lịch tái khám"
                Icon={CalendarPlus}
                onClick={async () => {
                  const ok = await ghi(
                    "taikham",
                    "CHECK_OUT",
                    "GHI_NHAN",
                    "Sau khám: đi hướng đặt lịch tái khám",
                  );
                  if (ok) {
                    router.push(
                      `/appointments?bn=${encodeURIComponent(patientCode)}`,
                    );
                  }
                }}
              />
            </div>
          </>
        );

      case "CHO_KQ_XN":
        return (
          <>
            <p className="text-[11px] font-semibold leading-snug text-ink">
              Check với đơn vị xét nghiệm: đã có kết quả hay chưa?
            </p>
            {oGhiChu}
            <div className="flex gap-2">
              <NutPhu
                ma="co"
                nhan="Có rồi"
                Icon={Check}
                onClick={() =>
                  void ghi(
                    "co",
                    "CHECK_XN",
                    "DA_LIEN_HE",
                    ghiChu.trim() || "Đơn vị XN báo ĐÃ có kết quả",
                  )
                }
              />
              <NutPhu
                ma="chua"
                nhan="Chưa có"
                Icon={X}
                onClick={() =>
                  void ghi(
                    "chua",
                    "CHECK_XN",
                    "DA_LIEN_HE",
                    ghiChu.trim() || "Đơn vị XN báo CHƯA có kết quả",
                  )
                }
              />
            </div>
            <p className="text-[11px] leading-snug text-ink-faint">
              Cả hai đều ghi lại kèm thời điểm — “chưa có” cũng là một lần đã
              hỏi, và ca sau cần biết đã hỏi lúc nào.
            </p>
          </>
        );

      case "GOI_LAI":
        return (
          <>
            <p className="text-[11px] leading-snug text-ink-soft">
              Lần trước không nghe máy / không liên lạc được / khách hẹn gọi lại.
            </p>
            {soDienThoai}
            {oGhiChu}
            <NutChinh
              ma="gl"
              nhan="Đã gọi xác nhận lịch hẹn"
              Icon={Phone}
              onClick={() => void ghi("gl", "NHAC_HEN", "DA_LIEN_HE")}
            />
          </>
        );

      case "CHO_BAC_SI":
      case "KQ_CHUA_GUI":
        return (
          <>
            <div className="rounded-xl border border-line bg-surface-muted/60 p-2">
              <div className="mb-1 flex items-center gap-1.5 text-[11px] font-bold text-ink">
                <Upload size={13} /> Kết quả siêu âm / xét nghiệm
              </div>
              <TepKetQua
                clinicPatientId={clinicPatientId}
                appointmentId={appointmentId}
                items={tepKetQua}
              />
            </div>

            {trangThai === "CHO_BAC_SI" ? (
              <>
                <p className="text-[11px] leading-snug text-warning">
                  Kết quả đang chờ BÁC SĨ duyệt. Hỏi bác sĩ trước, chưa gọi
                  khách ở bước này.
                </p>
                {oGhiChu}
                <NutChinh
                  ma="bs"
                  nhan="Đã hỏi bác sĩ"
                  onClick={() =>
                    void ghi(
                      "bs",
                      "KHAC",
                      "DA_LIEN_HE",
                      ghiChu.trim() || "Đã hỏi bác sĩ về kết quả",
                    )
                  }
                />
              </>
            ) : (
              <>
                {oGhiChu}
                <NutChinh
                  ma="gui"
                  nhan="Đã gửi kết quả cho bệnh nhân"
                  Icon={Send}
                  onClick={() =>
                    void ghi(
                      "gui",
                      "TRA_KQ",
                      "DA_LIEN_HE",
                      ghiChu.trim() || "Đã gửi kết quả cho bệnh nhân",
                    )
                  }
                />
                {/* NÓI THẬT VỀ THỨ CHƯA XÂY. Tải lên đã chạy được; GỬI TỰ ĐỘNG
                    thì chưa: Zalo ZNS chỉ gửi được template CHỮ đã duyệt, không
                    đính kèm được tệp hay video. Nên nút trên ghi nhận rằng CSKH
                    đã gửi (qua Zalo cá nhân/Messenger), chứ hệ thống không tự
                    gửi. Nhập nhèm chỗ này là để người trực tin rằng khách đã
                    nhận video trong khi chưa ai gửi. */}
                <p className="rounded-lg border border-dashed border-line px-2 py-1.5 text-[11px] leading-snug text-ink-muted">
                  <b>Đang xây dựng:</b> hệ thống chưa TỰ gửi được ảnh/video cho
                  khách — Zalo ZNS chỉ gửi template chữ. Hiện CSKH gửi bằng kênh
                  của mình rồi bấm nút trên để ghi nhận.
                </p>
              </>
            )}
          </>
        );

      case "DA_TRA_KQ":
        return (
          <>
            <p className="text-[11px] leading-snug text-ink-soft">
              Kết quả đã trả. Còn một việc: có hẹn tái khám hay không.
            </p>
            <div className="flex gap-2">
              <NutPhu
                ma="cotk"
                nhan="Cần tái khám"
                Icon={CalendarPlus}
                onClick={() =>
                  void ghi(
                    "cotk",
                    "KHAC",
                    "DA_LIEN_HE",
                    "Sau trả kết quả: CẦN hẹn tái khám",
                  )
                }
              />
              <NutPhu
                ma="khongtk"
                nhan="Không cần tái khám"
                Icon={X}
                onClick={() =>
                  void ghi(
                    "khongtk",
                    "KHAC",
                    "DA_LIEN_HE",
                    "Sau trả kết quả: KHÔNG cần tái khám",
                  )
                }
              />
            </div>
            <p className="text-[11px] leading-snug text-ink-faint">
              Chọn “cần tái khám” xong thì gõ ngày ở khối <b>Nhắc tái khám</b>{" "}
              để hệ thống tự sinh hai mốc gọi.
            </p>
          </>
        );

      case "HOI_LY_DO_HUY":
        return (
          <>
            <p className="text-[11px] leading-snug text-ink-soft">
              Gọi lại hỏi lý do huỷ (trong vòng 1–14 ngày kể từ lúc huỷ).
            </p>
            {soDienThoai}
            <div className="space-y-1">
              <textarea
                rows={2}
                value={lyDo}
                onChange={(e) => setLyDo(e.target.value)}
                placeholder="Lý do khách huỷ lịch…"
                className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-[11px] text-ink"
              />
              {/* Ô ĐIỀN + TOGGLE BA LÝ DO SẴN, đúng hình dạng đặc tả: người gõ
                  được câu riêng, mà ba trường hợp hay gặp thì bấm một cái là
                  xong — và ba câu ấy giống nhau giữa mọi người, nên về sau đếm
                  được. */}
              <button
                type="button"
                onClick={() => setMoLyDoSan((v) => !v)}
                aria-expanded={moLyDoSan}
                className="text-[11px] font-semibold text-brand-700 hover:underline"
              >
                {moLyDoSan ? "▾ Ẩn lý do có sẵn" : "▸ Chọn lý do có sẵn"}
              </button>
              {moLyDoSan && (
                <ul className="space-y-1">
                  {LY_DO_HUY_SAN.map((l) => (
                    <li key={l}>
                      <button
                        type="button"
                        onClick={() => {
                          setLyDo(l);
                          setMoLyDoSan(false);
                        }}
                        className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-left text-[11px] leading-snug text-ink-soft hover:border-brand-400 hover:bg-brand-50"
                      >
                        {l}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <NutChinh
              ma="huy"
              nhan="Ghi lý do huỷ"
              onClick={() =>
                void ghi("huy", "HOI_LY_DO_HUY", "DA_LIEN_HE", lyDo)
              }
            />
          </>
        );

      case "KHONG_FOLLOW_UP":
        return (
          <>
            <p className="text-[11px] leading-snug text-ink-soft">
              Không cần gọi vào ngày hôm sau. Ghi lại để ca sau khỏi gọi thừa.
            </p>
            {oGhiChu}
            <NutChinh
              ma="kfu"
              nhan="Ghi nhận: không cần gọi"
              onClick={() =>
                void ghi(
                  "kfu",
                  "KHAC",
                  "BO_QUA",
                  ghiChu.trim() || "Không cần follow up sau thủ thuật",
                )
              }
            />
          </>
        );

      case "SAU_SINH_1_THANG":
        return (
          <>
            <p className="text-[11px] leading-snug text-ink-soft">
              Chúc mừng đầy tháng, mời khám lại sau sinh.
            </p>
            {soDienThoai}
            {oGhiChu}
            <NutChinh
              ma="ss"
              nhan="Đã gọi chúc mừng đầy tháng"
              Icon={Phone}
              onClick={() => void ghi("ss", "HOI_THAM", "DA_LIEN_HE")}
            />
          </>
        );

      case "SAU_THU_THUAT_1_NGAY":
        return (
          <>
            <p className="text-[11px] leading-snug text-ink-soft">
              Gọi hỏi thăm tình trạng sau thủ thuật.
            </p>
            {soDienThoai}
            {oGhiChu}
            <NutChinh
              ma="stt"
              nhan="Đã gọi hỏi thăm"
              Icon={Phone}
              onClick={() => void ghi("stt", "HOI_THAM", "DA_LIEN_HE")}
            />
          </>
        );

      default:
        return (
          <p className="text-[11px] leading-snug text-ink-muted">
            Chọn một trạng thái ở cột giữa để thấy việc phải làm và các nút
            tương ứng.
          </p>
        );
    }
  }

  return (
    <div className="space-y-2">
      {(xong || daXong) && (
        <p className="flex items-center gap-1.5 rounded-lg bg-success-bg px-2 py-1.5 text-[11px] font-semibold text-success">
          <Check size={13} /> Đã ghi nhận — trạng thái này đã tích xanh ở cột
          giữa. Bấm lại nếu cần làm thêm lần nữa.
        </p>
      )}
      {than()}
      {loi && <p className="text-[11px] text-danger">{loi}</p>}
    </div>
  );
}
