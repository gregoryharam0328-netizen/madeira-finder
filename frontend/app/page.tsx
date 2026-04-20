import LoginForm from "@/components/LoginForm";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-brand-50 px-4 py-12">
      <div className="w-full max-w-md">
        <LoginForm />
      </div>
      <p className="mt-8 max-w-sm text-center text-xs text-brand-500">
        Internal tool for Exploring Madeira — daily digest, filters, and listing actions.
      </p>
    </main>
  );
}
