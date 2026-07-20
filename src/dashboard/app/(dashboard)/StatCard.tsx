// Stat card for dashboard summary rows. Presentational only.

export default function StatCard({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-[#e4e4e7] bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.08)]">
      <p className="text-[12px] text-[#888888]">{label}</p>
      <p className="mt-1 text-[28px] font-semibold leading-tight text-[#171717]">
        {value}
      </p>
    </div>
  );
}
