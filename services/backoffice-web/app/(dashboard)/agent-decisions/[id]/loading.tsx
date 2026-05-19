export default function AgentDecisionDetailLoading() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4">
      <div
        className="h-10 w-10 animate-spin rounded-full border-[3px] border-slate-200 border-t-biomont-primary"
        role="status"
        aria-label="Cargando decisión"
      />
      <p className="text-sm font-medium text-slate-600">Cargando decisión…</p>
    </div>
  );
}
