"use client";

import { motion, useReducedMotion } from "framer-motion";
import { useState } from "react";

import { apiFetch } from "@/lib/api";
import { springSnappy } from "@/lib/motion";

const inputClass =
  "w-full rounded-md border border-brand-300 bg-white px-3 py-2.5 text-sm text-brand-900 shadow-sm outline-none transition placeholder:text-brand-400 focus:border-ocean-600 focus:ring-1 focus:ring-ocean-600";

export default function LoginForm() {
  const reduce = useReducedMotion();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("client@example.com");
  const [password, setPassword] = useState("password123");
  const [fullName, setFullName] = useState("Client User");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (mode === "register") {
        await apiFetch("/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, password, full_name: fullName }),
        });
      }
      const token = await apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      localStorage.setItem("token", token.access_token);
      window.location.href = "/dashboard";
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={springSnappy}
      className="flex w-full max-w-md overflow-hidden rounded-lg border border-brand-200 bg-white shadow-card"
    >
      <div className="hidden w-1.5 shrink-0 bg-ocean-700 sm:block" aria-hidden />
      <div className="flex-1 p-8">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-ocean-700">Exploring Madeira</p>
        <h1 className="mt-2 text-2xl font-semibold text-brand-900">Property Finder</h1>
        <p className="mt-2 text-sm text-brand-600">
          Sign in to the shared daily listing workspace — same view as the client brief.
        </p>

        <form onSubmit={onSubmit} className="mt-6 space-y-3">
          {mode === "register" && (
            <input
              className={inputClass}
              placeholder="Full name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
          )}
          <input
            className={inputClass}
            placeholder="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <input
            className={inputClass}
            placeholder="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && (
            <div className="rounded-md border border-danger-600/20 bg-danger-50 px-3 py-2 text-sm text-danger-700">
              {error}
            </div>
          )}
          <motion.button
            type="submit"
            disabled={loading}
            whileHover={reduce || loading ? undefined : { scale: 1.01 }}
            whileTap={reduce || loading ? undefined : { scale: 0.98 }}
            transition={springSnappy}
            className="w-full rounded-md bg-ocean-700 py-2.5 text-sm font-semibold text-white hover:bg-ocean-800 disabled:opacity-50"
          >
            {loading ? "Please wait…" : mode === "login" ? "Log in" : "Create account"}
          </motion.button>
        </form>

        <button
          type="button"
          className="mt-4 w-full text-center text-sm font-medium text-ocean-700 hover:underline"
          onClick={() => setMode(mode === "login" ? "register" : "login")}
        >
          {mode === "login" ? "Need an account?" : "Already have an account?"}
        </button>
      </div>
    </motion.div>
  );
}
