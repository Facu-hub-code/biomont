export default function DashboardLoading() {
  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <div className="skeleton h-9 w-56 max-w-full" />
        <div className="skeleton h-4 w-96 max-w-full" />
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="card-static space-y-3 p-5">
            <div className="skeleton h-3 w-24" />
            <div className="skeleton h-10 w-20" />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {[1, 2].map((i) => (
          <div key={i} className="card-static space-y-4 p-6">
            <div className="skeleton h-4 w-40" />
            <div className="space-y-2">
              <div className="skeleton h-3 w-full" />
              <div className="skeleton h-3 w-full" />
              <div className="skeleton h-3 w-4/5" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
