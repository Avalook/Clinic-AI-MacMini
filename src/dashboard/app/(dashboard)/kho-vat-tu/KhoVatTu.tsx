"use client";

// KHO VẬT TƯ — điều hướng theo việc nhân viên cần làm.

import { useState } from "react";

import ThanhTab from "@/components/ui/ThanhTab";
import type { DongVatTu } from "../cashier/VatTuBangGia";
import ChoDuyetVatTu, { type GoiChoDuyet } from "./ChoDuyetVatTu";
import DanhMucVatTu from "./DanhMucVatTu";
import DanhSachPhieuVatTu, { type PhieuVatTu } from "./DanhSachPhieuVatTu";
import LapPhieuVatTu from "./LapPhieuVatTu";
import TieuHaoVatTu from "./TieuHaoVatTu";
import TonVatTu, { type DongTon, type NoiChua } from "./TonVatTu";

type Tab = "ton" | "nhap" | "cap" | "kiem" | "bao_cao" | "quan_ly";
type LoaiPhieu = "NHAP" | "XUAT_PHONG" | "DIEU_CHINH";

const LOAI_THEO_TAB: Partial<Record<Tab, LoaiPhieu>> = {
  nhap: "NHAP",
  cap: "XUAT_PHONG",
  kiem: "DIEU_CHINH",
};

export default function KhoVatTu({
  ton,
  noiChua,
  vatTu,
  phieu,
  choDuyet,
  suaGiaDuoc,
}: {
  ton: DongTon[];
  noiChua: NoiChua[];
  vatTu: DongVatTu[];
  phieu: PhieuVatTu[];
  /** Yêu cầu nhập chờ duyệt; null = máy chủ không trả lời (tab tự báo). */
  choDuyet: GoiChoDuyet | null;
  /** Có quyền Bảng giá (`price.service.manage`) — chỉ để khoá ô sửa danh mục. */
  suaGiaDuoc: boolean;
}) {
  const [tab, setTab] = useState<Tab>("ton");
  const [mucBaoCao, setMucBaoCao] = useState<"lich_su" | "tieu_hao">("lich_su");
  const [mucQuanLy, setMucQuanLy] = useState<"cho_duyet" | "danh_muc">("cho_duyet");
  const canChuY = ton.filter((t) => t.canh_bao).length;
  const dangCho = choDuyet?.items.filter((y) => y.trang_thai === "CHO_DUYET").length ?? 0;
  const chon = vatTu.map((v) => ({ id: v.id, name: v.name }));
  const loaiPhieu = LOAI_THEO_TAB[tab];

  return (
    <main className="page-in flex flex-col gap-4 p-4 lg:p-5">
      <header>
        <h1 className="text-title font-semibold text-ink">Kho vật tư</h1>
        <p className="text-body text-ink-muted">
          Xem vật tư còn ở kho cơ sở hoặc từng phòng. Nhập hàng làm tăng tồn kho; cấp cho phòng chuyển số lượng từ kho sang phòng.
        </p>
      </header>
      <ThanhTab
        nhan="Kho vật tư"
        chon={tab}
        onChon={setTab}
        muc={[
          { ma: "ton", nhan: "Tồn kho", dem: canChuY > 0 ? canChuY : undefined },
          { ma: "nhap", nhan: "Nhập hàng" },
          { ma: "cap", nhan: "Cấp cho phòng" },
          { ma: "kiem", nhan: "Kiểm kê" },
          { ma: "bao_cao", nhan: "Lịch sử & báo cáo" },
          { ma: "quan_ly", nhan: "Quản lý", dem: dangCho > 0 ? dangCho : undefined },
        ]}
      />
      {tab === "ton" ? (
        <TonVatTu ton={ton} noiChua={noiChua} onLamNhanh={setTab} />
      ) : loaiPhieu ? (
        <section className="space-y-3">
          <div>
            <h2 className="text-title font-semibold text-ink">
              {tab === "nhap" ? "Ghi nhận hàng vừa nhận" : tab === "cap" ? "Ghi nhận vật tư giao cho phòng" : "Đếm và cập nhật tồn thực tế"}
            </h2>
            <p className="mt-1 text-body text-ink-muted">
              {tab === "nhap"
                ? "Chọn từng mặt hàng, nhập số lượng nhận và nơi cất. Nếu mặt hàng cần duyệt, hàng chỉ vào kho sau khi được duyệt."
                : tab === "cap"
                  ? "Ghi số lượng đã lấy khỏi kho cơ sở và phòng nhận. Nếu số trên hệ thống chưa kịp cập nhật, vẫn ghi nhận việc giao; tồn âm sẽ được nhắc để đối chiếu."
                  : "Đếm hàng đang có tại kho hoặc phòng. Lưu số đếm sẽ cập nhật tồn theo thực tế và ghi lại phần chênh lệch."}
            </p>
          </div>
          <LapPhieuVatTu
            noiChua={noiChua}
            vatTu={chon}
            ton={ton}
            xemChoDuyet={() => {
              setMucQuanLy("cho_duyet");
              setTab("quan_ly");
            }}
            loaiBanDau={loaiPhieu}
          />
        </section>
      ) : tab === "bao_cao" ? (
        <section className="space-y-3">
          <ThanhTab
            nhan="Lịch sử và báo cáo kho vật tư"
            chon={mucBaoCao}
            onChon={setMucBaoCao}
            muc={[
              { ma: "lich_su", nhan: "Lịch sử nhập, cấp, trả" },
              { ma: "tieu_hao", nhan: "Mức dùng theo phòng" },
            ]}
          />
          {mucBaoCao === "lich_su" ? (
            <section className="space-y-2">
              <p className="text-body text-ink-muted">
                Ai làm, lúc nào, mặt hàng nào và số lượng thay đổi. Ghi nhầm thì hoàn tác; lịch sử cũ vẫn được giữ.
              </p>
              <DanhSachPhieuVatTu ds={phieu} />
            </section>
          ) : (
            <section className="space-y-2">
              <p className="text-body text-ink-muted">
                Chọn tuần, tháng hoặc khoảng ngày để xem lượng từng phòng đã dùng. Muốn tính đúng cần có số đếm đầu và cuối kỳ.
              </p>
              <TieuHaoVatTu />
            </section>
          )}
        </section>
      ) : (
        <section className="space-y-3">
          <ThanhTab
            nhan="Quản lý kho vật tư"
            chon={mucQuanLy}
            onChon={setMucQuanLy}
            muc={[
              { ma: "cho_duyet", nhan: "Yêu cầu nhập cần duyệt", dem: dangCho > 0 ? dangCho : undefined },
              { ma: "danh_muc", nhan: "Mặt hàng & phân loại" },
            ]}
          />
          {mucQuanLy === "cho_duyet" ? (
            <section className="space-y-2">
              <p className="text-body text-ink-muted">
                Yêu cầu nhập chỉ cộng vào tồn sau khi người có quyền duyệt.
              </p>
              <ChoDuyetVatTu goi={choDuyet} noiChua={noiChua} />
            </section>
          ) : (
            <section className="space-y-2">
              <p className="text-body text-ink-muted">
                Quản lý danh mục, đơn vị, giá và vật tư được phép bán thêm. Mức cảnh báo chỉ nhắc, không tự tạo đơn nhập.
              </p>
              <DanhMucVatTu ds={vatTu} suaDuoc={suaGiaDuoc} />
            </section>
          )}
        </section>
      )}
    </main>
  );
}
