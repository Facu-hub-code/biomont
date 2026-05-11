import { LoginForm } from "./login-form";

export default async function LoginPage({
  searchParams,
}: {
  searchParams?: Promise<{ error?: string }>;
}) {
  const params = (await searchParams) ?? {};
  const error = params.error;

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <LoginForm error={error} />
    </main>
  );
}
