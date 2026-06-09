-- Prioridades Proteggo 3M / Proteggo M (spec 016).
-- Ejecutar tras migración 014 y con cuadro comparativo importado.
--
--   psql "$DATABASE_URL" -f scripts/seed_proteggo_comparison_columns.sql

BEGIN;

UPDATE public.commercial_comparison_columns AS c
SET display_tier = 1
FROM public.commercial_comparison_sets AS s
JOIN public.products AS p ON p.id = s.subject_product_id
WHERE c.set_id = s.id
  AND (
    lower(p.name) LIKE '%proteggo%'
    OR lower(p.name) LIKE '%protego%'
  )
  AND (
    c.column_key IN (
      'tiempo_de_efecto_meses',
      'tiempo_de_efecto',
      'indicaciones',
      'f_farmaceutica',
      'via_de_adm',
      'especies',
      'especies_de_destino'
    )
    OR lower(c.header_label) LIKE '%tiempo de efecto%'
    OR lower(c.header_label) LIKE '%forma farmac%'
    OR lower(c.header_label) LIKE '%via de adm%'
    OR lower(c.header_label) LIKE '%vía de adm%'
    OR lower(c.header_label) LIKE '%especies%'
    OR lower(c.header_label) LIKE '%indicaciones%'
  );

UPDATE public.commercial_comparison_columns AS c
SET display_tier = 3
FROM public.commercial_comparison_sets AS s
JOIN public.products AS p ON p.id = s.subject_product_id
WHERE c.set_id = s.id
  AND (
    lower(p.name) LIKE '%proteggo%'
    OR lower(p.name) LIKE '%protego%'
  )
  AND c.display_tier <> 1
  AND c.column_key IN (
    'formula',
    'dosis',
    'precauciones',
    'contraindicaciones',
    'reacciones_adversas',
    'laboratorio_fabricante',
    'pais',
    'producto'
  );

COMMIT;
