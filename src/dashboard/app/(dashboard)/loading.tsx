// Skeleton hiển thị NGAY khi điều hướng sang trang dashboard bất kỳ (Next
// stream skeleton trong lúc server component chạy) → cảm giác tức thì.

export default function Loading() {
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="space-y-2">
        <div className="skeleton h-6 w-48" />
        <div className="skeleton h-4 w-72" />
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="rounded-xl border border-[#e4e4e7] bg-white p-4"
          >
            <div className="skeleton mb-2 h-3 w-24" />
            <div className="skeleton h-7 w-16" />
          </div>
        ))}
      </div>

      {/* Rows */}
      <div className="space-y-2">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            className="flex items-center gap-3 rounded-xl border border-[#e4e4e7] bg-white p-3"
          >
            <div className="skeleton h-10 w-10 rounded-full" />
            <div className="flex-1 space-y-1.5">
              <div className="skeleton h-3.5 w-1/3" />
              <div className="skeleton h-3 w-1/2" />
            </div>
            <div className="skeleton h-8 w-20" />
          </div>
        ))}
      </div>
    </div>
  );
}
