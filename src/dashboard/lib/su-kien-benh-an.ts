// "Bệnh án vừa lưu" — tín hiệu trong cùng một trang (smoke 18/09, UI-01).
//
// Phiếu chuyên khoa và bệnh án TỰ LƯU ở component khác với khung Ký; khung Ký
// cần biết để đọc lại "còn thiếu gì" ngay, thay vì đứng yên tới lúc tải lại
// trang. Chỉ là cái chuông báo — trạng thái thật vẫn đọc từ máy chủ.

const TEN = "clinicai:benh-an-da-luu";

export function baoBenhAnDaLuu(visitId: string): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(TEN, { detail: { visitId } }));
}

export function ngheBenhAnDaLuu(visitId: string, khiLuu: () => void): () => void {
  const nghe = (e: Event) => {
    if ((e as CustomEvent<{ visitId: string }>).detail?.visitId === visitId) khiLuu();
  };
  window.addEventListener(TEN, nghe);
  return () => window.removeEventListener(TEN, nghe);
}
