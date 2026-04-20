"use client";

import { motion, useReducedMotion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { apiFetch } from "@/lib/api";
import { springSnappy } from "@/lib/motion";

const WORKFLOW_OPTIONS: { value: string; label: string }[] = [
  { value: "new", label: "Unreviewed" },
  { value: "seen", label: "Seen" },
  { value: "favourite", label: "Favourite" },
  { value: "need_to_call", label: "Need to call" },
  { value: "viewing_arranged", label: "Viewing arranged" },
  { value: "offer_made", label: "Offer made" },
  { value: "not_available", label: "Gone" },
  { value: "not_interested", label: "Not interested" },
];

function workflowBadgeClass(w: string) {
  switch (w) {
    case "new":
      return "bg-slate-100 text-slate-800";
    case "seen":
      return "bg-gray-100 text-gray-800";
    case "favourite":
      return "bg-amber-100 text-amber-900";
    case "need_to_call":
      return "bg-sky-100 text-sky-900";
    case "viewing_arranged":
      return "bg-violet-100 text-violet-900";
    case "offer_made":
      return "bg-emerald-200 text-emerald-950";
    case "not_available":
      return "bg-red-100 text-red-900";
    case "not_interested":
      return "bg-gray-50 text-gray-500";
    default:
      return "bg-brand-100 text-brand-800";
  }
}

function formatPropertyType(t: string | null | undefined) {
  if (!t) return "Property";
  if (t === "apartment") return "Apartment";
  if (t === "house") return "House";
  if (t === "land") return "Land";
  if (t === "villa") return "Villa";
  return t.charAt(0).toUpperCase() + t.slice(1);
}

const HAS_LETTER = /\p{L}/u;

function stripHtmlTags(raw: string) {
  return raw
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;|&#160;/gi, " ")
    .replace(/\u00a0/g, " ");
}

/** At most `maxWords` short tokens (default 1–2 words) for card layout; full text on `title` hover only. */
function microBlurb(raw: string | null | undefined, maxWords = 2, maxCharsTotal = 28) {
  const full = stripHtmlTags(String(raw ?? ""))
    .replace(/\s+/g, " ")
    .trim();
  if (!full) return { display: "", full: "" };
  const tokens = full
    .split(/\s+/)
    .map((t) => t.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, ""))
    .filter((t) => t.length > 0);
  const withLetters = tokens.filter((t) => HAS_LETTER.test(t));
  const picked = (withLetters.length ? withLetters : tokens).slice(0, maxWords).map((t) => (t.length > 16 ? `${t.slice(0, 16)}…` : t));
  let display = picked.join(" ").trim();
  if (display.length > maxCharsTotal) display = `${display.slice(0, Math.max(1, maxCharsTotal - 1)).trimEnd()}…`;
  return { display, full: full };
}

/** Short fixed headline: type + typology (e.g. Apartment T2). Raw title stays on hover. */
function cardHeadline(item: { property_type?: string | null; bedrooms?: number | null }) {
  const type = formatPropertyType(item.property_type);
  const n = item.bedrooms;
  if (n != null && Number.isFinite(Number(n))) return `${type} T${n}`;
  return type;
}

function isNewTodayFromIso(firstSeenAt: string | null | undefined) {
  if (!firstSeenAt) return false;
  const d = new Date(firstSeenAt);
  if (Number.isNaN(d.getTime())) return false;
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

/** Portal listing date if present, else first scrape (ISO from API). Shown as "Listed: 20 Apr 2026". */
function formatListedLabel(publishedAt: string | null | undefined, firstSeenAt: string | null | undefined) {
  const iso = (publishedAt && String(publishedAt).trim()) || (firstSeenAt && String(firstSeenAt).trim()) || "";
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const formatted = d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  return `Listed: ${formatted}`;
}

export default function ListingCard({
  item,
  onRefresh,
  variant = "default",
}: {
  item: any;
  onRefresh: () => void;
  variant?: "default" | "new_today";
}) {
  const reduce = useReducedMotion();
  const [note, setNote] = useState(item.note ?? "");
  const [saving, setSaving] = useState(false);
  const noteTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setNote(item.note ?? "");
  }, [item.listing_group_id, item.note]);

  const priceLabel = useMemo(() => {
    if (item.price == null) return "Price on request";
    const n = typeof item.price === "number" ? item.price : Number(item.price);
    if (!Number.isFinite(n)) return "Price on request";
    return `€${Math.round(n).toLocaleString("en-IE")}`;
  }, [item.price]);

  const areaPill = item.municipality || item.area_name || item.location_text || "Madeira";
  const wf = item.workflow_status || "new";
  const newToday = isNewTodayFromIso(item.first_seen_at);

  const headline = useMemo(() => cardHeadline(item), [item.property_type, item.bedrooms]);
  const descBlurb = useMemo(() => microBlurb(item.description, 2, 28), [item.description]);
  const listedLabel = useMemo(
    () => formatListedLabel(item.published_at, item.first_seen_at),
    [item.published_at, item.first_seen_at],
  );

  const listingUrl = useMemo(() => {
    const s = (item.source_url || "").trim();
    return s || item.canonical_url || "#";
  }, [item.source_url, item.canonical_url]);

  const otherPortalLinks = useMemo(() => {
    const raw = item.portal_links;
    if (!Array.isArray(raw) || raw.length < 2) return [];
    return raw.filter((p: { url?: string }) => p.url && String(p.url).trim() !== listingUrl);
  }, [item.portal_links, listingUrl]);

  const persistNote = useCallback(async (text: string) => {
    setSaving(true);
    try {
      await apiFetch(`/actions/${item.listing_group_id}/state`, {
        method: "PATCH",
        body: JSON.stringify({ note: text }),
      });
    } finally {
      setSaving(false);
    }
  }, [item.listing_group_id]);

  const onNoteChange = (text: string) => {
    setNote(text);
    if (noteTimer.current) clearTimeout(noteTimer.current);
    noteTimer.current = setTimeout(() => {
      void persistNote(text);
    }, 650);
  };

  useEffect(
    () => () => {
      if (noteTimer.current) clearTimeout(noteTimer.current);
    },
    [],
  );

  async function setWorkflow(next: string) {
    await apiFetch(`/actions/${item.listing_group_id}/state`, {
      method: "PATCH",
      body: JSON.stringify({ workflow_status: next }),
    });
    onRefresh();
  }

  async function toggleStar() {
    if (item.is_saved) {
      await apiFetch(`/actions/${item.listing_group_id}/unsave`, { method: "POST" });
    } else {
      await apiFetch(`/actions/${item.listing_group_id}/save`, { method: "POST" });
    }
    onRefresh();
  }

  return (
    <motion.article
      layout
      initial={reduce ? false : { opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={springSnappy}
      whileHover={reduce ? undefined : { y: -4 }}
      className={`group flex flex-col overflow-hidden rounded-lg border border-brand-200 bg-white shadow-card transition-shadow hover:border-ocean-600/25 hover:shadow-lg ${
        variant === "new_today" && newToday ? "border-l-4 border-l-emerald-500 ring-1 ring-emerald-100" : ""
      }`}
    >
      <div className="relative aspect-[4/3] overflow-hidden bg-brand-100">
        {newToday ? (
          <span
            className="absolute left-3 top-3 z-10 h-2.5 w-2.5 rounded-full bg-emerald-500 shadow ring-2 ring-white"
            title="New in today’s scan"
            aria-hidden
          />
        ) : null}
        {item.image_url ? (
          <motion.img
            src={item.image_url}
            alt=""
            className="h-full w-full object-cover"
            whileHover={reduce ? undefined : { scale: 1.04 }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-brand-500">No image</div>
        )}
        <div className="absolute right-2 top-2 flex flex-col items-end gap-1">
          {item.eligibility_status === "filtered_out" ? (
            <span className="rounded bg-amber-100/95 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-900 shadow-sm backdrop-blur-sm">
              Outside brief
            </span>
          ) : null}
        </div>
      </div>

      <div className="flex flex-1 flex-col border-t border-brand-100 p-4">
        {variant === "new_today" ? (
          newToday ? (
            <div className="flex items-center gap-2 text-emerald-800">
              <span className="h-2 w-2 shrink-0 rounded-full bg-emerald-500" aria-hidden />
              <span className="text-sm font-semibold tracking-tight">New today</span>
            </div>
          ) : null
        ) : (
          <div className="flex flex-wrap gap-1.5">
            <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${workflowBadgeClass(wf)}`}>
              {WORKFLOW_OPTIONS.find((o) => o.value === wf)?.label ?? wf}
            </span>
          </div>
        )}

        <div className="mt-3 flex items-start justify-between gap-2">
          <p className="text-2xl font-bold tabular-nums text-ocean-800">{priceLabel}</p>
          <motion.button
            type="button"
            whileTap={{ scale: 0.92 }}
            transition={springSnappy}
            onClick={() => void toggleStar()}
            className="rounded-md p-1 text-amber-500 hover:bg-amber-50 hover:text-amber-600"
            aria-label={item.is_saved ? "Remove favourite" : "Add favourite"}
            title="Favourite"
          >
            <svg
              className="h-7 w-7"
              viewBox="0 0 24 24"
              fill={item.is_saved ? "currentColor" : "none"}
              stroke="currentColor"
              strokeWidth="1.8"
            >
              <path d="M12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" />
            </svg>
          </motion.button>
        </div>

        <h3
          className="mt-1 text-base font-semibold leading-snug text-brand-900 text-balance"
          title={item.title ? String(item.title).replace(/\s+/g, " ").trim() : undefined}
        >
          {headline}
        </h3>

        {descBlurb.display ? (
          <p
            className="mt-2 line-clamp-1 max-h-[1.35rem] overflow-hidden text-ellipsis rounded-md bg-brand-50 px-2 py-1 text-xs leading-tight text-brand-700 break-words"
            title={descBlurb.full !== descBlurb.display ? descBlurb.full : undefined}
          >
            {descBlurb.display}
          </p>
        ) : null}

        <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-brand-700">
          <span className="rounded-full bg-brand-100 px-2 py-0.5 font-medium">{formatPropertyType(item.property_type)}</span>
          <span className="rounded-full bg-brand-100 px-2 py-0.5 font-medium">
            {item.bedrooms != null ? `${item.bedrooms} beds` : "— beds"}
          </span>
          <span className="rounded-full bg-brand-100 px-2 py-0.5 font-medium">{areaPill}</span>
          <span className="rounded-full bg-brand-100 px-2 py-0.5 font-medium">{item.primary_source || "Source"}</span>
        </div>

        {listedLabel ? (
          <p
            className="mt-2.5 rounded-md border border-sky-200/80 bg-sky-50 px-2.5 py-1.5 text-xs font-medium text-brand-900"
            title={item.published_at ? "Date from the property portal when available" : "First seen in our scans (portal date not available)"}
          >
            {listedLabel}
          </p>
        ) : null}

        <label className="mt-3 block text-[11px] font-semibold uppercase tracking-wide text-brand-500">Status</label>
        <select
          className="mt-1 w-full rounded-md border border-brand-200 bg-white px-2 py-2 text-sm font-medium text-brand-900"
          value={wf}
          onChange={(e) => void setWorkflow(e.target.value)}
        >
          {WORKFLOW_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>

        <label className="mt-3 block text-[11px] font-semibold uppercase tracking-wide text-brand-500">Notes</label>
        <textarea
          className="mt-1 min-h-[4.5rem] w-full resize-y rounded-md border border-brand-200 px-2 py-2 text-sm text-brand-900 placeholder:text-brand-400"
          placeholder="Private notes (saved automatically)"
          value={note}
          onChange={(e) => onNoteChange(e.target.value)}
        />
        {saving ? <p className="mt-1 text-[10px] text-brand-500">Saving notes…</p> : null}

        <div className="mt-auto space-y-2 border-t border-brand-100 pt-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              {item.price_reduced ? (
                <span className="rounded-full bg-red-100 px-2 py-0.5 text-[11px] font-semibold text-red-800">
                  Price reduced
                </span>
              ) : null}
              <span className="text-xs font-medium text-brand-500">{item.primary_source || "Source"}</span>
            </div>
            <motion.a
              href={listingUrl}
              target="_blank"
              rel="noopener noreferrer"
              whileTap={{ scale: 0.96 }}
              transition={springSnappy}
              className="rounded-md border border-ocean-600 bg-ocean-700 px-3 py-2 text-xs font-semibold text-white hover:bg-ocean-800"
            >
              {item.primary_source ? `View on ${item.primary_source}` : "View listing"}
            </motion.a>
          </div>
          {otherPortalLinks.length ? (
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wide text-brand-500">Also on</p>
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
                {otherPortalLinks.map((p: { source_name: string; url: string }) => (
                  <a
                    key={p.url}
                    href={p.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-medium text-ocean-800 underline decoration-ocean-600/40 underline-offset-2 hover:text-ocean-950"
                  >
                    {p.source_name}
                  </a>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </motion.article>
  );
}
