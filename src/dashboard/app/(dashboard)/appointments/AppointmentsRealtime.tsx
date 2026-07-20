"use client";

// Thin realtime indicator + auto-refresh for /appointments.
// Lighter than TasksRealtime — instead of mirroring rows into client
// state (the list has joins to patient/staff/service_type that are
// painful to rebuild on the client), we subscribe to any change on
// ``appointment`` and call ``router.refresh()`` so the server component
// re-runs with fresh data and PostgREST handles the joins. A small live
// pill confirms the channel is active and counts events since mount.

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { getSupabaseBrowser } from "../../../lib/supabase-browser";

const REFRESH_DEBOUNCE_MS = 1500;

export default function AppointmentsRealtime() {
  const router = useRouter();
  const [eventCount, setEventCount] = useState(0);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const supabase = getSupabaseBrowser();
    const channel = supabase
      .channel("appointment-changes")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "appointment" },
        () => {
          setEventCount((c) => c + 1);
          // Debounce: many simultaneous INSERTs (e.g. bulk sync) only
          // trigger one server-side re-render, not one per event.
          if (refreshTimer.current) clearTimeout(refreshTimer.current);
          refreshTimer.current = setTimeout(() => {
            router.refresh();
          }, REFRESH_DEBOUNCE_MS);
        },
      )
      .subscribe();
    return () => {
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
      void supabase.removeChannel(channel);
    };
  }, [router]);

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="inline-flex h-1.5 w-1.5 animate-pulse rounded-full bg-green-500" />
      <span className="text-[#71717a]">
        Realtime
        {eventCount > 0 && (
          <span className="ml-2 rounded bg-green-100 px-1.5 py-0.5 font-medium text-green-800">
            +{eventCount} cập nhật
          </span>
        )}
      </span>
    </div>
  );
}
