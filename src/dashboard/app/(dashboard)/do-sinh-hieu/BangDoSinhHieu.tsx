"use client";

// Danh sách chờ đo + ô điền sinh hiệu. Lưu xong TỰ CHUYỂN sang người kế tiếp:
// người đo làm việc theo hàng, không phải theo từng hồ sơ, và bắt họ bấm lại vào
// danh sách sau mỗi người là thêm một thao tác thừa cho mỗi khách trong ngày.
//
// ĐIỆN THOẠI (27/09/2026, đợt 3 — "giao diện PWA cho điện thoại đối với sinh
// hiệu"): điều dưỡng cầm máy đứng cạnh khách.
//   · ô là `components/ui/OSo` (chữ 16px dưới sm → iPhone không tự phóng to khi
//     chạm; chỉ số đếm được mở bàn phím SỐ); Enter sang ô kế, ô cuối "done";
//     chọn khách là con trỏ đứng sẵn ở ô tâm thu. KHÔNG tự nhảy ô theo số chữ
//     số — "36" rồi ".6" là chuyện thường, nhảy sớm là gõ nhầm ô;
//   · lưới 2 cột theo CẶP ở mọi cỡ (tâm thu/tâm trương, mạch/nhiệt độ, cân/cao,
//     nhịp thở/SpO₂), mức đau một dòng;
//   · thanh [Đo xong] DÍNH ĐÁY ngay trên BottomNav (token
//     `--inset-tren-thanh-duoi`, có đệm thanh home iPhone);
//   · dưới lg: đã chọn khách thì danh sách thu thành một thanh
//     "← Danh sách (n chờ)"; "Đã đo hôm nay" gập sẵn;
//   · ô lỗi / ô bất thường tô theo `truong` MÁY CHỦ trả (`parse_vitals_co_truong`,
//     `canh_bao_sinh_hieu`) — ngưỡng không nằm ở đây.
//
// THANH NGÀY (Tuyền 29/09/2026 — "quay lại ngày đó xem và sửa"): chọn ngày cũ →
// mọi lượt check-in hôm đó (`/luot-kham/bang?ngay=`), sửa được lần đo — mỗi lần
// [Đo xong] là MỘT lần đo mới, lần mới nhất thắng, lần cũ còn nguyên để xem lại
// ("Xem các lần đo"). Ngày cũ không có ô "Bỏ qua tư vấn" (máy chủ không trả —
// đổi đường đi là việc của hôm nay). Ngày nằm trên URL (`?ngay=`).

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import Button from "@/components/ui/Button";
import OSo from "@/components/ui/OSo";

import XemLuot from "../_lam-viec/XemLuot";
import { useNgayXem } from "../_lam-viec/dung-ngay-xem";
import ChipLoc from "@/components/ui/ChipLoc";
import SoLuot from "@/components/ui/SoLuot";
import ThanhNgay from "@/components/ui/ThanhNgay";
import { ngayNgan } from "@/lib/thanh-ngay";
import { useNgheBang } from "../dung-nghe-bang";

interface SinhHieu {
  tam_thu: number | null;
  tam_truong: number | null;
  mach: number | null;
  nhiet_do: number | null;
  can_nang: number | null;
  chieu_cao: number | null;
  nhip_tho: number | null;
  spo2: number | null;
  bmi: number | null;
  muc_do_dau: number | null;
  luc: string | null;
  nguoi_do: string | null;
  /** Nhãn máy chủ trả khi số đo của lượt khác cùng buổi ("lượt trước"); null = lượt này. */
  nguon?: string | null;
}

interface Luot {
  visit_id: string;
  ma_bn: string;
  ten: string;
  bac_si: string | null;
  check_in_luc: string | null;
  /** `pending` · `in_progress` · `recorded` — trạng thái THẬT, máy chủ giữ. */
  sinh_hieu_trang_thai: string;
  /** Lúc bấm [Bắt đầu] đo. Trống nếu lưu thẳng mà không ai bấm Bắt đầu. */
  bat_dau_do_luc: string | null;
  bat_dau_do_boi: string | null;
  /** Số tiếp đón chung của quầy — số điều dưỡng đọc khi gọi. */
  so_tiep_don: number | null;
  /** Số booking cấp lúc đặt lịch (23/09/2026). */
  so_booking?: number | null;
  /** Loại khám của lượt (27/09 tối). */
  loai_kham?: string | null;
  /** Phút đã chờ từ check-in + cờ "chờ lâu" — máy chủ tính, màn chỉ tô màu. */
  cho_phut?: number | null;
  cho_lau?: boolean;
  sinh_hieu: SinhHieu | null;
  /** Lượt qua tư vấn: đang bỏ qua chưa, đổi được không. null = không qua tư vấn. */
  tu_van?: { bo_qua: boolean; doi_duoc: boolean } | null;
}

/** Máy chủ nhắc chỉ số bất thường sau khi lưu (`canh_bao_sinh_hieu`). */
interface CanhBao {
  truong: string;
  cau: string;
}

/** Ô nhập — khoá gửi backend, nhãn, đơn vị, khoá đọc lại từ `sinh_hieu`.
 *  THỨ TỰ = thứ tự Enter đi qua VÀ thứ tự trên lưới 2 cột (đi theo cặp).
 *  `nguyen` chỉ đổi bàn phím điện thoại; "phải là số nguyên" do máy chủ quyết. */
const O: readonly {
  gui: string;
  nhan: string;
  don_vi: string;
  doc: keyof SinhHieu;
  batBuoc?: boolean;
  nguyen?: boolean;
  motDong?: boolean;
}[] = [
  { gui: "systolic", nhan: "Huyết áp tâm thu", don_vi: "mmHg", doc: "tam_thu", batBuoc: true, nguyen: true },
  { gui: "diastolic", nhan: "Huyết áp tâm trương", don_vi: "mmHg", doc: "tam_truong", batBuoc: true, nguyen: true },
  { gui: "pulse", nhan: "Mạch", don_vi: "lần/phút", doc: "mach", nguyen: true },
  { gui: "temperature", nhan: "Nhiệt độ", don_vi: "°C", doc: "nhiet_do" },
  { gui: "weight_kg", nhan: "Cân nặng", don_vi: "kg", doc: "can_nang" },
  { gui: "height_cm", nhan: "Chiều cao", don_vi: "cm", doc: "chieu_cao" },
  { gui: "respiratory_rate", nhan: "Nhịp thở", don_vi: "lần/phút", doc: "nhip_tho", nguyen: true },
  { gui: "spo2", nhan: "SpO₂", don_vi: "%", doc: "spo2", nguyen: true },
  { gui: "pain_score", nhan: "Mức độ đau", don_vi: "0–10", doc: "muc_do_dau", nguyen: true, motDong: true },
];

/** Tóm tắt số đang gõ ở thanh dưới — chỉ HIỂN THỊ chữ đã gõ, không kiểm gì. */
function tomTatSo(gia: Readonly<Record<string, string>>): string {
  const v = (k: string) => (gia[k] ?? "").trim();
  const phan: string[] = [];
  if (v("systolic") || v("diastolic")) phan.push(`HA ${v("systolic") || "—"}/${v("diastolic") || "—"}`);
  if (v("pulse")) phan.push(`Mạch ${v("pulse")}`);
  if (v("temperature")) phan.push(`${v("temperature")}°C`);
  if (v("spo2")) phan.push(`SpO₂ ${v("spo2")}%`);
  const trong = O.filter((o) => !v(o.gui)).length;
  if (trong > 0) phan.push(`còn trống ${trong} ô`);
  return phan.length ? phan.join(" · ") : "Chưa nhập chỉ số nào";
}

/** Khách kế tiếp còn chờ đo — theo giờ check-in (cùng thứ tự danh sách). */
function keTiep(ds: readonly Luot[]): Luot | null {
  return (
    [...ds]
      .sort((a, b) => (a.check_in_luc ?? "").localeCompare(b.check_in_luc ?? ""))
      .find((l) => !l.sinh_hieu) ?? null
  );
}

/** Khoá gửi lại cho MỘT lần bấm Lưu. Cùng cách LuotKhamBoard làm — không dùng
 *  crypto.randomUUID vì nó chỉ có trong secure context. Đặt NGOÀI component để
 *  không bị coi là tính toán trong lúc vẽ. */
function khoaGuiLai(): string {
  return `sh-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

function gio(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "—";
  }
}

async function docBang(ngay: string): Promise<{ luot: Luot[] } | { loi: string }> {
  try {
    const r = await fetch(`/api/luot-kham?ngay=${encodeURIComponent(ngay)}`, { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as { luot?: Luot[]; message?: string } | null;
    if (!r.ok) return { loi: d?.message ?? "Không đọc được danh sách khách." };
    return { luot: d?.luot ?? [] };
  } catch {
    return { loi: "Mất kết nối tới máy chủ." };
  }
}

export default function BangDoSinhHieu() {
  const { ngay, homNay, laHomNay, chonNgay } = useNgayXem();
  const [luot, setLuot] = useState<Luot[] | null>(null);
  const [chon, setChon] = useState<string | null>(null);
  const [xemLuot, setXemLuot] = useState<string | null>(null);
  const [gia, setGia] = useState<Record<string, string>>({});
  const [loi, setLoi] = useState<string | null>(null);
  const [xong, setXong] = useState<string | null>(null);
  const [dangLuu, setDangLuu] = useState(false);
  const [dangBatDau, setDangBatDau] = useState(false);
  const [dangDoiTuVan, setDangDoiTuVan] = useState(false);
  // Ô máy chủ báo lỗi (`truong`) — tô đỏ; gõ lại ô ấy thì bỏ tô.
  const [oLoi, setOLoi] = useState<readonly string[]>([]);
  // Chỉ số máy chủ NHẮC sau khi lưu — tô vàng, không chặn.
  const [canhBao, setCanhBao] = useState<readonly CanhBao[]>([]);
  // Dưới lg: đã chọn khách mà muốn xem lại danh sách (không mất số đang gõ).
  const [xemDs, setXemDs] = useState(false);
  // Lượt đã gửi lệnh bắt đầu (tự gửi ở lần gõ đầu tiên) — gửi MỘT lần / lượt.
  const daGuiBatDau = useRef<string | null>(null);
  // Ô nhập theo thứ tự `O` — Enter sang ô kế, chọn khách thì focus ô đầu.
  const oRefs = useRef<(HTMLInputElement | null)[]>([]);
  // Khoá gửi lại của lần [Đo xong] CHƯA thành công: mất mạng rồi bấm lại cùng
  // số → cùng khoá → máy chủ trả biên nhận cũ, không ghi hai lần đo.
  const khoaLuu = useRef<{ visit: string; than: string; khoa: string } | null>(null);

  // Lỗi ĐỌC danh sách tách khỏi lỗi THAO TÁC (27/09/2026, đợt 3 — bấm thật):
  // lưu hỏng → tin realtime nạp lại bảng → bảng đọc được thì `setLoi(null)` xoá
  // mất câu "Huyết áp tâm thu phải lớn hơn tâm trương" trước khi người đo kịp đọc.
  const [loiBang, setLoiBang] = useState<string | null>(null);
  const nhan = useCallback((kq: { luot: Luot[] } | { loi: string }) => {
    if ("loi" in kq) {
      setLoiBang(kq.loi);
      return;
    }
    setLoiBang(null);
    setLuot(kq.luot);
  }, []);
  // SỰ KIỆN THAY NHỊP HỎI (27/09/2026): nghe tin bảng đổi qua dòng SSE chung
  // (`useNgheBang`) → nạp lại NGAY; nhịp hỏi giãn còn 60 giây làm lưới an toàn.
  const [lanNghe, setLanNghe] = useState(0);
  useNgheBang(["visit", "encounter_flow", "vital_measurement", "queue_entry"], () =>
    setLanNghe((n) => n + 1),
  );

  useEffect(() => {
    let huy = false;
    void docBang(ngay).then((kq) => {
      if (!huy) nhan(kq);
    });
    // Làm mới mỗi 20 giây: khách check-in liên tục ở quầy, người đo không nên
    // phải tải lại trang mới thấy người vừa đến.
    const t = setInterval(() => {
      void docBang(ngay).then((kq) => {
        if (!huy) nhan(kq);
      });
    }, 60000);
    return () => {
      huy = true;
      clearInterval(t);
    };
  }, [nhan, lanNghe, ngay]);

  // THỨ TỰ = GIỜ CHECK-IN, người đến trước lên trước (Tuyền 15/09: "hàng chờ =
  // giờ check-in"). Chưa đo đứng trên, đã đo xuống dưới.
  // Tuyền 27/09 tối: chọn xếp theo số check-in hay số booking (chỉ tăng dần —
  // hàng chờ luôn cần người trước lên trước). Số thiếu xuống cuối.
  const [xepTheo, setXepTheo] = useState<"checkin" | "booking">("checkin");
  const { choDo, dangDo, daDo } = useMemo(() => {
    const khoa = (l: Luot) => (xepTheo === "booking" ? l.so_booking : l.so_tiep_don) ?? Number.MAX_SAFE_INTEGER;
    const ds = [...(luot ?? [])].sort(
      (a, b) => khoa(a) - khoa(b) || (a.check_in_luc ?? "").localeCompare(b.check_in_luc ?? ""),
    );
    // "ĐANG ĐO" ĐỌC TỪ TRẠNG THÁI THẬT (23/09/2026), không suy từ giờ gọi.
    // Bản trước lấy `goi_do_luc` làm "đang đo" — tức "đã gọi" bị đọc thành
    // "đã bắt đầu đo", hai chuyện khác nhau. Giờ máy chủ giữ `in_progress`.
    const dangDoThat = (l: Luot) =>
      !l.sinh_hieu && l.sinh_hieu_trang_thai === "in_progress";
    return {
      choDo: ds.filter((l) => !l.sinh_hieu && !dangDoThat(l)),
      dangDo: ds.filter(dangDoThat),
      daDo: ds.filter((l) => l.sinh_hieu),
    };
  }, [luot, xepTheo]);

  const dangChon = (luot ?? []).find((l) => l.visit_id === chon) ?? null;

  const moKhach = (l: Luot, giuBao = false) => {
    setXemDs(false);
    // Bấm lại đúng khách đang điền (vd quay ra danh sách rồi vào lại) — giữ số
    // đang gõ, không nạp lại từ lần đo trước.
    if (l.visit_id === chon) return;
    setChon(l.visit_id);
    // Màn hẹp: danh sách thu lại, khung nhập lên đầu — cuộn về đầu khung rồi
    // con trỏ đứng sẵn ở ô tâm thu (smoke 18/09: chọn xong phải cuộn tay xa).
    const hep = typeof window !== "undefined" && window.innerWidth < 1024;
    requestAnimationFrame(() => {
      if (hep) {
        document.getElementById("khung-do-sinh-hieu")?.scrollIntoView({ block: "start" });
      }
      oRefs.current[0]?.focus({ preventScroll: hep });
    });
    if (!giuBao) setXong(null);
    setLoi(null);
    setOLoi([]);
    setCanhBao([]);
    const cu: Record<string, string> = {};
    for (const o of O) {
      const v = l.sinh_hieu?.[o.doc];
      cu[o.gui] = v === null || v === undefined ? "" : String(v);
    }
    setGia(cu);
  };

  // Enter = sang ô kế (bàn phím điện thoại hiện "Tiếp"); ô cuối = "Xong", cất
  // bàn phím. KHÔNG lưu bằng Enter: lưu là một quyết định, bấm [Đo xong].
  const enterSangO = (i: number) => (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== "Enter" || e.nativeEvent.isComposing) return;
    e.preventDefault();
    const ke = oRefs.current[i + 1];
    if (ke) ke.focus();
    else e.currentTarget.blur();
  };

  // KHÔNG CÒN NÚT [BẮT ĐẦU] (Tuyền 24/09/2026: "không cần ấn bắt đầu đo nữa, cứ
  // nhập thông tin vào sẽ phát sinh event từ lúc nhập vào đầu tiên và đo xong
  // lúc ấn đo xong"). Lần GÕ ĐẦU TIÊN tự gửi lệnh bắt đầu (mốc bắt đầu = lúc
  // gõ); [Đo xong] = lưu. Máy chủ vẫn giữ cổng VITALS_NOT_STARTED — lỡ bấm Đo
  // xong trước khi lệnh bắt đầu kịp đi thì `luu` tự gửi bắt đầu trước.
  //
  // (Cũ) [BẮT ĐẦU] ĐO — thay cho [Gọi vào đo] (Tuyền chốt 23/09/2026: `Gọi vào →
  // Bắt đầu` là hai bước cho một việc). Máy chủ chuyển `pending → in_progress`
  // và ghi ai bắt đầu, lúc nào. Bấm lại chính mình thì không sao; người khác đã
  // bắt đầu thì máy chủ từ chối kèm tên — câu ấy hiện nguyên văn ở đây.
  //
  // LẦN LƯU ĐẦU PHẢI SAU [Bắt đầu] (chốt 23/09/2026) — không thì lại có lượt
  // "đã đo" mà không biết bắt đầu lúc nào. Máy chủ là cửa chặn thật
  // (VITALS_NOT_STARTED); ở đây khoá nút Lưu và nói rõ lý do để khỏi ăn lỗi.
  // Ô nhập VẪN gõ được: gõ chưa phải lưu, bấm Bắt đầu xong số vẫn còn.
  const batDau = async (): Promise<boolean> => {
    if (!dangChon) return false;
    daGuiBatDau.current = dangChon.visit_id;
    setDangBatDau(true);
    setLoi(null);
    try {
      const r = await fetch("/api/luot-kham", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": khoaGuiLai() },
        body: JSON.stringify({ thao_tac: "bat-dau-do", id: dangChon.visit_id, du_lieu: {} }),
      });
      const d = (await r.json().catch(() => null)) as { message?: string; error?: string } | null;
      if (!r.ok) {
        daGuiBatDau.current = null;
        setLoi(d?.message ?? d?.error ?? "Không bắt đầu đo được.");
        // Thường là người khác vừa bắt đầu đo khách này: nạp lại để thấy
        // "Đang đo" — hết `pending` thì các lần gõ sau không gửi lại nữa.
        nhan(await docBang(ngay));
        return false;
      }
      nhan(await docBang(ngay));
      return true;
    } catch {
      daGuiBatDau.current = null;
      setLoi("Mất kết nối — CHƯA bắt đầu đo.");
      return false;
    } finally {
      setDangBatDau(false);
    }
  };

  const luu = async () => {
    if (!dangChon) return;
    const chuaBd = !dangChon.sinh_hieu && dangChon.sinh_hieu_trang_thai === "pending";
    if (chuaBd && daGuiBatDau.current !== dangChon.visit_id && !(await batDau())) return;
    setDangLuu(true);
    setLoi(null);
    setOLoi([]);
    setCanhBao([]);
    try {
      const du_lieu: Record<string, string> = {};
      for (const o of O) if (gia[o.gui]?.trim()) du_lieu[o.gui] = gia[o.gui].trim();
      const than = JSON.stringify({ thao_tac: "sinh-hieu", id: dangChon.visit_id, du_lieu });
      const cu = khoaLuu.current;
      const khoa =
        cu && cu.visit === dangChon.visit_id && cu.than === than ? cu.khoa : khoaGuiLai();
      khoaLuu.current = { visit: dangChon.visit_id, than, khoa };
      const r = await fetch("/api/luot-kham", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": khoa,
        },
        body: than,
      });
      const d = (await r.json().catch(() => null)) as {
        message?: string;
        error?: string;
        truong?: unknown;
        canh_bao?: unknown;
      } | null;
      if (!r.ok) {
        setLoi(d?.message ?? d?.error ?? "Không lưu được sinh hiệu.");
        // Máy chủ chỉ ra ô nào (`truong`) → tô đỏ và đưa con trỏ tới ô đầu tiên.
        const tenO = Array.isArray(d?.truong)
          ? d.truong.filter((t): t is string => typeof t === "string")
          : [];
        setOLoi(tenO);
        const dau = O.findIndex((o) => tenO.includes(o.gui));
        if (dau >= 0) oRefs.current[dau]?.focus();
        return;
      }
      khoaLuu.current = null;
      const nhac = Array.isArray(d?.canh_bao)
        ? d.canh_bao.filter(
            (c): c is CanhBao =>
              !!c &&
              typeof c === "object" &&
              typeof (c as CanhBao).truong === "string" &&
              typeof (c as CanhBao).cau === "string",
          )
        : [];
      const ten = dangChon.ten;
      const kq = await docBang(ngay);
      nhan(kq);
      if (nhac.length > 0) {
        // Có chỉ số bất thường: ĐÃ LƯU (nhắc, không chặn) nhưng ĐỨNG LẠI ở
        // khách này để người đo thấy ô tô vàng — tự sang người kế thì lời nhắc
        // trôi mất. Sang người kế bằng nút [Sang khách kế tiếp].
        setCanhBao(nhac);
        setXong(`Đã lưu sinh hiệu cho ${ten} — có chỉ số cần lưu ý.`);
        return;
      }
      // Sang NGƯỜI KẾ TIẾP còn chờ đo — báo SAU khi chuyển (moKhach xoá báo cũ,
      // trước đây câu "đã lưu" biến mất ngay nên người đo không kịp thấy).
      if ("luot" in kq) {
        const ke = keTiep(kq.luot);
        if (ke) moKhach(ke, true);
        else setChon(null);
      }
      setXong(`Đã lưu sinh hiệu cho ${ten}.`);
    } catch {
      setLoi("Mất kết nối — sinh hiệu CHƯA được lưu. Số vẫn còn, bấm [Đo xong] lại khi có mạng.");
    } finally {
      setDangLuu(false);
    }
  };

  // Ô "Bỏ qua bác sĩ tư vấn" — ÁP NGAY vào vị trí khách (Tuyền 25/09/2026: "là
  // lựa chọn và áp luôn cho vị trí của khách"): tick → hàng bác sĩ chính, bỏ
  // tick → về hàng tư vấn. Ô đọc trạng thái THẬT từ máy chủ, nên lỡ tay thì bỏ
  // tick là khách về lại (khi bên nhận chưa bắt đầu).
  const doiTuVan = async (boQua: boolean) => {
    if (!dangChon) return;
    const ten = dangChon.ten;
    setDangDoiTuVan(true);
    setLoi(null);
    setXong(null);
    try {
      const r = await fetch("/api/luot-kham", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": khoaGuiLai() },
        body: JSON.stringify({
          thao_tac: "bo-qua-tu-van",
          id: dangChon.visit_id,
          du_lieu: { bo_qua: boQua },
        }),
      });
      const d = (await r.json().catch(() => null)) as { message?: string; error?: string } | null;
      if (!r.ok) {
        setLoi(d?.message ?? d?.error ?? "Không đổi được.");
        return;
      }
      nhan(await docBang(ngay));
      setXong(
        boQua
          ? `${ten}: bỏ qua tư vấn — đã chuyển sang hàng bác sĩ chính.`
          : `${ten}: đã đưa lại vào hàng tư vấn.`,
      );
    } catch {
      setLoi("Mất kết nối — CHƯA đổi.");
    } finally {
      setDangDoiTuVan(false);
    }
  };

  // Thanh ngày + câu "đang xem ngày cũ" — vẽ cả lúc đang tải.
  const thanhNgay = (
    <>
      <ThanhNgay
        motNgay
        nhan="Xem khách đo sinh hiệu theo ngày"
        khoang={{ tu: ngay, den: ngay }}
        homNay={homNay}
        soNgaySau={0}
        dangTai={luot === null}
        onChon={(k) => {
          const moi = k?.den ?? homNay;
          if (moi === ngay) return;
          setLuot(null);
          setChon(null);
          setXong(null);
          setLoi(null);
          chonNgay(moi);
        }}
      />
      {!laHomNay ? (
        <p className="rounded-control border border-warning bg-warning-bg px-3 py-2 text-body text-warning">
          Đang xem ngày {ngayNgan(ngay)} — mọi khách check-in hôm đó. Sửa lần đo thì
          lần mới nhất thắng, các lần trước vẫn giữ để xem lại.
        </p>
      ) : null}
    </>
  );

  if (luot === null) {
    return (
      <div className="grid gap-4">
        {thanhNgay}
        {loiBang ? (
          <p role="alert" className="text-body text-danger">{loiBang}</p>
        ) : (
          <p className="text-body text-ink-muted">Đang tải…</p>
        )}
      </div>
    );
  }

  // Chưa có mốc bắt đầu cho khách đang mở — lần gõ đầu tiên sẽ tạo nó.
  const chuaBatDau =
    !!dangChon && !dangChon.sinh_hieu && dangChon.sinh_hieu_trang_thai === "pending";

  // Dòng khách (Tuyền 27/09 tối): bỏ ô số tròn + chip trạng thái lặp tên mục;
  // hai số ghép một viên (SoLuot); bên phải là thông tin CÓ ÍCH: chờ bao lâu
  // (cam khi máy chủ báo chờ lâu) / ai đang đo / đo lúc nào.
  const MotDong = ({ l }: { l: Luot }) => {
    const phai = l.sinh_hieu ? (
      <span className="text-meta text-success">
        đo {gio(l.sinh_hieu.luc)}
        {l.sinh_hieu.nguon ? ` (${l.sinh_hieu.nguon})` : ""}
      </span>
    ) : l.sinh_hieu_trang_thai === "in_progress" ? (
      <span className="text-meta text-brand-700">
        {chon === l.visit_id ? "đang mở" : `${l.bat_dau_do_boi ?? "Có người"} đang đo`}
      </span>
    ) : l.cho_phut != null ? (
      <span className={`text-meta tabular-nums ${l.cho_lau ? "font-semibold text-warning" : "text-ink-muted"}`}>
        chờ {l.cho_phut >= 60 ? `${Math.floor(l.cho_phut / 60)}g${String(l.cho_phut % 60).padStart(2, "0")}′` : `${l.cho_phut}′`}
      </span>
    ) : null;
    return (
      <li>
        <button
          type="button"
          onClick={() => moKhach(l)}
          className={`flex w-full items-center gap-3 border-b border-line px-3 py-2.5 text-left hover:bg-brand-50 ${
            chon === l.visit_id ? "bg-brand-50" : ""
          }`}
        >
          <SoLuot dang="tron" booking={l.so_booking} checkin={l.so_tiep_don} />
          {/* Tên + số LUÔN đủ ở mọi cỡ màn (Tuyền 27/09 tối): tên xuống dòng chứ
              không cắt; trạng thái (chờ bao lâu / ai đang đo) nằm ở dòng phụ. */}
          <span className="min-w-0 flex-1">
            <span className="block break-words font-semibold text-ink">{l.ten}</span>
            <span className="flex flex-wrap items-baseline gap-x-2 text-meta text-ink-muted">
              <span>{[l.loai_kham, l.bac_si].filter(Boolean).join(" · ") || l.ma_bn}</span>
              {phai}
            </span>
          </span>
        </button>
      </li>
    );
  };

  const oCanhBao = new Set(canhBao.map((c) => c.truong));
  const khachKe = dangChon
    ? keTiep((luot ?? []).filter((l) => l.visit_id !== dangChon.visit_id))
    : null;
  // Dưới lg chỉ một trong hai khung: danh sách (chưa chọn / đang xem lại) hoặc ô nhập.
  const anDs = !!dangChon && !xemDs;

  return (
    <div className="grid gap-4">
    {thanhNgay}
    <div className="grid gap-4 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
      {/* Dưới lg, đã chọn khách: danh sách thu thành MỘT thanh (27/09/2026,
          đợt 3) — ô nhập lên đầu màn, không phải cuộn qua vài chục khách. */}
      {dangChon ? (
        <div className="lg:hidden">
          <Button
            variant="secondary"
            size="lg"
            className="w-full justify-start"
            aria-expanded={xemDs}
            onClick={() => setXemDs((x) => !x)}
          >
            {xemDs ? `→ Quay lại ${dangChon.ten}` : `← Danh sách (${choDo.length} chờ)`}
          </Button>
        </div>
      ) : null}
      <section
        className={`overflow-hidden rounded-card border border-line bg-surface shadow-card ${
          anDs ? "hidden lg:block" : ""
        }`}
      >
        {dangDo.length > 0 ? (
          <>
            <p className="border-b border-line bg-surface-muted px-3 py-2 text-sm font-semibold text-ink">
              Đang đo ({dangDo.length})
            </p>
            <ul>
              {dangDo.map((l) => (
                <MotDong key={l.visit_id} l={l} />
              ))}
            </ul>
          </>
        ) : null}
        <div className="flex flex-wrap items-center justify-between gap-2 border-y border-line bg-surface-muted px-3 py-2">
          <p className="text-sm font-semibold text-ink">Chờ đo ({choDo.length})</p>
          <ChipLoc
            nhan="Xếp theo"
            muc={[
              { ma: "checkin", nhan: "Check-in" },
              { ma: "booking", nhan: "Booking" },
            ]}
            chon={xepTheo}
            onChon={setXepTheo}
          />
        </div>
        <ul>
          {choDo.length === 0 ? (
            <li className="px-3 py-4 text-meta text-ink-muted">Không còn ai chờ đo.</li>
          ) : (
            choDo.map((l) => <MotDong key={l.visit_id} l={l} />)
          )}
        </ul>
        {/* GẬP SẴN (27/09/2026, đợt 3): danh sách đã đo dài dần trong ngày và
            đẩy hàng chờ ra khỏi màn điện thoại; mở khi cần sửa lại một lần đo. */}
        {daDo.length > 0 ? (
          // Ngày cũ: mở sẵn — xem lại để sửa là lý do chọn ngày ấy.
          <details key={ngay} className="group" open={!laHomNay}>
            <summary className="flex cursor-pointer list-none items-center justify-between border-y border-line bg-surface-muted px-3 py-2 text-sm font-semibold text-ink">
              Đã đo {laHomNay ? "hôm nay" : `ngày ${ngayNgan(ngay)}`} ({daDo.length})
              <span aria-hidden className="text-meta text-ink-muted group-open:rotate-180">
                ▾
              </span>
            </summary>
            <ul>
              {daDo.map((l) => (
                <MotDong key={l.visit_id} l={l} />
              ))}
            </ul>
          </details>
        ) : null}
      </section>

      <section
        id="khung-do-sinh-hieu"
        className={`rounded-card border border-line bg-surface p-4 shadow-card ${
          !dangChon || xemDs ? "hidden lg:block" : ""
        }`}
      >
        {!dangChon ? (
          <p className="py-10 text-center text-body text-ink-muted">
            Chọn một khách bên trái để điền sinh hiệu.
          </p>
        ) : (
          <>
            <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
              <p className="flex flex-wrap items-center gap-2 text-lg font-semibold text-ink">
                {dangChon.ten}
                <SoLuot booking={dangChon.so_booking} checkin={dangChon.so_tiep_don} />
              </p>
              <p className="text-meta text-ink-muted">
                {dangChon.ma_bn} · check-in {gio(dangChon.check_in_luc)}
                {dangChon.sinh_hieu?.nguoi_do
                  ? ` · lần đo trước: ${dangChon.sinh_hieu.nguoi_do} lúc ${gio(dangChon.sinh_hieu.luc)}${dangChon.sinh_hieu.nguon ? ` (${dangChon.sinh_hieu.nguon})` : ""}`
                  : ""}
                {dangChon.bat_dau_do_luc && !dangChon.sinh_hieu
                  ? ` · bắt đầu đo lúc ${gio(dangChon.bat_dau_do_luc)}${dangChon.bat_dau_do_boi ? ` (${dangChon.bat_dau_do_boi})` : ""}`
                  : ""}
              </p>
              {/* Đã đo: xem lại mọi lần đo (người đo, giờ) và lượt trước. */}
              {dangChon.sinh_hieu ? (
                <Button
                  size="sm"
                  variant="ghost"
                  className="mt-1 -ml-3"
                  onClick={() => setXemLuot(dangChon.visit_id)}
                >
                  Xem các lần đo &amp; lượt trước
                </Button>
              ) : null}
              {xemLuot ? <XemLuot visitId={xemLuot} onDong={() => setXemLuot(null)} /> : null}
              </div>
            </div>
            {canhBao.length > 0 ? (
              <ul
                role="status"
                className="mb-3 space-y-1 rounded-control border border-warning bg-warning-bg px-3 py-2 text-meta text-warning"
              >
                {canhBao.map((c) => (
                  <li key={c.truong}>{c.cau}</li>
                ))}
              </ul>
            ) : null}
            {/* HAI CỘT THEO CẶP ở mọi cỡ (27/09/2026, đợt 3) — 375 cũng vậy:
                tâm thu cạnh tâm trương, mạch cạnh nhiệt độ… đúng thứ tự đo.
                `items-end`: nhãn dài xuống dòng thì ô vẫn thẳng hàng. */}
            <div className="grid grid-cols-2 items-end gap-3">
              {O.map((o, i) => (
                <label key={o.gui} className={`block min-w-0 ${o.motDong ? "col-span-2" : ""}`}>
                  <span className="mb-1 block text-sm font-medium text-ink">
                    {o.nhan}
                    {o.don_vi ? <span className="ml-1 text-meta text-ink-muted">({o.don_vi})</span> : null}
                  </span>
                  <OSo
                    ref={(el) => {
                      oRefs.current[i] = el;
                    }}
                    rong="day"
                    nguyen={o.nguyen}
                    enterKeyHint={i === O.length - 1 ? "done" : "next"}
                    onKeyDown={enterSangO(i)}
                    loi={oLoi.includes(o.gui)}
                    canhBao={oCanhBao.has(o.gui)}
                    title={o.nhan}
                    value={gia[o.gui] ?? ""}
                    onChange={(v) => {
                      setGia((g) => ({ ...g, [o.gui]: v }));
                      setOLoi((ds) => (ds.includes(o.gui) ? ds.filter((t) => t !== o.gui) : ds));
                      // Gõ đầu tiên = bắt đầu đo (một lần / lượt).
                      if (
                        chuaBatDau &&
                        !dangBatDau &&
                        daGuiBatDau.current !== dangChon.visit_id
                      ) {
                        void batDau();
                      }
                    }}
                  />
                </label>
              ))}
            </div>
            {/* BMI KHÔNG có ô nhập (S0-3, 18/09/2026): máy chủ tự tính từ cân
                nặng và chiều cao khi lưu, số gõ tay trước đây từng thắng số
                tính. Ở đây chỉ hiện lại con số đã lưu. */}
            <p className="mt-3 text-meta text-ink-muted">
              BMI (tự tính từ cân nặng, chiều cao khi lưu):{" "}
              <span className="font-semibold tabular-nums text-ink">
                {dangChon.sinh_hieu?.bmi ?? "—"}
              </span>
            </p>
            {/* THANH DÍNH ĐÁY (27/09/2026, đợt 3): trên điện thoại [Đo xong]
                luôn trong tầm ngón cái, ngay trên BottomNav (có đệm thanh home
                iPhone); ≥md dính sát đáy khung. Thông báo nằm TRONG thanh —
                17/09: đặt trên đầu thì khối ô nhập tụt xuống, bấm lệch ô. */}
            <div className="sticky bottom-tren-thanh-duoi z-10 mt-4 flex flex-wrap items-center justify-end gap-3 rounded-card border border-line bg-surface p-3 shadow-panel md:bottom-3">
              {/* Tên + tóm tắt số vừa gõ (27/09 tối): soát một chỗ trước khi lưu. */}
              <div className="min-w-0 flex-1 basis-full sm:basis-auto">
                <p className="truncate text-body font-semibold text-ink">{dangChon.ten}</p>
                <p className="truncate text-meta text-ink-muted">{tomTatSo(gia)}</p>
              </div>
              {loi || loiBang ? (
                <p role="alert" className="w-full rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger sm:mr-auto sm:w-auto">
                  {loi ?? loiBang}
                </p>
              ) : xong ? (
                <p role="status" className="w-full rounded-control border border-success bg-success-bg px-3 py-2 text-meta text-success sm:mr-auto sm:w-auto">
                  {xong}
                </p>
              ) : null}
              {/* Tick = khách không qua bác sĩ tư vấn, vào thẳng hàng bác sĩ chính;
                  bỏ tick = về lại hàng tư vấn. ÁP NGAY, không đợi [Đo xong]
                  (Tuyền 25/09/2026). Lượt không qua tư vấn thì không hiện ô. */}
              {dangChon.tu_van ? (
                <label className="flex min-h-10 w-full items-center gap-2 text-sm text-ink sm:w-auto">
                  <input
                    type="checkbox"
                    className="size-4 shrink-0 accent-brand-600"
                    checked={dangChon.tu_van.bo_qua}
                    disabled={dangDoiTuVan || !dangChon.tu_van.doi_duoc}
                    onChange={(e) => void doiTuVan(e.target.checked)}
                  />
                  Bỏ qua bác sĩ tư vấn — vào thẳng bác sĩ chính
                  {!dangChon.tu_van.doi_duoc ? (
                    <span className="text-meta text-ink-muted">
                      ({dangChon.tu_van.bo_qua ? "bác sĩ chính đã khám" : "tư vấn đã nhận khách"})
                    </span>
                  ) : null}
                </label>
              ) : null}
              {canhBao.length > 0 && khachKe ? (
                <Button
                  variant="secondary"
                  size="lg"
                  className="flex-1 sm:flex-none"
                  onClick={() => moKhach(khachKe)}
                >
                  Sang khách kế tiếp →
                </Button>
              ) : null}
              <Button
                variant="primary"
                size="lg"
                className="flex-1 sm:flex-none"
                onClick={luu}
                disabled={dangLuu}
              >
                {dangLuu ? "Đang lưu…" : khachKe && canhBao.length === 0 ? "Đo xong → khách kế" : "Đo xong"}
              </Button>
            </div>
          </>
        )}
      </section>
    </div>
    </div>
  );
}
