import { AgentConfigEditor, type AgentConfigVersion } from "@/app/(dashboard)/agent-config/agent-config-editor";
import { apiRequest } from "@/lib/api";
import { requireRole } from "@/lib/auth";

export default async function AgentConfigPage() {
  const user = await requireRole(["admin", "scientist", "viewer"]);
  const canMutate = user.role === "admin";

  let versions: AgentConfigVersion[] = [];
  let active: AgentConfigVersion | null = null;
  try {
    versions = await apiRequest<AgentConfigVersion[]>("/agent-config/versions");
    active = versions.find((v) => v.is_active) ?? null;
    if (!active) {
      try {
        active = await apiRequest<AgentConfigVersion>("/agent-config/active");
      } catch {
        active = null;
      }
    }
  } catch {
    versions = [];
    active = null;
  }

  return (
    <div className="space-y-10">
      <header className="page-header">
        <h2 className="page-title">Configuración del agente</h2>
        <p className="page-subtitle">
          top_k de retrieval, intenciones del clasificador y tipos de documento por intent.
          Los cambios aplican al servicio agent tras la ventana de caché (~60s).
        </p>
      </header>

      <AgentConfigEditor active={active} versions={versions} canMutate={canMutate} />
    </div>
  );
}
