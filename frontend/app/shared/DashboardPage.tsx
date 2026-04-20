"use client";

import { AnimatePresence, LayoutGroup, motion, useReducedMotion } from "framer-motion";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

import DashboardHeaderControls from "@/components/DashboardHeaderControls";
import ListingCard from "@/components/ListingCard";
import Sidebar, { type SidebarNavCounts } from "@/components/Sidebar";
import StatCard from "@/components/StatCard";
import { apiFetch } from "@/lib/api";
import { springSnappy, staggerContainer, staggerItem } from "@/lib/motion";

type Filters = {
  area: string;
  property_type: string;
  bedrooms: string;
  sort: string;
};

/** Madeira municipalities for area filter (substring match on listing municipality / area / location). */
const AREA_OPTIONS: { value: string; label: string }[] = [
  { value: "all", label: "All areas" },
  { value: "Funchal", label: "Funchal" },
  { value: "Câmara de Lobos", label: "Câmara de Lobos" },
  { value: "Santa Cruz", label: "Santa Cruz" },
  { value: "Caniço", label: "Caniço" },
  { value: "Machico", label: "Machico" },
  { value: "Ponta do Sol", label: "Ponta do Sol" },
  { value: "Ribeira Brava", label: "Ribeira Brava" },
];

function formatScanTime(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-IE", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function buildListingsPath(endpoint: string, filters: Filters, workflowFromUrl: string | null) {
  if (
    endpoint === "/listings/saved" ||
    endpoint === "/listings/price-changes" ||
    endpoint === "/listings/not-interested"
  ) {
    return endpoint;
  }

  const p = new URLSearchParams();

  if (endpoint === "/listings") {
    if (workflowFromUrl && workflowFromUrl !== "all") {
      p.set("workflow_status", workflowFromUrl);
    }
  }

  if (endpoint === "/listings" || endpoint === "/listings/new") {
    if (filters.area && filters.area !== "all" && filters.area.trim()) p.set("area", filters.area.trim());
    if (filters.property_type && filters.property_type !== "all") p.set("property_type", filters.property_type);
    if (filters.bedrooms && filters.bedrooms !== "any") p.set("bedrooms", filters.bedrooms);
    if (filters.sort && filters.sort !== "newest") p.set("sort", filters.sort);
  }

  const qs = p.toString();
  return qs ? `${endpoint}?${qs}` : endpoint;
}

function DashboardPageInner({ endpoint, title }: { endpoint: string; title: string }) {
  const reduce = useReducedMotion();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [items, setItems] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [ingesting, setIngesting] = useState(false);
  const [removingMock, setRemovingMock] = useState(false);
  const [ingestHint, setIngestHint] = useState("");
  const [ingestionHints, setIngestionHints] = useState<{ notices: string[] } | null>(null);
  const [filters, setFilters] = useState<Filters>({
    area: "all",
    property_type: "all",
    bedrooms: "2",
    sort: "newest",
  });

  const workflowFromUrl =
    pathname === "/dashboard/all" ? (searchParams.get("workflow") || "").toLowerCase() || null : null;

  const listingsUrl = useMemo(
    () => buildListingsPath(endpoint, filters, workflowFromUrl),
    [endpoint, filters, workflowFromUrl],
  );

  const emptyHint = useMemo(() => {
    if (!summary) return null;
    if (summary.total === 0) {
      return (
        <>
          No listings yet. Set <span className="font-medium">APIFY_TOKEN</span> in the backend .env for Idealista (see
          .env.example), click <span className="font-medium">Fetch listings now</span>, wait for scrapers to finish, then{" "}
          <span className="font-medium">Refresh data</span>. HTML-only portals may still return rows without Apify.
        </>
      );
    }
    if (endpoint === "/listings/new") {
      return (
        <>
          Nothing new in today&apos;s window. Try{" "}
          <Link className="font-medium text-ocean-700 underline underline-offset-2" href="/dashboard/all">
            All Listings
          </Link>
          .
        </>
      );
    }
    if (endpoint === "/listings/price-changes") {
      return (
        <>
          No price changes yet. Try{" "}
          <Link className="font-medium text-ocean-700 underline underline-offset-2" href="/dashboard/all">
            All Listings
          </Link>
          .
        </>
      );
    }
    if (endpoint === "/listings/not-interested") {
      return (
        <>
          Nothing marked as not interested. Dismissed listings stay in the database and appear here — use{" "}
          <span className="font-medium">Not interested</span> on a card to move it out of{" "}
          <Link className="font-medium text-ocean-700 underline underline-offset-2" href="/dashboard/all">
            All listings
          </Link>
          .
        </>
      );
    }
    if (endpoint === "/listings/saved") {
      return (
        <>
          Nothing saved yet. Open{" "}
          <Link className="font-medium text-ocean-700 underline underline-offset-2" href="/dashboard/all">
            All Listings
          </Link>{" "}
          and favourite a card.
        </>
      );
    }
    return null;
  }, [endpoint, summary]);

  const loadDashboard = useCallback((options?: { showLoading?: boolean }) => {
    const showLoading = options?.showLoading ?? true;
    if (showLoading) setLoading(true);
    setError("");
    return Promise.all([apiFetch(listingsUrl), apiFetch("/dashboard/summary")])
      .then(([listings, dashboard]) => {
        setItems(Array.isArray(listings) ? listings : []);
        setSummary(dashboard);
      })
      .catch((err) => {
        setError(err?.message || "Failed to load dashboard");
      })
      .finally(() => {
        setLoading(false);
      });
  }, [listingsUrl]);

  useEffect(() => {
    let cancelled = false;
    void loadDashboard({ showLoading: true }).then(() => {
      if (cancelled) return;
    });
    return () => {
      cancelled = true;
    };
  }, [loadDashboard]);

  useEffect(() => {
    let cancelled = false;
    // Defer so listings + summary win the network first (faster first paint).
    const t = window.setTimeout(() => {
      apiFetch("/dashboard/ingestion-hints")
        .then((h) => {
          if (cancelled) return;
          setIngestionHints(h);
        })
        .catch(() => {
          if (cancelled) return;
          setIngestionHints(null);
        });
    }, 350);
    return () => {
      cancelled = true;
      window.clearTimeout(t);
    };
  }, []);

  async function runIngestionNow() {
    setIngesting(true);
    setError("");
    setIngestHint("");
    try {
      const res = await apiFetch("/dashboard/trigger-ingestion", { method: "POST", body: "{}" });
      const parts = [res?.message, ...((res?.notices as string[]) || [])].filter(Boolean) as string[];
      setIngestHint(parts.join("\n\n"));
      await loadDashboard();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not start ingestion");
    } finally {
      setIngesting(false);
    }
  }

  async function runRemoveMock() {
    setRemovingMock(true);
    setError("");
    setIngestHint("");
    try {
      const res = await apiFetch("/dashboard/remove-mock-listings", { method: "POST", body: "{}" });
      setIngestHint(res?.message || "Mock listings removed.");
      await loadDashboard();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not remove mock listings");
    } finally {
      setRemovingMock(false);
    }
  }

  const filterTabs = useMemo(() => {
    // Order aligned with ListingCard status dropdown; every workflow has a tab.
    const base = [
      { href: "/dashboard/all", label: "All", match: (p: string, w: string | null) => p === "/dashboard/all" && !w },
      { href: "/dashboard", label: "New today", match: (p: string) => p === "/dashboard" },
      {
        href: "/dashboard/all?workflow=new",
        label: "Unreviewed",
        match: (p: string, w: string | null) => p === "/dashboard/all" && w === "new",
      },
      {
        href: "/dashboard/all?workflow=seen",
        label: "Seen",
        match: (p: string, w: string | null) => p === "/dashboard/all" && w === "seen",
      },
      { href: "/dashboard/saved", label: "Favourites", match: (p: string) => p === "/dashboard/saved" },
      {
        href: "/dashboard/all?workflow=need_to_call",
        label: "Need to call",
        match: (p: string, w: string | null) => p === "/dashboard/all" && w === "need_to_call",
      },
      {
        href: "/dashboard/all?workflow=viewing_arranged",
        label: "Viewing arranged",
        match: (p: string, w: string | null) => p === "/dashboard/all" && w === "viewing_arranged",
      },
      {
        href: "/dashboard/all?workflow=offer_made",
        label: "Offer made",
        match: (p: string, w: string | null) => p === "/dashboard/all" && w === "offer_made",
      },
      {
        href: "/dashboard/all?workflow=not_available",
        label: "Gone",
        match: (p: string, w: string | null) => p === "/dashboard/all" && w === "not_available",
      },
      {
        href: "/dashboard/all?workflow=not_interested",
        label: "Not interested",
        match: (p: string, w: string | null) => p === "/dashboard/all" && w === "not_interested",
      },
    ];
    return base;
  }, []);

  const showFilterDropdowns = endpoint === "/listings" || endpoint === "/listings/new";
  const isNotInterestedView = endpoint === "/listings/not-interested";

  const sidebarCounts = useMemo((): SidebarNavCounts | null => {
    if (!summary) return null;
    return {
      new_today: Number(summary.new_today) || 0,
      total: Number(summary.total) || 0,
      saved: Number(summary.saved) || 0,
      price_changes: Number(summary.price_changes ?? 0) || 0,
      not_interested: Number(summary.not_interested ?? 0) || 0,
    };
  }, [summary]);

  return (
    <main className="min-h-screen bg-brand-50">
      <motion.header
        initial={reduce ? false : { opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={springSnappy}
        className="border-b border-brand-200 bg-white shadow-header"
      >
        <div className="flex w-full flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-2">
            <div className="relative h-8 w-8 shrink-0">
              <Image
                src="/exploring-madeira-logo.png"
                alt="Exploring Madeira logo"
                fill
                sizes="150px"
                className="object-contain"
                priority
              />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-semibold text-ocean-700">Madeira</p>
              <p className="text-sm font-semibold text-brand-900">Property discovery</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-3 sm:gap-4">
            <p className="hidden max-w-[14rem] text-right text-xs text-brand-500 md:block lg:max-w-none">
              Last scan:{" "}
              <span className="font-medium text-brand-700">{formatScanTime(summary?.last_scan_at)}</span>
            </p>
            <DashboardHeaderControls
              lastScanAt={summary?.last_scan_at}
              newToday={Number(summary?.new_today) || 0}
              total={Number(summary?.total) || 0}
            />
          </div>
        </div>
      </motion.header>

      <div className="grid w-full gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,17rem)_minmax(0,1fr)] lg:items-start lg:gap-8 lg:px-8">
        <Sidebar counts={sidebarCounts} />
        <section className="min-w-0 space-y-6">
          <motion.div
            initial={reduce ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={springSnappy}
            className="rounded-xl border border-amber-200/80 bg-amber-50/90 px-4 py-3 text-sm text-amber-950 shadow-sm"
          >
            <p className="font-semibold text-amber-950">Search brief</p>
            <p className="mt-1 text-amber-900/95">
              €260,000 – €340,000 · Madeira island only · Houses, villas and apartments only (NO land) · 2 bedrooms
              minimum · For sale only
            </p>
          </motion.div>

          <motion.div
            initial={reduce ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={springSnappy}
            className="rounded-lg border border-brand-200 bg-white p-6 shadow-card"
          >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-brand-500">Dashboard</p>
                <h1 className="mt-1 text-2xl font-semibold text-brand-900 lg:text-[1.65rem]">{title}</h1>
                <p className="mt-2 max-w-2xl text-sm text-brand-600">
                  {isNotInterestedView ? (
                    <>
                      Listings you marked <span className="font-medium text-brand-800">Not interested</span> stay in
                      the database. Change status on any card to return it to{" "}
                      <Link className="font-medium text-ocean-700 underline underline-offset-2" href="/dashboard/all">
                        All listings
                      </Link>
                      . Last scan{" "}
                      <span className="font-medium text-brand-800">{formatScanTime(summary?.last_scan_at)}</span>
                    </>
                  ) : (
                    <>
                      €260,000 – €340,000 · Houses and apartments · For sale · Last scan{" "}
                      <span className="font-medium text-brand-800">{formatScanTime(summary?.last_scan_at)}</span>
                    </>
                  )}
                </p>
              </div>
              <div className="flex shrink-0 flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center lg:flex-col lg:items-end">
                <motion.button
                  type="button"
                  disabled={ingesting}
                  whileHover={reduce || ingesting ? undefined : { scale: 1.02 }}
                  whileTap={reduce || ingesting ? undefined : { scale: 0.98 }}
                  transition={springSnappy}
                  onClick={() => runIngestionNow()}
                  className="rounded-md bg-ocean-700 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-ocean-800 disabled:opacity-50"
                >
                  {ingesting ? "Starting…" : "Fetch listings now"}
                </motion.button>
                {/* <motion.button
                  type="button"
                  disabled={removingMock}
                  whileHover={reduce || removingMock ? undefined : { scale: 1.02 }}
                  whileTap={reduce || removingMock ? undefined : { scale: 0.98 }}
                  transition={springSnappy}
                  onClick={() => runRemoveMock()}
                  className="rounded-md border border-brand-300 bg-white px-4 py-2 text-sm font-semibold text-brand-700 hover:bg-brand-50 disabled:opacity-50"
                >
                  {removingMock ? "Removing…" : "Remove mock / sample listings"}
                </motion.button> */}
                <motion.button
                  type="button"
                  disabled={loading}
                  whileHover={reduce || loading ? undefined : { scale: 1.02 }}
                  whileTap={reduce || loading ? undefined : { scale: 0.98 }}
                  transition={springSnappy}
                  onClick={() => {
                    setIngestHint("");
                    void loadDashboard();
                  }}
                  className="rounded-md border border-brand-300 bg-white px-4 py-2 text-sm font-semibold text-brand-800 hover:bg-brand-50 disabled:opacity-50"
                >
                  Refresh data
                </motion.button>
              </div>
            </div>
            {ingestionHints?.notices?.length ? (
              <p className="mt-3 whitespace-pre-line text-xs text-brand-600">
                {(ingestionHints.notices as string[]).join("\n\n")}
              </p>
            ) : null}
            {ingestHint ? (
              <motion.p
                initial={reduce ? false : { opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={springSnappy}
                className="mt-4 whitespace-pre-line rounded-md border border-ocean-600/30 bg-ocean-700/5 px-3 py-2 text-sm text-ocean-800"
              >
                {ingestHint}
              </motion.p>
            ) : null}
          </motion.div>

          {summary && (
            <motion.div
              variants={staggerContainer}
              initial="hidden"
              animate="show"
              className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"
            >
              {(
                [
                  ["Total", summary.total, "neutral"],
                  ["New today", summary.new_today, "emerald"],
                  ["Favourites", summary.saved, "amber"],
                  ["Need to call", summary.need_to_call ?? 0, "blue"],
                  ["Viewings", summary.viewing_arranged ?? 0, "violet"],
                ] as const
              ).map(([label, value, accent]) => (
                <motion.div key={label} variants={staggerItem} className="min-w-0">
                  <StatCard label={label} value={value} accent={accent} />
                </motion.div>
              ))}
            </motion.div>
          )}

          <div className="rounded-lg border border-brand-200 bg-white p-4 shadow-card">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-brand-500">Filter listings</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {filterTabs.map((tab) => {
                const active = tab.match(pathname || "", workflowFromUrl);
                return (
                  <Link
                    key={tab.href}
                    href={tab.href}
                    className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
                      active ? "bg-brand-900 text-white shadow-sm" : "border border-brand-300 bg-white text-brand-800 hover:bg-brand-50"
                    }`}
                  >
                    {tab.label}
                  </Link>
                );
              })}
            </div>

            {showFilterDropdowns ? (
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <label className="block text-xs font-medium text-brand-600">
                  Area
                  <select
                    className="mt-1 w-full rounded-md border border-brand-200 px-2 py-2 text-sm"
                    value={filters.area}
                    onChange={(e) => setFilters((f) => ({ ...f, area: e.target.value }))}
                  >
                    {AREA_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-xs font-medium text-brand-600">
                  Type
                  <select
                    className="mt-1 w-full rounded-md border border-brand-200 px-2 py-2 text-sm"
                    value={filters.property_type}
                    onChange={(e) => setFilters((f) => ({ ...f, property_type: e.target.value }))}
                  >
                    <option value="all">All types</option>
                    <option value="house">House</option>
                    <option value="apartment">Apartment</option>
                    <option value="other">Other</option>
                  </select>
                </label>
                <label className="block text-xs font-medium text-brand-600">
                  Beds
                  <select
                    className="mt-1 w-full rounded-md border border-brand-200 px-2 py-2 text-sm"
                    value={filters.bedrooms}
                    onChange={(e) => setFilters((f) => ({ ...f, bedrooms: e.target.value }))}
                  >
                    <option value="2">2+</option>
                    <option value="3">3+</option>
                    <option value="4">4+</option>
                  </select>
                </label>
                <label className="block text-xs font-medium text-brand-600">
                  Sort order
                  <select
                    className="mt-1 w-full rounded-md border border-brand-200 px-2 py-2 text-sm"
                    value={filters.sort}
                    onChange={(e) => setFilters((f) => ({ ...f, sort: e.target.value }))}
                  >
                    <option value="newest">Newest first</option>
                    <option value="price_desc">Price high to low</option>
                    <option value="price_asc">Price low to high</option>
                  </select>
                </label>
              </div>
            ) : (
              <p className="mt-3 text-xs text-brand-500">Open All Listings or New Today to use area, type, beds, and sort filters.</p>
            )}
          </div>

          <AnimatePresence mode="wait">
            {error ? (
              <motion.div
                key="err"
                initial={reduce ? false : { opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduce ? undefined : { opacity: 0 }}
                transition={springSnappy}
                className="rounded-lg border border-danger-600/25 bg-danger-50 px-4 py-3 text-sm text-danger-700"
              >
                {error}
              </motion.div>
            ) : null}
          </AnimatePresence>

          <AnimatePresence mode="wait">
            {loading ? (
              <motion.div
                key="load"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: reduce ? 0 : 0.2 }}
                className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
              >
                {[1, 2, 3, 4, 5, 6].map((i) => (
                  <motion.div
                    key={i}
                    initial={reduce ? false : { opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ ...springSnappy, delay: reduce ? 0 : i * 0.05 }}
                    className="overflow-hidden rounded-lg border border-brand-200 bg-white"
                  >
                    <div className="aspect-[4/3] animate-pulse bg-gradient-to-br from-brand-100 to-brand-50" />
                    <div className="space-y-2 border-t border-brand-100 p-4">
                      <div className="h-4 w-4/5 animate-pulse rounded bg-brand-100" />
                      <div className="h-5 w-1/3 animate-pulse rounded bg-brand-100" />
                      <div className="h-3 w-full animate-pulse rounded bg-brand-100" />
                    </div>
                  </motion.div>
                ))}
              </motion.div>
            ) : items.length === 0 ? (
              <motion.div
                key="empty"
                initial={reduce ? false : { opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={reduce ? undefined : { opacity: 0, y: -8 }}
                transition={springSnappy}
                className="rounded-lg border border-brand-200 bg-white p-6 shadow-card"
              >
                <h2 className="text-lg font-semibold text-brand-900">Nothing to show here yet</h2>
                <p className="mt-2 text-sm text-brand-600">{emptyHint || "No results matched this view."}</p>
                <Link
                  href="/dashboard/all"
                  className="mt-4 inline-flex rounded-md bg-ocean-700 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-ocean-800"
                >
                  View all listings
                </Link>
              </motion.div>
            ) : (
              <LayoutGroup id={`listings-${endpoint}`}>
                <motion.div
                  key={`grid-${endpoint}`}
                  initial={reduce ? false : { opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: reduce ? 0 : 0.2 }}
                  layout
                  className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4"
                >
                  {items.map((item) => (
                    <ListingCard
                      key={item.listing_group_id}
                      item={item}
                      variant={endpoint === "/listings/new" ? "new_today" : "default"}
                      onRefresh={() => loadDashboard({ showLoading: false })}
                    />
                  ))}
                </motion.div>
              </LayoutGroup>
            )}
          </AnimatePresence>
        </section>
      </div>
    </main>
  );
}

export default function DashboardPage(props: { endpoint: string; title: string }) {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-brand-50 px-4 py-16 text-center text-sm text-brand-600">Loading dashboard…</main>
      }
    >
      {/* Remount per route so list + summary always match the tab (e.g. Not interested only). */}
      <DashboardPageInner key={props.endpoint} {...props} />
    </Suspense>
  );
}
