"use client";

// Quét bằng camera điện thoại / máy tính bảng (G3b). Thư viện zxing chạy HOÀN
// TOÀN trong trình duyệt — ảnh không rời máy; chỉ chuỗi mã đọc được mới gửi đi
// tra. Cần HTTPS (staging / prod có); chỗ gọi đã ẩn nút khi trình duyệt không
// cho camera. Nạp thư viện lúc bấm, không nặng cho người chỉ dùng máy quét USB.
//
// Chọn @zxing/browser 0.1.5 + @zxing/library 0.21.3 (ghim đúng phiên bản, phát
// hành 08/2024): đọc được EAN / Code 128 / QR / DataMatrix (mã vuông GS1) bằng JS
// thuần, không WASM tải từ CDN — không phụ thuộc mạng ngoài lúc chạy.

import { useEffect, useRef, useState } from "react";

import Button from "@/components/ui/Button";

export default function CameraQuet({
  onMa,
  onDong,
}: {
  onMa: (ma: string) => void;
  onDong: () => void;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const [loi, setLoi] = useState<string | null>(null);

  useEffect(() => {
    let dung: (() => void) | null = null;
    let huy = false;
    (async () => {
      try {
        const [{ BrowserMultiFormatReader }, { BarcodeFormat, DecodeHintType }] = await Promise.all([
          import("@zxing/browser"),
          import("@zxing/library"),
        ]);
        const hints = new Map();
        hints.set(DecodeHintType.POSSIBLE_FORMATS, [
          BarcodeFormat.EAN_13,
          BarcodeFormat.EAN_8,
          BarcodeFormat.UPC_A,
          BarcodeFormat.CODE_128,
          BarcodeFormat.CODE_39,
          BarcodeFormat.DATA_MATRIX,
          BarcodeFormat.QR_CODE,
        ]);
        // Mã vuông (QR / DataMatrix) cần ảnh nét và nhiều điểm ảnh hơn mã vạch 1 chiều:
        // đọc kỹ (TRY_HARDER), camera SAU, độ phân giải cao, thử lại nhanh.
        hints.set(DecodeHintType.TRY_HARDER, true);
        const doc = new BrowserMultiFormatReader(hints, { delayBetweenScanAttempts: 60 });
        if (huy || !video.current) return;
        const dk = await doc.decodeFromConstraints(
          {
            video: {
              facingMode: { ideal: "environment" },
              width: { ideal: 1920 },
              height: { ideal: 1080 },
            },
          },
          video.current,
          (kq) => {
            if (kq) {
              dung?.();
              onMa(kq.getText());
            }
          },
        );
        dung = () => dk.stop();
        if (huy) dk.stop();
      } catch {
        setLoi("Không mở được camera — kiểm tra quyền camera của trình duyệt.");
      }
    })();
    return () => {
      huy = true;
      dung?.();
    };
    // onMa đổi mỗi lần vẽ lại của cha; camera chỉ khởi động một lần.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-2 rounded-control border border-line bg-surface-muted p-2">
      <video ref={video} className="max-h-64 w-full rounded-control bg-black" muted playsInline />
      {loi ? (
        <p role="alert" className="text-meta text-danger">
          {loi}
        </p>
      ) : (
        <p className="text-meta text-ink-muted">Đưa mã vạch / mã vuông trên hộp vào khung hình.</p>
      )}
      <Button type="button" size="sm" variant="ghost" onClick={onDong}>
        Đóng camera
      </Button>
    </div>
  );
}
