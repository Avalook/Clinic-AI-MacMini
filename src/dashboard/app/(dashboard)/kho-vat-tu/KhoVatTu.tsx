"use client";

// Điều hướng gọn: tồn kho để thao tác, lịch sử để đối chiếu, danh mục để quản lý.

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import ONhap from "@/components/ui/ONhap";
import ThanhTab from "@/components/ui/ThanhTab";
import XuatBangTrongVung from "@/components/ui/XuatBangTrongVung";
import type { DongVatTu } from "../cashier/VatTuBangGia";
import { useNgheBang } from "../dung-nghe-bang";
import { docBaoCaoVatTu, khoangTuanHienTai, type GoiTieuHao } from "./bao-cao-vat-tu";
import BanChoKhachVatTu from "./BanChoKhachVatTu";
import ChoDuyetVatTu, { type GoiChoDuyet } from "./ChoDuyetVatTu";
import DanhMucVatTu from "./DanhMucVatTu";
import DanhSachPhieuVatTu, { type PhieuVatTu } from "./DanhSachPhieuVatTu";
import TieuHaoVatTu from "./TieuHaoVatTu";
import TonVatTu, { type DongTon, type NoiChua } from "./TonVatTu";

type Tab = "ton" | "ban" | "bao_cao" | "cho_duyet" | "danh_muc";

export default function KhoVatTu({
  ton,
  noiChua,
  vatTu,
  phieu,
  choDuyet,
  suaGiaDuoc,
  banCanXuLy,
}: {
  ton: DongTon[];
  noiChua: NoiChua[];
  vatTu: DongVatTu[];
  phieu: PhieuVatTu[];
  /** Yêu cầu nhập chờ duyệt; null = máy chủ không trả lời (tab tự báo). */
  choDuyet: GoiChoDuyet | null;
  /** Có quyền Bảng giá (`price.service.manage`) — chỉ để khoá ô sửa danh mục. */
  suaGiaDuoc: boolean;
  /** Số dòng bán chờ gán phòng / chờ người kho xử lý — chip trên tab. */
  banCanXuLy: number;
}) {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("ton");
  const [soCanXuLy, setSoCanXuLy] = useState(banCanXuLy);
  const [mucBaoCao, setMucBaoCao] = useState<"lich_su" | "tieu_hao">("lich_su");
  const [khoang, setKhoang] = useState(khoangTuanHienTai);
  const [baoCao, setBaoCao] = useState<GoiTieuHao | null>(null);
  const [loiBaoCao, setLoiBaoCao] = useState<string | null>(null);
  const [dangBaoCao, setDangBaoCao] = useState(true);
  const [chiDu, setChiDu] = useState(false);
  const [lanLamMoi, setLanLamMoi] = useState(0);
  const dangCho = choDuyet?.items.filter((y) => y.trang_thai === "CHO_DUYET").length ?? 0;

  useEffect(() => {
    const controller = new AbortController();
    void docBaoCaoVatTu(khoang.tu, khoang.den, controller.signal).then((ketQua) => {
      if (controller.signal.aborted) return;
      setDangBaoCao(false);
      if ("goi" in ketQua) {
        setBaoCao(ketQua.goi);
        setLoiBaoCao(null);
      } else {
        setLoiBaoCao(ketQua.loi);
      }
    });
    return () => controller.abort();
  }, [khoang.den, khoang.tu, lanLamMoi]);

  const taiLaiKho = useCallback(() => {
    setBaoCao(null);
    setLoiBaoCao(null);
    setDangBaoCao(true);
    setLanLamMoi((n) => n + 1);
    router.refresh();
  }, [router]);
  useNgheBang(["vat_tu_txn", "vat_tu_ban"], taiLaiKho);

  function doiTuNgay(tu: string) {
    setBaoCao(null);
    setLoiBaoCao(null);
    setDangBaoCao(true);
    setKhoang((hienTai) => ({
      tu,
      den: tu && hienTai.den && tu > hienTai.den ? tu : hienTai.den,
    }));
  }

  function doiDenNgay(den: string) {
    setBaoCao(null);
    setLoiBaoCao(null);
    setDangBaoCao(true);
    setKhoang((hienTai) => ({
      tu: den && hienTai.tu && den < hienTai.tu ? den : hienTai.tu,
      den,
    }));
  }

  return (
    <main className="page-in flex flex-col gap-4 p-4 lg:p-5">
      <ThanhTab
        nhan="Kho vật tư"
        chon={tab}
        onChon={setTab}
        muc={[
          { ma: "ton", nhan: "Tồn kho" },
          { ma: "ban", nhan: "Bán cho khách", dem: soCanXuLy > 0 ? soCanXuLy : undefined },
          { ma: "bao_cao", nhan: "Lịch sử & báo cáo" },
          { ma: "cho_duyet", nhan: "Chờ duyệt", dem: dangCho > 0 ? dangCho : undefined },
          { ma: "danh_muc", nhan: "Danh mục" },
        ]}
      />
      <XuatBangTrongVung tenTep={`kho-vat-tu-${tab}`}>
        {tab === "ton" ? (
          <TonVatTu
            ton={ton}
            noiChua={noiChua}
            vatTu={vatTu}
            baoCao={baoCao}
            tuNgay={khoang.tu}
            denNgay={khoang.den}
            dangBaoCao={dangBaoCao}
            loiBaoCao={loiBaoCao}
          />
        ) : tab === "ban" ? (
          <BanChoKhachVatTu noiChua={noiChua} vatTu={vatTu} lanLamMoi={lanLamMoi} onDem={setSoCanXuLy} />
        ) : tab === "bao_cao" ? (
          <section className="space-y-3">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <ThanhTab
                className="min-w-0 flex-1"
                nhan="Lịch sử và báo cáo kho vật tư"
                chon={mucBaoCao}
                onChon={setMucBaoCao}
                muc={[
                  { ma: "lich_su", nhan: "Lịch sử thao tác" },
                  { ma: "tieu_hao", nhan: "Mức dùng theo phòng" },
                ]}
              />
              {mucBaoCao === "tieu_hao" ? (
                <div aria-label="Khoảng ngày báo cáo mức dùng" className="grid w-full grid-cols-2 gap-2 sm:w-auto">
                  <label className="flex min-w-0 flex-col gap-1 text-meta text-ink-muted sm:min-w-40">
                    <span>Từ ngày</span>
                    <ONhap
                      type="date"
                      aria-label="Từ ngày"
                      value={khoang.tu}
                      onChange={(e) => doiTuNgay(e.target.value)}
                      className="w-full"
                    />
                  </label>
                  <label className="flex min-w-0 flex-col gap-1 text-meta text-ink-muted sm:min-w-40">
                    <span>Đến ngày</span>
                    <ONhap
                      type="date"
                      aria-label="Đến ngày"
                      value={khoang.den}
                      onChange={(e) => doiDenNgay(e.target.value)}
                      className="w-full"
                    />
                  </label>
                </div>
              ) : null}
            </div>
            {mucBaoCao === "lich_su" ? (
              <DanhSachPhieuVatTu ds={phieu} vatTu={vatTu} />
            ) : (
              <TieuHaoVatTu
                baoCao={baoCao}
                loi={loiBaoCao}
                dang={dangBaoCao}
                chiDu={chiDu}
                setChiDu={setChiDu}
              />
            )}
          </section>
        ) : tab === "cho_duyet" ? (
          <ChoDuyetVatTu goi={choDuyet} noiChua={noiChua} />
        ) : (
          <DanhMucVatTu ds={vatTu} suaDuoc={suaGiaDuoc} />
        )}
      </XuatBangTrongVung>
    </main>
  );
}
