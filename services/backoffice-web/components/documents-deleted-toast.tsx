"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { useToast } from "@/components/toast-provider";

/** Muestra toast tras borrar documento y limpia el query param de la URL. */
export function DocumentsDeletedToast() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { showToast } = useToast();

  useEffect(() => {
    if (searchParams.get("deleted") !== "1") return;
    showToast("success", "Documento eliminado.", "document-deleted");
    router.replace("/documents");
  }, [searchParams, router, showToast]);

  return null;
}
