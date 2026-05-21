"use client";

import {
  Bot,
  ChevronRight,
  Inbox,
  Loader2,
  Phone,
  SendHorizontal,
  Sparkles,
  UserRound,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState, useTransition } from "react";

import { formatRelativeShort, initialsFromName } from "@/lib/format-time";

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

function ThreadBubble({ message }: { message: ChatMessage }) {
  const mine = message.role === "user";
  const stamp = new Date(message.created_at).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className={`flex w-full gap-2.5 ${mine ? "flex-row-reverse" : "flex-row"}`}>
      <div
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl shadow-sm ring-1 ring-black/[0.04] ${
          mine
            ? "bg-gradient-to-br from-teal-600 to-biomont-primary text-white"
            : "bg-white text-teal-700 ring-zinc-200/80"
        }`}
        aria-hidden
      >
        {mine ? (
          <UserRound className="h-4 w-4" strokeWidth={2.25} />
        ) : (
          <Bot className="h-4 w-4" strokeWidth={2.25} />
        )}
      </div>
      <div className={`flex max-w-[min(560px,82%)] flex-col gap-1 ${mine ? "items-end" : "items-start"}`}>
        <div className="flex items-center gap-2 px-0.5">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-zinc-400">
            {message.role === "assistant"
              ? "Agente"
              : message.role === "user"
                ? "Usuario"
                : message.role}
          </span>
          <span className="text-[11px] font-medium tabular-nums text-zinc-400">{stamp}</span>
        </div>
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-md transition-all duration-200 ${
            mine
              ? "rounded-br-md bg-gradient-to-br from-teal-600 to-biomont-primary text-white shadow-teal-900/18"
              : "rounded-bl-md border border-zinc-200/85 bg-white/95 text-zinc-800 shadow-zinc-900/[0.06] backdrop-blur-md"
          }`}
        >
          <div className="whitespace-pre-wrap">{message.content}</div>
        </div>
      </div>
    </div>
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
    <div className="space-y-8">
      <header className="flex flex-wrap items-start justify-between gap-6">
        <div className="page-header">
          <h2 className="page-title">Chats</h2>
          <p className="page-subtitle">
            Bandeja en tiempo casi real del agente (solo lectura). Se sincroniza cada{" "}
            {POLL_MS / 1000}s.
          </p>
        </div>
        {canPlayground ? (
          <button
            type="button"
            className="btn-primary gap-2 px-6 shadow-lift transition-transform duration-200 hover:-translate-y-0.5 active:translate-y-0"
            onClick={() => void openModal()}
          >
            <Sparkles className="h-4 w-4 shrink-0 opacity-95" aria-hidden />
            Probar agente
          </button>
        ) : null}
      </header>

      {loadError ? (
        <div
          role="alert"
          className="rounded-2xl border border-amber-200/90 bg-amber-50/95 px-5 py-4 text-sm font-medium text-amber-950 shadow-soft backdrop-blur-sm"
        >
          {loadError}
        </div>
      ) : null}

      <div className="flex min-h-[560px] flex-col overflow-hidden rounded-[28px] border border-zinc-200/70 bg-white/55 shadow-glow backdrop-blur-xl md:flex-row">
        {/* Inbox */}
        <aside className="flex w-full flex-col border-zinc-200/70 md:w-[340px] md:max-w-[40vw] md:border-r">
          <div className="flex items-center gap-3 border-b border-zinc-100/90 bg-white/65 px-5 py-4 backdrop-blur-md">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-zinc-800 to-zinc-950 text-white shadow-md">
              <Inbox className="h-[18px] w-[18px]" strokeWidth={2.25} aria-hidden />
            </div>
            <div>
              <p className="text-[13px] font-semibold text-zinc-900">Bandeja</p>
              <p className="text-[11px] font-medium text-zinc-500">
                {conversations.length} conversaciones
              </p>
            </div>
          </div>
          <div className="flex flex-1 flex-col overflow-y-auto bg-zinc-50/40">
            {pending && conversations.length === 0 ? (
              <div className="space-y-2 p-3">
                {[1, 2, 3, 4, 5, 6].map((i) => (
                  <div key={i} className="flex gap-3 rounded-2xl border border-transparent bg-white/40 p-3">
                    <div className="skeleton h-11 w-11 shrink-0 rounded-2xl" />
                    <div className="flex flex-1 flex-col gap-2 py-0.5">
                      <div className="skeleton h-3 w-3/5" />
                      <div className="skeleton h-3 w-full" />
                      <div className="skeleton h-3 w-2/5" />
                    </div>
                  </div>
                ))}
              </div>
            ) : null}
            {!pending && conversations.length === 0 ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-3 px-8 py-16 text-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-zinc-100 ring-8 ring-white/80">
                  <Inbox className="h-7 w-7 text-zinc-400" aria-hidden />
                </div>
                <p className="text-sm font-semibold text-zinc-700">Sin conversaciones aún</p>
                <p className="max-w-[240px] text-xs leading-relaxed text-zinc-500">
                  Cuando lleguen mensajes por WhatsApp o playground vas a verlos acá al instante.
                </p>
              </div>
            ) : null}
            {conversations.map((c) => {
              const active = selectedId === c.id;
              return (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => setSelectedId(c.id)}
                  className={`flex w-full gap-3 border-b border-zinc-100/80 px-4 py-3.5 text-left transition-all duration-200 hover:bg-white/85 ${
                    active ? "bg-white shadow-[inset_3px_0_0_0_#0f766e]" : "bg-transparent"
                  }`}
                >
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-zinc-100 to-zinc-200/90 text-[11px] font-bold uppercase tracking-wide text-zinc-700 ring-1 ring-white shadow-sm">
                    {initialsFromName(c.rtc_name)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <span className="truncate font-semibold text-zinc-900">{c.rtc_name}</span>
                      <span className="shrink-0 rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-semibold tabular-nums text-zinc-500">
                        {formatRelativeShort(c.last_message_at)}
                      </span>
                    </div>
                    <div className="mt-0.5 flex items-center gap-1 text-[11px] font-mono text-zinc-400">
                      <Phone className="h-3 w-3 shrink-0 opacity-70" aria-hidden />
                      <span className="truncate">{c.phone_e164}</span>
                    </div>
                    <p className="mt-1.5 line-clamp-2 text-[13px] leading-snug text-zinc-600">
                      {c.last_preview ? truncate(c.last_preview, PREVIEW_LEN) : "—"}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </aside>

        {/* Thread */}
        <section className="relative flex flex-1 flex-col chat-thread-bg">
          <div className="relative z-[1] flex items-start gap-4 border-b border-zinc-200/60 bg-white/75 px-6 py-4 backdrop-blur-lg">
            {selected ? (
              <>
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-600 to-biomont-primary text-sm font-bold text-white shadow-lg shadow-teal-900/15 ring-2 ring-white">
                  {initialsFromName(selected.rtc_name)}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-lg font-semibold tracking-tight text-zinc-900">
                    {selected.rtc_name}
                  </p>
                  <p className="mt-0.5 flex items-center gap-2 font-mono text-xs text-zinc-500">
                    <Phone className="h-3.5 w-3.5 shrink-0 text-teal-600/80" aria-hidden />
                    {selected.phone_e164}
                  </p>
                </div>
              </>
            ) : (
              <p className="text-sm font-medium text-zinc-500">
                Seleccioná una conversación para ver el hilo completo.
              </p>
            )}
          </div>

          <div className="relative z-[1] flex flex-1 flex-col gap-4 overflow-y-auto px-5 py-6 md:px-8">
            {!selectedId ? (
              <div className="m-auto flex max-w-sm flex-col items-center gap-4 px-6 py-12 text-center">
                <div className="rounded-full bg-white/90 p-5 shadow-soft ring-1 ring-zinc-200/80 backdrop-blur-md">
                  <Sparkles className="h-10 w-10 text-teal-600/90" aria-hidden />
                </div>
                <div>
                  <p className="text-base font-semibold text-zinc-800">Tu vista previa del agente</p>
                  <p className="mt-2 text-sm leading-relaxed text-zinc-500">
                    Elegí un chat a la izquierda para revisar preguntas, respuestas y cómo citó documentos.
                  </p>
                </div>
              </div>
            ) : (
              messages.map((m) => <ThreadBubble key={m.id} message={m} />)
            )}
          </div>

          <div className="relative z-[1] border-t border-zinc-200/70 bg-white/80 px-6 py-3 text-center text-[11px] font-medium uppercase tracking-wide text-zinc-400 backdrop-blur-md">
            Solo lectura · no se envían mensajes desde esta vista
          </div>
        </section>
      </div>

      {modalOpen ? (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-zinc-950/45 p-4 backdrop-blur-md transition-opacity duration-300"
          role="dialog"
          aria-modal="true"
          aria-labelledby="playground-title"
        >
          <div className="relative w-full max-w-xl animate-[fadeUp_0.35s_ease-out_forwards] opacity-0 shadow-[0_40px_120px_-40px_rgba(15,76,92,0.55)]">
            <div className="rounded-[28px] bg-gradient-to-br from-teal-500/25 via-white/40 to-transparent p-[1px] shadow-glow">
              <div className="overflow-hidden rounded-[27px] border border-white/60 bg-white/95 shadow-2xl backdrop-blur-2xl">
                <div className="flex items-center justify-between gap-4 border-b border-zinc-100/90 bg-gradient-to-r from-white via-teal-50/30 to-white px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-teal-600 to-biomont-primary text-white shadow-lg">
                      <Sparkles className="h-5 w-5" aria-hidden />
                    </div>
                    <div>
                      <h3 id="playground-title" className="text-base font-semibold tracking-tight text-zinc-900">
                        Playground del agente
                      </h3>
                      <p className="text-xs font-medium text-zinc-500">Entorno seguro para pruebas internas</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn-ghost rounded-xl p-2 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800"
                    aria-label="Cerrar"
                    onClick={() => setModalOpen(false)}
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>

                <div className="border-b border-amber-100/90 bg-gradient-to-r from-amber-50 to-orange-50/40 px-6 py-3">
                  <p className="text-xs leading-relaxed text-amber-950/90">
                    Los mensajes se guardan en el mismo hilo activo que WhatsApp para el RTC elegido. La respuesta{" "}
                    <strong>no</strong> se reenvía al teléfono del cliente.
                  </p>
                </div>

                {playError ? (
                  <div className="border-b border-red-100 bg-red-50/95 px-6 py-3 text-xs font-medium text-red-900">
                    {playError}
                  </div>
                ) : null}

                {modalStep === "pick" ? (
                  <div className="max-h-[min(420px,55vh)] overflow-y-auto p-6">
                    <p className="mb-4 text-sm font-medium text-zinc-700">Elegí un RTC habilitado</p>
                    <ul className="space-y-2">
                      {rtcs.map((r) => (
                        <li key={r.id}>
                          <button
                            type="button"
                            className="group flex w-full items-center gap-4 rounded-2xl border border-zinc-200/90 bg-white/90 px-4 py-3.5 text-left shadow-sm transition-all duration-200 hover:border-teal-300/70 hover:bg-teal-50/35 hover:shadow-md"
                            onClick={() => void confirmRtcAndLoadChat(r.id)}
                          >
                            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-zinc-100 text-[11px] font-bold text-zinc-600 ring-1 ring-white transition-colors group-hover:bg-teal-100 group-hover:text-teal-800">
                              {initialsFromName(r.name)}
                            </div>
                            <div className="min-w-0 flex-1">
                              <span className="block truncate font-semibold text-zinc-900">{r.name}</span>
                              <span className="mt-0.5 block truncate font-mono text-xs text-zinc-500">
                                {r.phone_e164}
                              </span>
                            </div>
                            <ChevronRight className="h-5 w-5 shrink-0 text-zinc-300 transition-transform group-hover:translate-x-0.5 group-hover:text-teal-600" />
                          </button>
                        </li>
                      ))}
                    </ul>
                    {rtcs.length === 0 ? (
                      <p className="rounded-2xl border border-dashed border-zinc-200 bg-zinc-50/80 px-4 py-8 text-center text-sm text-zinc-500">
                        No hay RTCs habilitados.
                      </p>
                    ) : null}
                  </div>
                ) : (
                  <div className="flex h-[min(480px,62vh)] flex-col">
                    <div className="flex flex-wrap items-center gap-3 border-b border-zinc-100/90 bg-white/70 px-5 py-3 text-xs backdrop-blur-sm">
                      <span className="font-semibold uppercase tracking-wide text-zinc-400">RTC activo</span>
                      <span className="rounded-full bg-zinc-100 px-3 py-1 font-mono text-[11px] font-medium text-zinc-700">
                        {rtcs.find((r) => r.id === playRtcId)?.phone_e164 ?? playRtcId}
                      </span>
                      <button
                        type="button"
                        className="ml-auto text-xs font-semibold text-teal-700 underline-offset-4 hover:underline"
                        onClick={() => {
                          setModalStep("pick");
                          setPlayRtcId(null);
                          setPlayMessages([]);
                        }}
                      >
                        Cambiar RTC
                      </button>
                    </div>
                    <div className="flex flex-1 flex-col gap-4 overflow-y-auto chat-thread-bg px-4 py-4 md:px-5">
                      {playMessages.length === 0 ? (
                        <div className="m-auto rounded-2xl border border-dashed border-zinc-200/90 bg-white/70 px-6 py-10 text-center shadow-inner backdrop-blur-sm">
                          <Bot className="mx-auto mb-3 h-10 w-10 text-teal-600/70" />
                          <p className="text-sm font-semibold text-zinc-700">Arrancá la conversación</p>
                          <p className="mt-2 text-xs leading-relaxed text-zinc-500">
                            Escribí abajo como si fueras el cliente por WhatsApp.
                          </p>
                        </div>
                      ) : (
                        playMessages.map((m) => (
                          <ThreadBubble key={m.id} message={m} />
                        ))
                      )}
                    </div>
                    <div className="flex gap-3 border-t border-zinc-100/90 bg-white/85 p-4 backdrop-blur-lg">
                      <input
                        className="form-input mt-0 flex-1 rounded-2xl border-zinc-200/90 bg-white py-3 text-sm shadow-inner"
                        placeholder="Mensaje de prueba…"
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
                        className="btn-primary shrink-0 rounded-2xl px-5 disabled:translate-y-0 disabled:opacity-50"
                        disabled={playBusy || !playInput.trim()}
                        onClick={() => void onSendPlayground()}
                      >
                        {playBusy ? (
                          <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
                        ) : (
                          <SendHorizontal className="h-5 w-5" aria-hidden />
                        )}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
