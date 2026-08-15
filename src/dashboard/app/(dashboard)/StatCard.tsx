// Stat card for dashboard summary rows. Presentational only.

export default function StatCard({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="rounded-card border border-line bg-surface p-5 shadow-card">
      <p className="text-meta text-ink-muted">{label}</p>
      <p className="mt-1 text-[28px] font-semibold leading-tight text-ink">
        {value}
      </p>
    </div>
  );
}
