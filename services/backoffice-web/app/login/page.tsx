import { LoginForm } from "./login-form";

export default async function LoginPage({
  searchParams,
}: {
  searchParams?: Promise<{ error?: string }>;
}) {
  const params = (await searchParams) ?? {};
  const error = params.error;

  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-4 py-16">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_120%_80%_at_50%_-30%,rgba(20,184,166,0.18),transparent)]" />
      <div className="pointer-events-none absolute -left-24 top-1/4 h-72 w-72 rounded-full bg-teal-400/15 blur-[100px]" />
      <div className="pointer-events-none absolute -right-24 bottom-1/4 h-72 w-72 rounded-full bg-orange-400/12 blur-[100px]" />
      <LoginForm error={error} />
    </main>
  );
}
