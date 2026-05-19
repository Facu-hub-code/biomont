export type LinkedProduct = {
  product_id: string;
  name: string;
  brand?: string;
  is_primary: boolean;
};

export function DocumentProductsPanel({ linked }: { linked: LinkedProduct[] }) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">
        Productos vinculados al documento. El primario define documents.product_id y los chunks al
        ingestar; el agente usa todos los vínculos para retrieval.
      </p>

      {linked.length > 0 ? (
        <ul className="flex flex-wrap gap-2 text-sm">
          {linked.map((p) => (
            <li
              key={p.product_id}
              className="badge-neutral rounded-lg border border-slate-200 px-2.5 py-1"
            >
              {p.name}
              {p.is_primary ? (
                <span className="ml-1 text-xs font-medium text-biomont-primary">(primario)</span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-500">Sin productos vinculados.</p>
      )}
    </div>
  );
}
