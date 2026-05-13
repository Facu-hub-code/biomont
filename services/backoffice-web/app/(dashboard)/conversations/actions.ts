"use server";

import { apiRequest } from "@/lib/api";

export type ConversationSummary = {
  id: string;
  rtc_user_id: string;
  rtc_name: string;
  phone_e164: string;
  started_at: string;
  last_message_at: string;
  last_preview: string | null;
};

export type ChatMessage = {
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  created_at: string;
};

export type RtcRow = {
  id: string;
  phone_e164: string;
  name: string;
  enabled: boolean;
  country_isos: string[];
  created_at: string;
};

export async function fetchConversationsList(): Promise<ConversationSummary[]> {
  return apiRequest<ConversationSummary[]>("/conversations");
}

export async function fetchConversationMessages(conversationId: string): Promise<ChatMessage[]> {
  return apiRequest<ChatMessage[]>(`/conversations/${conversationId}/messages`);
}

export async function fetchRtcsList(): Promise<RtcRow[]> {
  return apiRequest<RtcRow[]>("/rtcs");
}

export type PlaygroundResult = {
  decision: string;
  reply_text: string;
  ticket_id: string | null;
};

export async function postPlaygroundMessage(
  rtcUserId: string,
  text: string,
): Promise<PlaygroundResult> {
  return apiRequest<PlaygroundResult>("/playground/messages", {
    method: "POST",
    json: { rtc_user_id: rtcUserId, text },
  });
}
