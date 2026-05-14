/** Estado devuelto por server actions usadas con `ActionFeedbackForm` (spec 005). */
export type ActionFeedbackState =
  | null
  | { ok: true; message?: string }
  | { ok: false; message: string };
