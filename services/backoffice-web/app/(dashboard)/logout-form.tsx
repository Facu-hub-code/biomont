"use client";

import { useFormStatus } from "react-dom";

import { logoutAction } from "./logout-action";

function LogoutSubmit() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      className="btn-secondary w-full justify-center py-2 text-sm disabled:cursor-wait"
      disabled={pending}
      aria-busy={pending}
    >
      {pending ? "Cerrando…" : "Cerrar sesión"}
    </button>
  );
}

export function LogoutForm() {
  return (
    <form action={logoutAction}>
      <LogoutSubmit />
    </form>
  );
}
