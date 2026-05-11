-- =====================================================================
-- 003_conversations_tickets.sql
-- System prompt versionado + conversaciones / mensajes + tickets.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- System prompt versionado.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.system_prompts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    version integer NOT NULL,
    content text NOT NULL,
    is_active boolean NOT NULL DEFAULT false,
    created_by uuid REFERENCES public.bo_users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (version)
);

-- Solo una version puede estar activa simultaneamente.
CREATE UNIQUE INDEX IF NOT EXISTS uq_system_prompts_active
    ON public.system_prompts ((is_active))
    WHERE is_active = true;

-- ---------------------------------------------------------------------
-- Conversaciones y mensajes.
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'message_role') THEN
        CREATE TYPE public.message_role AS ENUM ('user', 'assistant', 'system');
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.conversations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rtc_user_id uuid NOT NULL REFERENCES public.rtc_users(id) ON DELETE CASCADE,
    started_at timestamptz NOT NULL DEFAULT now(),
    last_message_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conversations_rtc
    ON public.conversations (rtc_user_id, last_message_at DESC);

CREATE TABLE IF NOT EXISTS public.messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL REFERENCES public.conversations(id) ON DELETE CASCADE,
    role public.message_role NOT NULL,
    content text NOT NULL,
    model text,
    citations jsonb NOT NULL DEFAULT '[]'::jsonb,
    latency_ms integer,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON public.messages (conversation_id, created_at);

-- ---------------------------------------------------------------------
-- Decisiones del agente (trazabilidad del pipeline).
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'agent_decision_kind') THEN
        CREATE TYPE public.agent_decision_kind AS ENUM
            ('answered', 'low_confidence', 'no_match', 'blocked', 'error');
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.agent_decisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id uuid REFERENCES public.messages(id) ON DELETE CASCADE,
    decision public.agent_decision_kind NOT NULL,
    reasoning text,
    retrieved jsonb NOT NULL DEFAULT '[]'::jsonb,
    top_similarity numeric(6,4),
    system_prompt_version integer,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_decision
    ON public.agent_decisions (decision, created_at DESC);

-- ---------------------------------------------------------------------
-- Tickets generados por el agente o pedidos por el usuario.
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ticket_type') THEN
        CREATE TYPE public.ticket_type AS ENUM
            ('no_info', 'low_confidence', 'user_request');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ticket_status') THEN
        CREATE TYPE public.ticket_status AS ENUM
            ('open', 'in_progress', 'resolved', 'wont_fix');
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS public.tickets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid REFERENCES public.conversations(id) ON DELETE SET NULL,
    message_id uuid REFERENCES public.messages(id) ON DELETE SET NULL,
    type public.ticket_type NOT NULL,
    status public.ticket_status NOT NULL DEFAULT 'open',
    summary text NOT NULL,
    notes text,
    assigned_to uuid REFERENCES public.bo_users(id) ON DELETE SET NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tickets_status
    ON public.tickets (status, created_at DESC);

DROP TRIGGER IF EXISTS trg_tickets_updated_at ON public.tickets;
CREATE TRIGGER trg_tickets_updated_at
    BEFORE UPDATE ON public.tickets
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMIT;
