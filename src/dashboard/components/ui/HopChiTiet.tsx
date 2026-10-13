"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";
import Button from "./Button";

/** Native dialog supplies focus containment and returns focus to its trigger. */
export default function HopChiTiet({ tieuDe, children, onDong }: {
  tieuDe: string; children: ReactNode; onDong: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const id = useId();
  useEffect(() => {
    const dialog = ref.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog?.showModal();
    return () => { dialog?.close(); document.body.style.overflow = previousOverflow; };
  }, []);
  return <dialog ref={ref} aria-labelledby={id} onCancel={onDong}
    className="m-auto max-h-dvh w-full max-w-5xl overflow-y-auto rounded-modal bg-surface p-4 text-body text-ink ring-1 ring-line backdrop:bg-ink/30 sm:max-h-[90vh]">
    <header className="mb-4 flex items-start justify-between gap-3">
      <h2 id={id} className="text-title font-semibold">{tieuDe}</h2>
      <Button type="button" onClick={onDong}>Đóng</Button>
    </header>
    {children}
  </dialog>;
}
