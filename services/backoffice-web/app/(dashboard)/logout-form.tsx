"use client";

import { useFormStatus } from "react-dom";

import { logoutAction } from "./logout-action";

function LogoutSubmit() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      className="btn-secondary w-full text-sm disabled:cursor-wait"
      disabled={pending}
      aria-busy={pending}
    >
      {pending ? "Cerrando…" : "Cerrar sesion"}
    </button>
  );
}

export function LogoutForm() {
  return (
    <form action={logoutAction} className="mt-8">
      <LogoutSubmit />
    </form>
  );
}
