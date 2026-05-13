"use client";

import { useCallback, useEffect, useMemo, useState, useTransition } from "react";

import {
  type ConversationSummary,
  fetchConversationMessages,
  fetchConversationsList,
  fetchRtcsList,
  postPlaygroundMessage,
  type ChatMessage,
  type RtcRow,
} from "./actions";

const POLL_MS = 5000;
const PREVIEW_LEN = 72;

function truncate(s: string, n: number): string {
  const t = s.trim();
  if (t.length <= n) return t;
  return `${t.slice(0, n)}…`;
}

function pickLatestConversationForRtc(
  list: ConversationSummary[],
  rtcUserId: string,
): ConversationSummary | null {
  const rows = list.filter((c) => c.rtc_user_id === rtcUserId);
  if (!rows.length) return null;
  return rows.reduce((a, b) =>
    new Date(a.last_message_at) >= new Date(b.last_message_at) ? a : b,
  );
}

type Props = {
  canPlayground: boolean;
};

export default function ConversationsClient({ canPlayground }: Props) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const [modalOpen, setModalOpen] = useState(false);
  const [modalStep, setModalStep] = useState<"pick" | "chat">("pick");
  const [rtcs, setRtcs] = useState<RtcRow[]>([]);
  const [playRtcId, setPlayRtcId] = useState<string | null>(null);
  const [playMessages, setPlayMessages] = useState<ChatMessage[]>([]);
  const [playInput, setPlayInput] = useState("");
  const [playBusy, setPlayBusy] = useState(false);
  const [playError, setPlayError] = useState<string | null>(null);

  const refreshConversations = useCallback(() => {
    startTransition(async () => {
      try {
        setLoadError(null);
        const list = await fetchConversationsList();
        setConversations(list);
      } catch (e) {
        setLoadError(e instanceof Error ? e.message : "Error al cargar conversaciones");
      }
    });
  }, []);

  const refreshMessages = useCallback((conversationId: string) => {
    startTransition(async () => {
      try {
        setLoadError(null);
        const msgs = await fetchConversationMessages(conversationId);
        setMessages(msgs);
      } catch (e) {
        setLoadError(e instanceof Error ? e.message : "Error al cargar mensajes");
      }
    });
  }, []);

  useEffect(() => {
    refreshConversations();
    const id = window.setInterval(refreshConversations, POLL_MS);
    return () => window.clearInterval(id);
  }, [refreshConversations]);

  useEffect(() => {
    if (!selectedId) {
      setMessages([]);
      return;
    }
    refreshMessages(selectedId);
    const id = window.setInterval(() => refreshMessages(selectedId), POLL_MS);
    return () => window.clearInterval(id);
  }, [selectedId, refreshMessages]);

  const selected = useMemo(
    () => conversations.find((c) => c.id === selectedId) ?? null,
    [conversations, selectedId],
  );

  async function openModal() {
    setPlayError(null);
    setModalStep("pick");
    setPlayRtcId(null);
    setPlayMessages([]);
    setPlayInput("");
    setModalOpen(true);
    try {
      const list = await fetchRtcsList();
      setRtcs(list.filter((r) => r.enabled));
    } catch (e) {
      setPlayError(e instanceof Error ? e.message : "No se pudieron cargar RTCs");
    }
  }

  async function confirmRtcAndLoadChat(rtcId: string) {
    setPlayRtcId(rtcId);
    setModalStep("chat");
    setPlayError(null);
    try {
      const list = await fetchConversationsList();
      const conv = pickLatestConversationForRtc(list, rtcId);
      if (conv) {
        setPlayMessages(await fetchConversationMessages(conv.id));
      } else {
        setPlayMessages([]);
      }
    } catch (e) {
      setPlayError(e instanceof Error ? e.message : "Error al abrir el chat");
    }
  }

  const refreshPlayMessages = useCallback(async () => {
    if (!playRtcId) return;
    try {
      const list = await fetchConversationsList();
      const conv = pickLatestConversationForRtc(list, playRtcId);
      if (conv) {
        setPlayMessages(await fetchConversationMessages(conv.id));
      }
    } catch {
      /* polling best-effort */
    }
  }, [playRtcId]);

  useEffect(() => {
    if (!modalOpen || modalStep !== "chat" || !playRtcId) return;
    const id = window.setInterval(() => {
      void refreshPlayMessages();
    }, POLL_MS);
    return () => window.clearInterval(id);
  }, [modalOpen, modalStep, playRtcId, refreshPlayMessages]);

  async function onSendPlayground() {
    const text = playInput.trim();
    if (!playRtcId || !text || playBusy) return;
    setPlayBusy(true);
    setPlayError(null);
    try {
      await postPlaygroundMessage(playRtcId, text);
      setPlayInput("");
      await refreshPlayMessages();
      refreshConversations();
      if (selected?.rtc_user_id === playRtcId && selectedId) {
        refreshMessages(selectedId);
      }
    } catch (e) {
      setPlayError(e instanceof Error ? e.message : "Fallo al enviar");
    } finally {
      setPlayBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">Conversaciones</h2>
          <p className="text-sm text-slate-500">
            Vista espejo de hilos del agente (solo lectura). Actualiza cada {POLL_MS / 1000}s.
          </p>
        </div>
        {canPlayground ? (
          <button type="button" className="btn-primary" onClick={() => void openModal()}>
            Probar agente
          </button>
        ) : null}
      </header>

      {loadError ? (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {loadError}
        </p>
      ) : null}

      <div className="flex min-h-[480px] overflow-hidden rounded-lg border border-slate-200 bg-[#e5ddd5] shadow-sm">
        <aside className="flex w-full max-w-sm flex-col border-r border-slate-200 bg-white">
          <div className="border-b border-slate-200 bg-[#075e54] px-4 py-3 text-sm font-semibold text-white">
            Chats
          </div>
          <div className="flex-1 overflow-y-auto">
            {pending && conversations.length === 0 ? (
              <p className="p-4 text-sm text-slate-500">Cargando…</p>
            ) : null}
            {!pending && conversations.length === 0 ? (
              <p className="p-4 text-sm text-slate-500">Sin conversaciones aún.</p>
            ) : null}
            {conversations.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => setSelectedId(c.id)}
                className={`flex w-full flex-col items-start gap-0.5 border-b border-slate-100 px-4 py-3 text-left text-sm transition hover:bg-slate-50 ${
                  selectedId === c.id ? "bg-slate-100" : "bg-white"
                }`}
              >
                <span className="font-medium text-slate-900">{c.rtc_name}</span>
                <span className="font-mono text-xs text-slate-500">{c.phone_e164}</span>
                <span className="line-clamp-2 text-xs text-slate-600">
                  {c.last_preview ? truncate(c.last_preview, PREVIEW_LEN) : "—"}
                </span>
                <span className="text-[10px] text-slate-400">
                  {new Date(c.last_message_at).toLocaleString()}
                </span>
              </button>
            ))}
          </div>
        </aside>

        <section className="flex flex-1 flex-col bg-[#e5ddd5]">
          <div className="border-b border-slate-200/80 bg-[#075e54] px-4 py-3 text-sm text-white">
            {selected ? (
              <>
                <div className="font-semibold">{selected.rtc_name}</div>
                <div className="font-mono text-xs opacity-90">{selected.phone_e164}</div>
              </>
            ) : (
              <span className="opacity-90">Selecciona una conversacion</span>
            )}
          </div>

          <div className="flex flex-1 flex-col gap-2 overflow-y-auto px-4 py-4">
            {!selectedId ? (
              <p className="m-auto text-center text-sm text-slate-600">
                Elige un chat en la lista para ver los mensajes.
              </p>
            ) : (
              messages.map((m) => {
                const mine = m.role === "user";
                return (
                  <div
                    key={m.id}
                    className={`max-w-[85%] rounded-lg px-3 py-2 text-sm shadow-sm ${
                      mine
                        ? "ml-auto bg-[#dcf8c6] text-slate-900"
                        : "mr-auto bg-white text-slate-900"
                    }`}
                  >
                    <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-slate-500">
                      {m.role === "assistant" ? "Agente" : m.role === "user" ? "Usuario" : m.role}
                    </div>
                    <div className="whitespace-pre-wrap">{m.content}</div>
                    <div className="mt-1 text-[10px] text-slate-400">
                      {new Date(m.created_at).toLocaleString()}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div className="border-t border-slate-200/80 bg-slate-200/60 px-4 py-3 text-center text-xs text-slate-500">
            Solo lectura: no se envian mensajes desde esta pantalla.
          </div>
        </section>
      </div>

      {modalOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="playground-title"
        >
          <div className="relative w-full max-w-lg rounded-[1.75rem] border-[10px] border-slate-800 bg-slate-900 p-3 shadow-2xl">
            <div className="overflow-hidden rounded-2xl bg-white">
              <div className="flex items-center justify-between border-b border-slate-200 bg-slate-100 px-4 py-2">
                <h3 id="playground-title" className="text-sm font-semibold text-slate-800">
                  Probar agente
                </h3>
                <button
                  type="button"
                  className="rounded px-2 py-1 text-xs text-slate-600 hover:bg-slate-200"
                  onClick={() => setModalOpen(false)}
                >
                  Cerrar
                </button>
              </div>
              <p className="border-b border-slate-100 bg-amber-50 px-4 py-2 text-xs text-amber-900">
                Mensajes de prueba se guardan en el mismo hilo que WhatsApp para el RTC elegido (misma
                ventana de actividad). No se reenvia la respuesta al telefono del cliente.
              </p>

              {playError ? (
                <p className="border-b border-red-100 bg-red-50 px-4 py-2 text-xs text-red-800">
                  {playError}
                </p>
              ) : null}

              {modalStep === "pick" ? (
                <div className="max-h-80 overflow-y-auto p-4">
                  <p className="mb-2 text-sm text-slate-600">Elegí un RTC habilitado:</p>
                  <ul className="space-y-2">
                    {rtcs.map((r) => (
                      <li key={r.id}>
                        <button
                          type="button"
                          className="w-full rounded-lg border border-slate-200 px-3 py-2 text-left text-sm hover:border-biomont-primary hover:bg-slate-50"
                          onClick={() => void confirmRtcAndLoadChat(r.id)}
                        >
                          <span className="font-medium">{r.name}</span>
                          <span className="ml-2 font-mono text-xs text-slate-500">{r.phone_e164}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                  {rtcs.length === 0 ? (
                    <p className="text-sm text-slate-500">No hay RTCs habilitados.</p>
                  ) : null}
                </div>
              ) : (
                <div className="flex h-[420px] flex-col">
                  <div className="border-b border-slate-100 px-3 py-2 text-xs text-slate-500">
                    RTC:{" "}
                    <span className="font-mono">
                      {rtcs.find((r) => r.id === playRtcId)?.phone_e164 ?? playRtcId}
                    </span>
                    <button
                      type="button"
                      className="ml-3 text-biomont-primary underline"
                      onClick={() => {
                        setModalStep("pick");
                        setPlayRtcId(null);
                        setPlayMessages([]);
                      }}
                    >
                      Cambiar RTC
                    </button>
                  </div>
                  <div className="flex-1 space-y-2 overflow-y-auto bg-[#e5ddd5] p-3">
                    {playMessages.map((m) => {
                      const mine = m.role === "user";
                      return (
                        <div
                          key={m.id}
                          className={`max-w-[90%] rounded-lg px-3 py-2 text-sm shadow-sm ${
                            mine
                              ? "ml-auto bg-[#dcf8c6] text-slate-900"
                              : "mr-auto bg-white text-slate-900"
                          }`}
                        >
                          <div className="mb-0.5 text-[10px] font-semibold uppercase text-slate-500">
                            {m.role === "assistant" ? "Agente" : "Usuario"}
                          </div>
                          <div className="whitespace-pre-wrap">{m.content}</div>
                        </div>
                      );
                    })}
                  </div>
                  <div className="flex gap-2 border-t border-slate-200 bg-slate-50 p-3">
                    <input
                      className="form-input flex-1 text-sm"
                      placeholder="Escribi un mensaje de prueba…"
                      value={playInput}
                      onChange={(e) => setPlayInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          void onSendPlayground();
                        }
                      }}
                      disabled={playBusy}
                    />
                    <button
                      type="button"
                      className="btn-primary shrink-0 px-4 disabled:opacity-50"
                      disabled={playBusy || !playInput.trim()}
                      onClick={() => void onSendPlayground()}
                    >
                      {playBusy ? "…" : "Enviar"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
