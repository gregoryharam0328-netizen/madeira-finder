"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { apiFetch } from "@/lib/api";

type Me = { email: string; full_name: string | null; role: string };

type Props = {
  lastScanAt?: string | null;
  newToday: number;
  total: number;
};

function formatScanTime(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-IE", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function initials(fullName: string | null | undefined, email: string) {
  const n = (fullName || "").trim();
  if (n) {
    const parts = n.split(/\s+/).filter(Boolean);
    const letters =
      parts.length >= 2
        ? `${parts[0][0] ?? ""}${parts[parts.length - 1][0] ?? ""}`
        : (parts[0]?.slice(0, 2) ?? "");
    return letters.toUpperCase() || "?";
  }
  const local = email.split("@")[0] || email;
  return local.slice(0, 2).toUpperCase() || "?";
}

export default function DashboardHeaderControls({ lastScanAt, newToday, total }: Props) {
  const [user, setUser] = useState<Me | null>(null);
  const [notifyOpen, setNotifyOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const notifyRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const loadMe = useCallback(async () => {
    try {
      const u = await apiFetch("/auth/me");
      setUser(u as Me);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    void loadMe();
  }, [loadMe]);

  useEffect(() => {
    function closeOnOutside(e: MouseEvent) {
      const t = e.target as Node;
      if (notifyRef.current?.contains(t) || menuRef.current?.contains(t)) return;
      setNotifyOpen(false);
      setMenuOpen(false);
    }
    document.addEventListener("mousedown", closeOnOutside);
    return () => document.removeEventListener("mousedown", closeOnOutside);
  }, []);

  function logout() {
    localStorage.removeItem("token");
    window.location.href = "/";
  }

  const displayName = user?.full_name?.trim() || user?.email?.split("@")[0] || "Account";

  return (
    <div className="flex shrink-0 items-center gap-2 sm:gap-3">
      <div className="relative" ref={notifyRef}>
        <button
          type="button"
          onClick={() => {
            setMenuOpen(false);
            setNotifyOpen((v) => !v);
          }}
          className="relative rounded-full border border-brand-200 bg-white p-2 text-brand-700 shadow-sm transition hover:bg-brand-50 focus:outline-none focus:ring-2 focus:ring-ocean-600 focus:ring-offset-1"
          aria-expanded={notifyOpen}
          aria-haspopup="dialog"
          aria-label="Data and scan notifications"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
            />
          </svg>
          {newToday > 0 ? (
            <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-ocean-700 px-1 text-[10px] font-bold leading-none text-white">
              {newToday > 99 ? "99+" : newToday}
            </span>
          ) : null}
        </button>
        {notifyOpen ? (
          <div
            className="absolute right-0 z-50 mt-2 w-[min(100vw-2rem,18rem)] rounded-lg border border-brand-200 bg-white py-2 shadow-lg"
            role="dialog"
            aria-label="Notification details"
          >
            <p className="border-b border-brand-100 px-3 pb-2 text-[11px] font-semibold uppercase tracking-wide text-brand-500">
              Listing updates
            </p>
            <div className="space-y-3 px-3 py-3 text-sm text-brand-800">
              <div>
                <p className="text-xs font-medium text-brand-500">Last scan</p>
                <p className="mt-0.5 font-semibold text-brand-900">{formatScanTime(lastScanAt)}</p>
                <p className="mt-1 text-xs text-brand-600">Time of the latest successful ingestion run.</p>
              </div>
              <div>
                <p className="text-xs font-medium text-brand-500">New data</p>
                <p className="mt-0.5 text-brand-900">
                  <span className="font-semibold text-ocean-800">{newToday}</span>
                  <span className="text-brand-700"> new today</span>
                  {total > 0 ? (
                    <span className="text-brand-600">
                      {" "}
                      · {total} total in workspace
                    </span>
                  ) : null}
                </p>
              </div>
              <Link
                href="/dashboard"
                className="inline-flex text-sm font-semibold text-ocean-700 hover:underline"
                onClick={() => setNotifyOpen(false)}
              >
                View New today →
              </Link>
            </div>
          </div>
        ) : null}
      </div>

      <div className="relative" ref={menuRef}>
        <button
          type="button"
          onClick={() => {
            setNotifyOpen(false);
            setMenuOpen((v) => !v);
          }}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 border-ocean-600 bg-gradient-to-br from-ocean-50 to-white text-xs font-bold text-ocean-900 shadow-sm transition hover:from-ocean-100 focus:outline-none focus:ring-2 focus:ring-ocean-600 focus:ring-offset-1"
          aria-expanded={menuOpen}
          aria-haspopup="menu"
          aria-label="Account menu"
        >
          {user ? initials(user.full_name, user.email) : "?"}
        </button>
        {menuOpen ? (
          <div
            className="absolute right-0 z-50 mt-2 w-56 rounded-lg border border-brand-200 bg-white py-1 shadow-lg"
            role="menu"
            aria-label="Account"
          >
            <div className="border-b border-brand-100 px-3 py-2.5">
              <p className="text-sm font-semibold text-brand-900">{user ? displayName : "Account"}</p>
              {user?.email ? <p className="mt-0.5 truncate text-xs text-brand-600">{user.email}</p> : null}
              {!user ? <p className="mt-1 text-xs text-brand-500">Session unavailable — try refreshing or sign in again.</p> : null}
            </div>
            {user ? (
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  logout();
                }}
                className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm font-medium text-brand-800 transition hover:bg-brand-50"
              >
                <svg className="h-4 w-4 shrink-0 text-brand-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                Log out
              </button>
            ) : (
              <Link
                href="/"
                role="menuitem"
                className="block px-3 py-2.5 text-sm font-semibold text-ocean-700 hover:bg-brand-50"
                onClick={() => setMenuOpen(false)}
              >
                Sign in
              </Link>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
