"use client";

// MỘT PHÒNG DỊCH VỤ: siêu âm, thủ thuật, lấy mẫu (Tuyền chốt 16/09/2026).
//
// Trái: hàng chờ của phòng. Phải: khách đang chọn —
//   Bắt đầu  → mở một LẦN LÀM (giờ vào) + dời con trỏ "khách đang ở đâu"
//   phiếu kết quả + gửi ảnh/video/PDF vào ô (xem ngay tại chỗ)
//   Xong     → đóng lần làm ấy, khách sang bước tiếp theo
//
// MỘT NÚT CHÍNH, NHIỀU SỰ THẬT PHÍA SAU (ChatGPT tin số 156, Tuyền tin số 157: *"chỉ cần
// 1 nút bắt đầu … xử lý thông minh phía sau, nút chỉ 1"*). Người làm thấy đúng
// hai nút trong cả ca: [Bắt đầu] rồi [Hoàn tất]. Bấm [Hoàn tất] một lần, hệ
// thống ghi cả ba việc: xác nhận toàn bộ phiếu · đóng dịch vụ
// (`service.completed`) · phát "đã có kết quả" (`result.ready`) nếu dịch vụ
// này có kết quả ngay tại phòng.
//
// Dịch vụ KHÔNG có phiếu kết quả (lấy mẫu gửi đi) thì [Hoàn tất] gọi thẳng
// lệnh đóng dịch vụ — vẫn một nút, vẫn một chỗ bấm.
//
// BA NGOẠI LỆ nằm ở hàng phụ, không phải nút chính: Không làm được (chưa bắt
// đầu) · Dừng giữa chừng (đã bắt đầu) · Làm lại. Đời thật có máy hỏng lúc
// 10:05 và khách đổi ý ở cửa phòng — nhưng đó là ngoại lệ, và giao diện không
// được bày ngoại lệ ngang hàng với việc thường. Bốn thứ KHÔNG BAO GIỜ tự động
// khi dừng: không tự hoàn tiền, không tự đánh dấu xong, không tự mở lần mới,
// không tự đổi phòng.
//
// Ai bấm được là do MÁY CHỦ quyết — nay theo QUYỀN (khối "Thực hiện dịch vụ"),
// không theo vai. Màn này không tự đoán, chỉ hiện câu từ chối của máy chủ.
// Ẩn nút không phải bảo mật: mỗi lệnh vẫn tự hỏi quyền của nó khi bấm.
//
// BỎ HẲN [GỌI VÀO] (Tuyền chốt 23/09/2026): `Gọi vào → Bắt đầu` là hai bước
// cho một việc. Nay chỉ còn `Chờ → Bắt đầu → Hoàn tất`. Lệnh Bắt đầu đã hấp
// thụ phần việc thật mà [Gọi vào] từng làm — dời con trỏ "khách đang ở đâu" —
// nên đây không phải xoá một cái nút rồi để state mắc lại.
//
// `called_at` trong database GIỮ NGUYÊN: lượt cũ còn đọc được giờ gọi. Chỉ
// thôi ghi mới từ màn này.
//
// NGÀY CŨ (Tuyền 29/09/2026): thanh chọn ngày xem lại hàng chờ của một ngày
// đã qua. Phòng lấy mẫu luôn có ô tệp — lịch sử các lần tải, tải thêm bất kỳ
// lúc nào.
//
// NGÀY CŨ SỬA ĐƯỢC Ở MỌI PHÒNG (Tuyền 29/09/2026 — "để bác sĩ hay bất kỳ ai quay
// lại ngày đó xem và sửa"): bỏ khoá chỉ-xem. Ngày cũ đủ nút như hôm nay — mở
// phiếu kết quả, sửa, Hoàn tất / Sửa lại, tải tệp; dịch vụ chưa làm thì Bắt đầu /
// Xong ghi GIỜ THẬT lúc bấm (như phòng Lấy mẫu). Sửa kết quả đã Hoàn tất vẫn đi
// đường "Sửa lại" (giữ bản cũ). Ngày nằm trên URL (`?ngay=`) để F5 không mất.
//
// KẾT QUẢ KHÔNG NẰM TRONG LỆNH "XONG" nữa. "Đã làm xong" và "đã có kết quả" là
// hai sự thật khác nhau — kết quả đi qua phiếu (`PhieuKetQua`), có vòng đời và
// người chịu trách nhiệm riêng. Hoàn tất phiếu lúc dịch vụ còn đang làm dở thì
// máy chủ đóng hộ dịch vụ và NÓI RA là đã đóng hay chưa.

import { useCallback, useEffect, useState } from "react";

import {
  cauDangOPhong,
  docBang,
  guiThaoTac,
  gioVn,
  soPhutTu,
  LY_DO_TIENG_VIET,
  type DemPhong,
  type DongHangCho,
  type Phong,
  type PhongHomNay,
  type ThucHien,
} from "../../_lam-viec/api";
import { type LuaChonBacSi } from "../../_lam-viec/ChonBacSiLam";
import HangChoCot from "../../_lam-viec/HangChoCot";
import KhungTep from "../../_lam-viec/KhungTep";
import PhieuKetQua from "../../_lam-viec/PhieuKetQua";
import XemLuot from "../../_lam-viec/XemLuot";
import ChuaXepPhong, { type KhachChuaXep } from "./ChuaXepPhong";
import SapDenPhong, { type KhachSapDen } from "./SapDenPhong";
import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import ChipLoc from "@/components/ui/ChipLoc";
import ThanhNgay from "@/components/ui/ThanhNgay";
import NutHoanTac from "@/components/ui/NutHoanTac";
import NutInPhieu from "@/components/ui/NutInPhieu";
import ThongBaoHoanTac, { type ThongBao } from "@/components/ui/ThongBaoHoanTac";
import { lenhHoanTac } from "../../_lam-viec/hoan-tac";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";
import { useNgheBang } from "../../dung-nghe-bang";
import { tienVn } from "@/lib/phieu-kham";
import { ngayNgan } from "@/lib/thanh-ngay";
import { useNgayXem } from "../../_lam-viec/dung-ngay-xem";
import { nhipKhiHien } from "@/lib/nhip-khi-hien";

/** Người đang xem đứng làn nào của phòng nhiều bác sĩ (máy chủ trả). */
interface LanCuaToi {
  co: boolean;
  lan: number[];
  nhan: string | null;
}

/** Link "Phải dừng giữa chừng? / Không làm được?" ở phòng — OFF 24/09/2026. */
const NUT_NGOAI_LE = false;

type LoaiPhong = "SIEU_AM" | "THU_THUAT" | "LAY_MAU" | "KHAC";

function loaiCua(node: string | null): LoaiPhong {
  if (!node) return "KHAC";
  if (node === "DICHVU-SIEUAM") return "SIEU_AM";
  if (node.startsWith("DICHVU-LAYMAU")) return "LAY_MAU";
  if (node === "DICHVU-THUTHUAT" || node === "DICHVU-SANGLOC-COTUCUNG") {
    return "THU_THUAT";
  }
  return "KHAC";
}

const NUT_XONG: Record<LoaiPhong, string> = {
  SIEU_AM: "Siêu âm xong",
  THU_THUAT: "Làm thủ thuật xong",
  LAY_MAU: "Đã lấy mẫu",
  KHAC: "Làm xong",
};

export default function PhongDichVu({ ma }: { ma: string }) {
  const [phong, setPhong] = useState<Phong | null>(null);
  const [khongCo, setKhongCo] = useState(false);
  const [hang, setHang] = useState<DongHangCho[] | null>(null);
  const [chuaXep, setChuaXep] = useState<KhachChuaXep[]>([]);
  // NHẬN KHÁCH TẠI PHÒNG (dây `nhan_tai_phong`, 07/10/2026): khối Sắp đến theo
  // khách + ba số của phòng — máy chủ trả, màn chỉ vẽ.
  const [taiPhong, setTaiPhong] = useState(false);
  const [sapDen, setSapDen] = useState<KhachSapDen[]>([]);
  const [bacSiPhong, setBacSiPhong] = useState<LuaChonBacSi[]>([]);
  const [dem, setDem] = useState<DemPhong | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [chonId, setChonId] = useState<string | null>(null);
  const [lanNap, setLanNap] = useState(0);
  const { ngay, homNay, chonNgay } = useNgayXem();
  /** Máy chủ nói ngày đang xem có phải hôm nay không (ngày rác → hôm nay). */
  const [laHomNay, setLaHomNay] = useState(true);
  // PHÒNG NHIỀU BÁC SĨ (30/09/2026): người đang trực một làn của phòng thì mặc
  // định chỉ thấy khách của làn mình (+ khách chưa chọn bác sĩ); tắt được để
  // xem cả phòng. Máy chủ quyết ai thuộc làn nào (`lan_toi`), màn chỉ lọc.
  const [lanToi, setLanToi] = useState<LanCuaToi | null>(null);
  const [cheDoLan, setCheDoLan] = useState<"lan" | "ca_phong">("lan");
  // "Đã xong … · Hoàn tác" vài giây sau khi bấm Xong (Tuyền 01/10/2026). Ở
  // cấp màn để còn hiện khi người làm bấm sang khách kế tiếp.
  const [thongBao, setThongBao] = useState<ThongBao | null>(null);
  const dongThongBao = useCallback(() => setThongBao(null), []);

  useEffect(() => {
    let huy = false;
    void docBang<PhongHomNay>("phong-hom-nay").then((kq) => {
      if (huy) return;
      if (!kq.ok) {
        setLoi(kq.loi);
        return;
      }
      // `room_id` là định danh (CORE-C, 23/09/2026); mã phòng cũ vẫn mở được
      // để link đã lưu trước đó không gãy.
      const p =
        kq.data.tat_ca_phong.find((x) => x.id === ma || x.code === ma) ?? null;
      setPhong(p);
      setKhongCo(p === null);
    });
    return () => {
      huy = true;
    };
  }, [ma]);

  useEffect(() => {
    if (!phong) return;
    let huy = false;
    const nap = async () => {
      const kq = await docBang<{
        hang_cho: DongHangCho[];
        chua_xep_phong?: KhachChuaXep[];
        nhan_tai_phong?: boolean;
        sap_den_phong?: KhachSapDen[];
        bac_si_phong?: LuaChonBacSi[];
        dem?: DemPhong | null;
        hom_nay?: boolean;
        lan_cua_toi?: LanCuaToi;
      }>("hang-cho", {
        phong: phong.id,
        ngay,
      });
      if (huy) return;
      if (kq.ok) {
        setLoi(null);
        setHang(kq.data.hang_cho.filter((d) => d.loai === "DICH_VU"));
        setChuaXep(kq.data.chua_xep_phong ?? []);
        setTaiPhong(kq.data.nhan_tai_phong ?? false);
        setSapDen(kq.data.sap_den_phong ?? []);
        setBacSiPhong(kq.data.bac_si_phong ?? []);
        setDem(kq.data.dem ?? null);
        setLaHomNay(kq.data.hom_nay ?? true);
        setLanToi(kq.data.lan_cua_toi?.co ? kq.data.lan_cua_toi : null);
      } else setLoi(kq.loi);
    };
    void nap();
    // SỰ KIỆN THAY NHỊP HỎI (27/09/2026): nghe tin bảng đổi qua dòng SSE chung
    // (`useNgheBang`) → nạp lại NGAY; nhịp hỏi giãn còn 60 giây làm lưới an toàn.
    const goNhip = nhipKhiHien(() => void nap(), 60000, { hoiKhiHien: false });
    return () => {
      huy = true;
      goNhip();
    };
  }, [phong, lanNap, ngay]);

  const napLai = useCallback(() => setLanNap((n) => n + 1), []);
  useNgheBang(["queue_entry", "service_order", "visit", "form_instance", "tep_ket_qua"], napLai);

  if (khongCo) {
    return (
      <p className="rounded-card border border-danger bg-danger-bg p-4 text-body text-danger">
        Không có phòng “{ma}”, hoặc phòng đã tắt.
      </p>
    );
  }

  const loc = lanToi !== null && cheDoLan === "lan";
  const ca = hang ?? [];
  const ds = loc ? ca.filter((d) => d.lan_toi !== false) : ca;
  const macDinh =
    ds.find((d) => d.trang_thai === "serving") ??
    ds.find((d) => d.trang_thai === "waiting" || d.trang_thai === "called") ??
    null;
  const chon = ds.find((d) => d.id === chonId) ?? macDinh;
  // GHIM KHÁCH ĐANG HIỆN (Tuyền 02/10/2026): bấm Xong / Hoàn tất phiếu thì khách
  // sang nhóm "Đã xong" ở cột trái nhưng khung phải VẪN là khách ấy — tải nhầm
  // tệp thì sửa ngay, khỏi đi tìm lại. Trước đây khách tự chọn (chưa bấm vào
  // dòng) không được ghim, nên Xong xong khung nhảy sang người chờ kế tiếp.
  // Sang người mới = bấm dòng ở cột trái hoặc nút "Khách kế tiếp".
  if (chon && chon.id !== chonId) setChonId(chon.id);
  // Khách kế tiếp = cùng thứ tự với khách mặc định: đang làm dở trước, rồi đang chờ.
  const keTiep =
    chon?.trang_thai === "done"
      ? (ds.find((d) => d.trang_thai === "serving") ??
        ds.find((d) => d.trang_thai === "waiting" || d.trang_thai === "called") ??
        null)
      : null;

  return (
    <div className="grid gap-4">
      <ThongBaoHoanTac thongBao={thongBao} onDong={dongThongBao} onHoanTacXong={napLai} />
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h1 className="text-title font-semibold text-ink">{phong?.ten ?? "Đang tải…"}</h1>
        {hang && taiPhong && dem ? (
          // Cùng ba số với ô phòng ở /phong (máy chủ đếm theo khách).
          <p className="text-body tabular-nums text-ink-muted">
            {dem.sap_den ?? 0} sắp đến · {dem.dang_cho} đang chờ · {dem.dang_lam} đang làm ·{" "}
            {ds.filter((d) => d.trang_thai === "done").length} đã xong
          </p>
        ) : hang ? (
          <p className="text-body text-ink-muted">
            {ds.filter((d) => d.trang_thai === "waiting" || d.trang_thai === "called").length}{" "}
            đang chờ · {ds.filter((d) => d.trang_thai === "serving").length} đang làm ·{" "}
            {ds.filter((d) => d.trang_thai === "done").length} đã xong
          </p>
        ) : null}
        {loi ? (
          <p role="alert" className="text-body text-danger">
            {loi}
          </p>
        ) : null}
      </header>

      <ThanhNgay
        motNgay
        nhan="Xem hàng chờ theo ngày"
        khoang={{ tu: ngay, den: ngay }}
        homNay={homNay}
        soNgaySau={0}
        dangTai={hang === null}
        onChon={(k) => {
          const moi = k?.den ?? homNay;
          if (moi === ngay) return;
          setHang(null);
          setChonId(null);
          chonNgay(moi);
        }}
      />
      {!laHomNay ? (
        <p className="rounded-control border border-warning bg-warning-bg px-3 py-2 text-body text-warning">
          Đang xem ngày {ngayNgan(ngay)} — xem và sửa được như hôm nay. Bấm
          Bắt đầu / Xong thì ghi giờ thật lúc bấm.
        </p>
      ) : null}

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(240px,0.6fr)_minmax(0,1.8fr)]">
        <aside aria-label="Hàng chờ phòng" className="space-y-3">
          {phong && taiPhong ? (
            <SapDenPhong
              roomId={phong.id}
              ds={sapDen}
              bacSi={bacSiPhong}
              onDaNhan={napLai}
              onBao={setThongBao}
            />
          ) : phong ? (
            <ChuaXepPhong roomId={phong.id} ds={chuaXep} onDaNhan={napLai} />
          ) : null}
          {lanToi ? (
            <ChipLoc
              nhan="Lọc khách theo làn"
              chon={cheDoLan}
              onChon={(m) => {
                setCheDoLan(m);
                setChonId(null);
              }}
              muc={[
                {
                  ma: "lan",
                  nhan: `Khách của làn tôi · ${lanToi.nhan ?? "làn của tôi"}`,
                  title: "Khách quầy chọn bác sĩ làn của bạn + khách chưa chọn bác sĩ",
                },
                { ma: "ca_phong", nhan: `Cả phòng (${ca.length})` },
              ]}
            />
          ) : null}
          {hang === null ? (
            <p className="text-body text-ink-muted">Đang tải hàng chờ…</p>
          ) : (
            <HangChoCot
              dong={ds}
              chon={chon?.id ?? null}
              onChon={(id) => {
                setChonId(id);
                // Màn hẹp: khung khách nằm DƯỚI danh sách — tự cuộn tới (smoke
                // 18/09, 375).
                if (window.innerWidth < 1024) {
                  requestAnimationFrame(() =>
                    document
                      .getElementById("khung-khach-trong-phong")
                      ?.scrollIntoView({ block: "start" }),
                  );
                }
              }}
              trong="Chưa có khách nào được chỉ định vào phòng này."
            />
          )}
        </aside>
        {chon ? (
          <KhachTrongPhong
            key={chon.id}
            dong={chon}
            nhaTaiPhong={taiPhong && laHomNay && phong ? phong.id : null}
            onDaBam={napLai}
            onBao={setThongBao}
            keTiep={keTiep ? { ten: keTiep.ten, onChon: () => setChonId(keTiep.id) } : null}
          />
        ) : (
          <section className="grid min-h-72 place-items-center rounded-card bg-surface p-8 text-center text-body text-ink-muted shadow-card">
            Chọn một khách trong hàng chờ.
          </section>
        )}
      </div>
    </div>
  );
}

function KhachTrongPhong({
  dong,
  nhaTaiPhong,
  onDaBam,
  onBao,
  keTiep,
}: {
  dong: DongHangCho;
  /** Dây Nhận tại phòng bật: mã phòng để nút Nhả gửi lệnh (null = không có nút). */
  nhaTaiPhong?: string | null;
  onDaBam: () => void;
  /** Báo thông báo kèm Hoàn tác sau thao tác (đặt ở cấp màn). */
  onBao?: (tb: ThongBao) => void;
  /** Khách đang chờ kế tiếp — chỉ có khi khách này đã xong. */
  keTiep?: { ten: string; onChon: () => void } | null;
}) {
  const loai = loaiCua(dong.node_code);
  const [th, setTh] = useState<ThucHien | null>(null);
  const [moLyDo, setMoLyDo] = useState<"khong-lam" | "gian-doan" | null>(null);
  const [lyDo, setLyDo] = useState("");
  const [ghiChu, setGhiChu] = useState("");
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);
  const [xemLuot, setXemLuot] = useState(false);
  const [lanDoc, setLanDoc] = useState(0);
  const [moPhieuPhu, setMoPhieuPhu] = useState(false);
  /** Tên các bên của mẫu đang mở (mẫu hai bên) — null = một ô tải. */
  const [cacBen, setCacBen] = useState<string[] | null>(null);
  const [ghiChuXong, setGhiChuXong] = useState("");
  /** LÀM KHÔNG THEO THỨ TỰ (V4, 30/09/2026): khách đang làm ở phòng khác →
   *  máy chủ trả tên phòng (`chi_tiet` của 409 PATIENT_BUSY) và có cho chuyển
   *  không; màn chỉ hỏi lại tại chỗ, không tự suy luật. */
  const [hoiChuyen, setHoiChuyen] = useState<string | null>(null);
  const [hoiHuy, setHoiHuy] = useState(false);

  // Trạng thái thực hiện đọc riêng, không lấy từ hàng chờ: hàng chờ không mang
  // hai số revision, mà thiếu chúng thì mọi lệnh đều phải đoán.
  useEffect(() => {
    let huy = false;
    void docBang<ThucHien>("thuc-hien", { chi_dinh: dong.ref_id }).then((kq) => {
      if (huy) return;
      if (kq.ok) setTh(kq.data);
      else setLoi(kq.loi);
    });
    return () => {
      huy = true;
    };
  }, [dong.ref_id, lanDoc]);

  const docLai = () => setLanDoc((n) => n + 1);

  /** Một lệnh thực hiện. Xong thì đọc lại trạng thái VÀ nạp lại hàng chờ. */
  const lenh = async (thaoTac: string, duLieu: Record<string, unknown>) => {
    setDangGui(true);
    setLoi(null);
    setBao(null);
    const kq = await guiThaoTac(thaoTac, dong.ref_id, duLieu);
    setDangGui(false);
    if (!kq.ok) {
      const ct = kq.chiTiet;
      if (ct?.ma === "PATIENT_BUSY" && ct.chuyen_duoc === true) {
        setHoiChuyen(typeof ct.phong === "string" ? ct.phong : "khác");
        return;
      }
      setHoiChuyen(null);
      setLoi(kq.loi);
      return;
    }
    setHoiChuyen(null);
    setHoiHuy(false);
    setMoLyDo(null);
    setLyDo("");
    setGhiChu("");
    // Máy chủ trả trạng thái mới — vừa "xong" thì mời hoàn tác vài giây.
    if (kq.data.execution_status === "COMPLETED") {
      onBao?.({
        cau: `Đã xong ${dong.viec ?? "dịch vụ"} — ${dong.ten}`,
        goi: lenhHoanTac("hoan-tac-xong-v1", dong.ref_id),
      });
    }
    docLai();
    onDaBam();
  };

  const nha = async (roomId: string) => {
    setDangGui(true);
    setLoi(null);
    const kq = await guiThaoTac("nha-khoi-phong", dong.visit_id, { room_id: roomId });
    setDangGui(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    onBao?.({
      cau: `Đã nhả ${dong.ten} — khách về Sắp đến`,
      goi: lenhHoanTac("hoan-tac-nha", dong.visit_id, { room_id: roomId }),
    });
    onDaBam();
  };

  const batDau = (giaiPhong: boolean) => {
    if (!th) return;
    void lenh("bat-dau-v1", {
      expected_execution_revision: th.execution_revision,
      expected_routing_revision: th.routing_revision,
      ...(giaiPhong ? { giai_phong: true } : {}),
    });
  };

  const trangThai = th?.execution_status ?? null;
  const dangLam = trangThai === "IN_PROGRESS" && th?.lan_dang_chay != null;
  const daDung = trangThai === "INTERRUPTED" && th?.lan_da_dung != null;
  const daXong = trangThai === "COMPLETED" || trangThai === "NOT_PERFORMED";
  // NULL = chưa có lần làm nào (chỉ định tạo từ phiếu khám không ghi sẵn
  // PENDING) — máy chủ coi như PENDING (`coalesce(execution_status, 'PENDING')`).
  // Bấm thật 23/09 khuya: so đúng chữ "PENDING" làm mất nút Bắt đầu.
  const chuaLam =
    th != null && (trangThai === "PENDING" || trangThai === null);
  // PHIẾU LÀ ĐƯỜNG CHÍNH khi dịch vụ có mẫu (đã gắn, hoặc gợi ý của phiếu v5) —
  // [Hoàn tất] trong phiếu đóng luôn dịch vụ. Không có mẫu (tháo vòng, đặt
  // vòng…) hoặc phòng LẤY MẪU gửi đối tác: [Xong] là đường chính, phiếu chỉ mở
  // khi cần. Bấm thật 23/09 khuya: từ khi luôn có 18 mẫu dự phòng, nút [Xong]
  // (trước chỉ hiện khi danh sách mẫu rỗng) biến mất — phòng thủ thuật / lấy
  // mẫu không kết thúc được nếu không điền một phiếu.
  const coPhieuChinh =
    th != null &&
    loai !== "LAY_MAU" &&
    (th.mau_goi_y != null || (th.phieu?.length ?? 0) > 0);

  return (
    <section
      id="khung-khach-trong-phong"
      aria-label={`Khách ${dong.ten}`}
      className="min-w-0 space-y-4 rounded-card bg-surface p-4 shadow-card"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        {/* ĐẦU DỊCH VỤ (27/09/2026 — bản mẫu `manPhong`): tên dịch vụ, rồi
            "mã phòng khám · giá · thời gian đã làm / đã chờ"; dòng dưới là
            khách. Mã + giá do máy chủ trả trong `thuc-hien`. */}
        <div className="min-w-0">
          <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">
            Số {dong.so_thu_tu}
          </p>
          <h2 className="text-title font-semibold text-ink">
            {dong.viec ?? th?.service_name ?? "—"}
          </h2>
          <p className="text-meta tabular-nums text-ink-muted">
            {[
              th?.ma_kiotviet ?? null,
              th ? tienVn(th.gia) : null,
              daXong
                ? `Xong lúc ${gioVn(dong.xong_luc)}`
                : dangLam
                  ? `Lần làm #${th?.lan_dang_chay?.attempt_no} · bắt đầu ${gioVn(
                      th?.lan_dang_chay?.started_at ?? null,
                    )} · đã làm ${soPhutTu(th?.lan_dang_chay?.started_at ?? null)}`
                  : daDung
                    ? `Lần làm #${th?.lan_da_dung?.attempt_no} đã dừng${
                        th?.lan_da_dung?.interruption_reason_code
                          ? ` — ${nhanLyDo(th.lan_da_dung.interruption_reason_code)}`
                          : ""
                      }`
                    : dong.trang_thai === "blocked"
                      ? dong.dang_o_phong
                        ? `${cauDangOPhong(dong.dang_o_phong)} — chưa làm bước này được.`
                        : "Khách đang ở một bước khác — chưa làm bước này được."
                      : `Vào hàng ${gioVn(dong.vao_hang_luc)} · chờ ${soPhutTu(dong.vao_hang_luc)}`,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <p className="mt-1 text-body text-ink">
            <b className="text-emph font-semibold">{dong.ten}</b>
            <span className="text-ink-muted">
              {" "}
              · {dong.ma_bn}
              {dong.bac_si ? ` · BS chỉ định: ${dong.bac_si}` : ""}
            </span>
          </p>
          {/* Nhận chéo: phòng khác đã nhận khách khi lần làm ở đây còn mở —
              phòng này tự bấm Xong / Gián đoạn (hệ thống không đoán thay). */}
          {dong.da_sang_phong ? (
            <Chip tone="danger" className="mt-1">
              Khách đã sang {dong.da_sang_phong.phong ?? "phòng khác"} lúc {gioVn(dong.da_sang_phong.luc)}
            </Chip>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* IN PHIẾU LUÔN Ở ĐÂY (Tuyền 02/10/2026): mọi trạng thái, mọi loại
              phòng — kể cả đã xong rồi quay lại, lấy mẫu, dịch vụ không phiếu.
              Trang in tự lo: phiếu nháp ghi BẢN NHÁP, chỉ có ảnh vẫn in ảnh. */}
          <NutInPhieu href={`/print/ket-qua/${dong.ref_id}`} size="lg" />
          {chuaLam && th ? (
            <Button
              size="lg"
              variant="primary"
              disabled={dangGui}
              onClick={() => batDau(false)}
            >
              {dangGui ? "Đang ghi…" : "Bắt đầu"}
            </Button>
          ) : null}
          {daDung && th?.lan_da_dung ? (
            <Button
              size="lg"
              variant="primary"
              disabled={dangGui}
              onClick={() =>
                void lenh("lam-lai-v1", {
                  interrupted_attempt_id: th.lan_da_dung!.id,
                  expected_execution_revision: th.execution_revision,
                })
              }
            >
              {dangGui ? "Đang ghi…" : "Làm lại"}
            </Button>
          ) : null}
          {/* NHẢ (07/10/2026, mục 7b): khách đang chờ ở phòng này về "Sắp đến"
              của mọi phòng — hoàn tác được vài giây sau. */}
          {nhaTaiPhong && chuaLam && ["waiting", "called", "blocked"].includes(dong.trang_thai) ? (
            <Button size="sm" variant="ghost" disabled={dangGui} onClick={() => void nha(nhaTaiPhong)}>
              Nhả khách
            </Button>
          ) : null}
          {/* HUỶ BẮT ĐẦU NHẦM (V4, 30/09/2026): ngay cạnh chỗ vừa bấm Bắt đầu,
              chỉ khi máy chủ nói được (đang làm, chưa điền phiếu). */}
          {dangLam && th?.huy_bat_dau_duoc && !hoiHuy ? (
            <Button size="sm" variant="ghost" onClick={() => setHoiHuy(true)}>
              Huỷ bắt đầu nhầm
            </Button>
          ) : null}
        </div>
      </header>

      {hoiHuy && dangLam && th?.lan_dang_chay ? (
        <XacNhanTaiCho
          cau="Huỷ lần bắt đầu này? Khách về lại hàng chờ của phòng."
          nhanDongY="Huỷ bắt đầu"
          dangGui={dangGui}
          onDongY={() =>
            void lenh("huy-bat-dau-v1", {
              attempt_id: th.lan_dang_chay!.id,
              expected_execution_revision: th.execution_revision,
            })
          }
          onThoi={() => setHoiHuy(false)}
        />
      ) : null}

      {hoiChuyen && chuaLam ? (
        <XacNhanTaiCho
          cau={`Khách đang ở phòng ${hoiChuyen} — chuyển sang đây?`}
          nhanDongY="Chuyển sang đây"
          dangGui={dangGui}
          onDongY={() => batDau(true)}
          onThoi={() => setHoiChuyen(null)}
        />
      ) : null}

      {loi ? (
        <p
          role="alert"
          className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-body text-danger"
        >
          {loi}
        </p>
      ) : null}
      {bao ? (
        <p className="rounded-control border border-warning bg-warning-bg px-3 py-2 text-body text-warning">
          {bao}
        </p>
      ) : null}

      {/* Lịch sử các lần làm: máy hỏng lúc 10:05 rồi làm lại 10:18 là chuyện
          phải đọc được, không phải chuyện bị ghi đè. */}
      {th && th.cac_lan.length > 1 ? (
        <ol className="space-y-1 rounded-control bg-surface-muted px-3 py-2 text-meta text-ink-soft">
          {th.cac_lan.map((l) => (
            <li key={l.id}>
              Lần #{l.attempt_no} · {gioVn(l.started_at)}
              {l.status === "COMPLETED"
                ? ` → xong ${gioVn(l.completed_at)}`
                : l.status === "INTERRUPTED"
                  ? ` → dừng ${gioVn(l.interrupted_at)}${
                      l.interruption_reason_code
                        ? ` (${nhanLyDo(l.interruption_reason_code)})`
                        : ""
                    }`
                  : " → đang làm"}
              {l.bat_dau_boi ? ` · ${l.bat_dau_boi}` : ""}
            </li>
          ))}
        </ol>
      ) : null}

      {/* ĐÃ XONG: xem lại đúng cái đã ghi (batch pilot 18/09). */}
      {daXong ? (
        <div className="rounded-control bg-surface-muted px-3 py-2 text-body">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-ink">
              {trangThai === "NOT_PERFORMED" ? "Không làm được" : "Đã làm"}
              {dong.nguoi_lam ? ` · ${dong.nguoi_lam}` : ""} · {gioVn(dong.xong_luc)}
            </p>
            {/* HOÀN TÁC "Xong" (01/10/2026): về lại đang làm, kết quả giữ nguyên. */}
            {trangThai === "COMPLETED" ? (
              <NutHoanTac
                goi={lenhHoanTac("hoan-tac-xong-v1", dong.ref_id)}
                onXong={() => {
                  docLai();
                  onDaBam();
                }}
                tieuDe="Hoàn tác “Xong” của dịch vụ này?"
                moTa="Đưa dịch vụ về lại đang làm — kết quả đã gõ giữ nguyên"
              />
            ) : null}
          </div>
          {/* Dịch vụ đã đóng mà phiếu kết quả mới là nháp (máy chủ quyết —
              27/09 đợt 3): bản in lúc này vẫn ghi BẢN NHÁP. */}
          {th?.phieu_chua_hoan_tat ? (
            <Chip tone="warning" className="mt-1">
              Phiếu kết quả chưa Hoàn tất
            </Chip>
          ) : null}
          {dong.ly_do_khong_lam ? (
            <p className="text-meta text-warning">
              Lý do: {nhanLyDo(dong.ly_do_khong_lam)}
            </p>
          ) : null}
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <Button size="sm" variant="ghost" className="-ml-3" onClick={() => setXemLuot(true)}>
              Xem lại cả lượt
            </Button>
            {keTiep ? (
              <Button size="sm" variant="secondary" onClick={keTiep.onChon}>
                Sang khách kế tiếp: {keTiep.ten} →
              </Button>
            ) : null}
          </div>
          {xemLuot ? (
            <XemLuot visitId={dong.visit_id} onDong={() => setXemLuot(false)} />
          ) : null}
        </div>
      ) : null}

      {/* PHÒNG LẤY MẪU (29/09/2026): ô tệp LUÔN có — lịch sử các lần tải (tên,
          giờ, ai tải) và tải thêm bất kỳ lúc nào, kể cả ngày cũ. */}
      {loai === "LAY_MAU" ? (
        <KhungTep
          clinicPatientId={dong.clinic_patient_id}
          serviceOrderId={dong.ref_id}
          tieuDe="Tệp kết quả · phiếu gửi kèm"
        />
      ) : null}

      {/* Ô TỆP: có ngay từ lúc khách đang làm, để gửi ảnh/video ngay khi chụp. */}
      {(dangLam || daXong) && loai !== "LAY_MAU" ? (
        cacBen ? (
          // Mẫu HAI BÊN (26/09/2026): mỗi bên một ô tải — tệp gắn `ben`.
          <div className="grid gap-3 md:grid-cols-2">
            {cacBen.map((ten, so) => (
              <KhungTep
                key={so}
                clinicPatientId={dong.clinic_patient_id}
                serviceOrderId={dong.ref_id}
                ben={{ so, ten }}
              />
            ))}
          </div>
        ) : (
          <KhungTep
            clinicPatientId={dong.clinic_patient_id}
            serviceOrderId={dong.ref_id}
            tieuDe={loai === "SIEU_AM" ? "Ảnh & video siêu âm" : "Ảnh · video · phiếu"}
          />
        )
      ) : null}

      {/* Phiếu kết quả: mở được ngay khi đang làm, và vẫn xem/điền được sau khi
          dịch vụ đã đóng — kết quả về muộn là chuyện thường. */}
      {th && (dangLam || daXong) && !coPhieuChinh && loai !== "LAY_MAU" ? (
        <Button size="sm" variant="ghost" onClick={() => setMoPhieuPhu((v) => !v)}>
          {moPhieuPhu ? "Đóng phiếu kết quả" : "Điền phiếu kết quả (nếu cần)"}
        </Button>
      ) : null}
      {th && (dangLam || daXong) && (coPhieuChinh || moPhieuPhu) ? (
        <PhieuKetQua
          serviceOrderId={dong.ref_id}
          mau={th.mau_ket_qua}
          mauMacDinh={th.phieu?.[0]?.form_id?.replace(/^KQ_/, "") ?? th.mau_goi_y ?? null}
          onCacBen={setCacBen}
          onHoanTat={({ daDongDichVu, viSao, laLanSua, conTrong }) => {
            // Đợt 3: dịch vụ đóng xong thì dòng này rời hàng chờ và phiếu đóng
            // lại — nhắc "còn trống" phải đi theo câu báo, không mất cùng phiếu.
            const nhacTrong = conTrong.length
              ? ` Còn ${conTrong.length} mục trống: ${conTrong.join(", ")} (chỉ nhắc).`
              : "";
            setBao(
              (laLanSua
                ? "Đã ghi bản sửa của kết quả."
                : daDongDichVu
                  ? "Đã hoàn tất phiếu, đóng dịch vụ và báo có kết quả."
                  : `Đã hoàn tất phiếu. Dịch vụ CHƯA đóng: ${viSao ?? "không rõ lý do"}.`) + nhacTrong,
            );
            docLai();
            onDaBam();
          }}
        />
      ) : null}

      {/* HÀNG PHỤ: ba ngoại lệ. Không nút chính nào ở đây — nút chính là
          [Bắt đầu] trên đầu và [Hoàn tất] trong phiếu. */}
      {th && (chuaLam || dangLam) ? (
        <div className="space-y-3 border-t border-line pt-3">
          {dangLam && th.lan_dang_chay && !coPhieuChinh ? (
            // Dịch vụ không có phiếu kết quả (lấy mẫu gửi đi, thủ thuật không
            // mẫu): nút này gọi thẳng lệnh đóng dịch vụ. Vẫn đúng một nút kết thúc.
            // GHI CHÚ (Tuyền 24/09/2026: "không để chỉ cho ấn đã lấy mẫu là xong,
            // phải có ghi chú lại chứ") — lưu vào chính lần làm.
            <div className="space-y-2">
              <label className="block">
                <span className="text-meta font-semibold text-ink">
                  Ghi chú {loai === "LAY_MAU" ? "lấy mẫu" : "khi làm"} (tuỳ chọn)
                </span>
                <textarea
                  value={ghiChuXong}
                  onChange={(e) => setGhiChuXong(e.target.value)}
                  rows={2}
                  maxLength={2000}
                  placeholder={
                    loai === "LAY_MAU"
                      ? "VD: lấy 2 ống, khách khó lấy ven, mẫu gửi đối tác lúc 10h…"
                      : "Ghi lại điều cần lưu ý…"
                  }
                  className="mt-1 w-full rounded-control border border-line bg-surface px-3 py-2 text-body text-ink"
                />
              </label>
              <Button
                size="lg"
                variant="primary"
                disabled={dangGui}
                onClick={() =>
                  void lenh("xong-v1", {
                    attempt_id: th.lan_dang_chay!.id,
                    expected_execution_revision: th.execution_revision,
                    ghi_chu: ghiChuXong.trim() || undefined,
                  })
                }
              >
                {dangGui ? "Đang ghi…" : NUT_XONG[loai]}
              </Button>
            </div>
          ) : null}

          {/* "Phải dừng giữa chừng? / Không làm được?" — OFF (Tuyền 24/09/2026:
              "bỏ mấy cái thừa này đi"). Giữ code, bật lại bằng cờ. */}
          {NUT_NGOAI_LE ? (
            <button
              type="button"
              onClick={() =>
                setMoLyDo((v) => (v ? null : dangLam ? "gian-doan" : "khong-lam"))
              }
              className="text-body text-ink-muted underline underline-offset-4 hover:text-ink"
            >
              {dangLam ? "Phải dừng giữa chừng?" : "Không làm được?"}
            </button>
          ) : null}

          {moLyDo ? (
            <div className="space-y-2 rounded-control border border-line bg-surface-muted p-3">
              <label className="block">
                <span className="text-meta font-semibold text-ink">
                  {moLyDo === "gian-doan"
                    ? "Vì sao phải dừng giữa chừng"
                    : "Vì sao không làm được"}
                </span>
                <select
                  value={lyDo}
                  onChange={(e) => setLyDo(e.target.value)}
                  className="mt-1 min-h-10 w-full max-w-md rounded-control border border-line bg-surface px-3 text-body text-ink"
                >
                  <option value="">— chọn lý do —</option>
                  {(moLyDo === "gian-doan"
                    ? th.ly_do_gian_doan
                    : th.ly_do_khong_lam
                  ).map((m) => (
                    <option key={m} value={m}>
                      {nhanLyDo(m)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-meta font-semibold text-ink">
                  Ghi chú (không bắt buộc)
                </span>
                <input
                  value={ghiChu}
                  onChange={(e) => setGhiChu(e.target.value)}
                  className="mt-1 min-h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink"
                />
              </label>
              <p className="text-label text-ink-muted">
                Ghi xong KHÔNG tự hoàn tiền, không tự mở lần làm mới, không tự
                đổi phòng — mỗi việc ấy là một quyết định riêng.
              </p>
              <Button
                size="md"
                variant="danger"
                disabled={dangGui || !lyDo}
                onClick={() =>
                  void lenh(
                    moLyDo === "gian-doan" ? "gian-doan-v1" : "khong-lam-v1",
                    moLyDo === "gian-doan"
                      ? {
                          attempt_id: th.lan_dang_chay?.id,
                          expected_execution_revision: th.execution_revision,
                          ly_do: lyDo,
                          ghi_chu: ghiChu || null,
                        }
                      : {
                          expected_execution_revision: th.execution_revision,
                          ly_do: lyDo,
                          ghi_chu: ghiChu || null,
                        },
                  )
                }
              >
                {moLyDo === "gian-doan" ? "Ghi dừng giữa chừng" : "Ghi không làm được"}
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

/** Mã lý do → câu người đọc được. Mã lạ hiện nguyên mã, không giấu đi. */
function nhanLyDo(ma: string): string {
  return LY_DO_TIENG_VIET[ma] ?? ma;
}
