// Gửi một FormData có kèm TIẾN ĐỘ — chạy ở trình duyệt.
//
// `fetch` không báo được đã gửi bao nhiêu byte. Không giới hạn dung lượng
// (Tuyền chốt 16/09/2026) nghĩa là một video vài GB có thể mất nhiều phút: không
// có con số chạy thì người dùng tưởng treo, bấm lại, và tải hai lần.

export interface KetQuaGui {
  ok: boolean;
  status: number;
  data: unknown;
}

/** `onTienDo(phan_tram)`; 100 = đã gửi hết, máy chủ đang cất vào kho. */
export function guiTepCoTienDo(
  url: string,
  fd: FormData,
  onTienDo: (phanTram: number) => void,
): Promise<KetQuaGui> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && e.total > 0) {
        onTienDo(Math.min(100, Math.floor((e.loaded / e.total) * 100)));
      }
    };
    xhr.onload = () => {
      let data: unknown = null;
      try {
        data = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        data = null;
      }
      resolve({ ok: xhr.status >= 200 && xhr.status < 300, status: xhr.status, data });
    };
    xhr.onerror = () => reject(new Error("mat-ket-noi"));
    xhr.onabort = () => reject(new Error("huy"));
    xhr.send(fd);
  });
}

export function doCoTep(byte: number): string {
  if (byte < 1024 * 1024) return `${Math.max(1, Math.round(byte / 1024))} KB`;
  if (byte < 1024 * 1024 * 1024) return `${(byte / 1024 / 1024).toFixed(1)} MB`;
  return `${(byte / 1024 / 1024 / 1024).toFixed(2)} GB`;
}
