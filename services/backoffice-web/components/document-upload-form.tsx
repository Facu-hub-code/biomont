"use client";

import { useRef, useState, type FormEvent } from "react";

import { ActionFeedbackForm } from "@/components/action-feedback-form";
import { ProductPicker, type CatalogProduct } from "@/components/product-picker";
import { SubmitButton } from "@/components/submit-button";

import { uploadDocumentAction } from "@/app/(dashboard)/documents/actions";

function titleFromFileName(fileName: string): string {
  const base = fileName.replace(/\.[^.]+$/, "").trim();
  return base.replace(/[_-]+/g, " ").trim() || fileName;
}

type Props = {
  products: CatalogProduct[];
};

export function DocumentUploadForm({ products }: Props) {
  const titleRef = useRef<HTMLInputElement>(null);
  const [productError, setProductError] = useState<string | null>(null);

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !titleRef.current) return;
    if (!titleRef.current.value.trim()) {
      titleRef.current.value = titleFromFileName(file.name);
    }
  }

  function validateProducts(form: HTMLFormElement): boolean {
    const checked = form.querySelectorAll<HTMLInputElement>('input[name="product_ids"]:checked');
    if (checked.length === 0) {
      setProductError("Seleccioná al menos un producto del catálogo.");
      return false;
    }
    setProductError(null);
    return true;
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    if (!validateProducts(event.currentTarget)) {
      event.preventDefault();
    }
  }

  return (
    <ActionFeedbackForm
      action={uploadDocumentAction}
      successMessage="Documento enviado para procesamiento."
      onSubmit={handleSubmit}
    >
      <div className="card grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="md:col-span-2">
          <label className="form-label" htmlFor="file">
            Archivo PDF
          </label>
          <input
            id="file"
            name="file"
            type="file"
            accept="application/pdf"
            required
            className="form-input file:mr-3 file:rounded-md file:border-0 file:bg-biomont-primary/10 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-biomont-primary"
            onChange={handleFileChange}
          />
        </div>
        <div>
          <label className="form-label" htmlFor="title">
            Titulo
          </label>
          <input
            id="title"
            name="title"
            ref={titleRef}
            required
            className="form-input"
            placeholder="Se completa con el nombre del archivo"
          />
        </div>
        <div className="md:col-span-2">
          <label className="form-label">Productos del catálogo</label>
          <ProductPicker
            products={products}
            hint="Obligatorio. El primero marcado en la lista será el producto primario al ingestar (podés elegir varios)."
          />
          {productError ? (
            <p className="mt-2 text-sm text-red-600" role="alert">
              {productError}
            </p>
          ) : null}
        </div>
        <div>
          <label className="form-label" htmlFor="country_iso">
            Pais (iso2, vacio = global)
          </label>
          <input
            id="country_iso"
            name="country_iso"
            maxLength={2}
            className="form-input uppercase"
          />
        </div>
        <div>
          <label className="form-label" htmlFor="language">
            Idioma
          </label>
          <input
            id="language"
            name="language"
            defaultValue="es"
            maxLength={2}
            className="form-input"
          />
        </div>
        <div>
          <label className="form-label" htmlFor="kind">
            Tipo
          </label>
          <select id="kind" name="kind" defaultValue="bitacora" className="form-input">
            <option value="ficha_tecnica">ficha_tecnica</option>
            <option value="bitacora">bitacora</option>
            <option value="balotario">balotario</option>
          </select>
        </div>
        <div className="md:col-span-2">
          <SubmitButton label="Procesar y validar" pendingLabel="Procesando…" />
        </div>
      </div>
    </ActionFeedbackForm>
  );
}
