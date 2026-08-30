"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { api, Review } from "@/lib/api";
import { useSidebar } from "./app-shell";

const MOTION = {
  expandedWidth: 224,
  collapsedWidth: 52,
  duration: 280,
  copyDuration: 180,
  copyOffset: 8,
  easing: "cubic-bezier(0.16, 1, 0.3, 1)",
};

const SEARCH_MOTION = { duration: 180, easing: "cubic-bezier(0.16, 1, 0.3, 1)" };

/* ---- icons (inline; the Beautiful UI icon set is not on npm) ---- */

function IconSidebarArrow({ flipped = false }: { flipped?: boolean }) {
  return (
    <svg
      width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"
      className={flipped ? "-scale-x-100" : undefined}
    >
      <rect x="3" y="4" width="18" height="16" rx="3" />
      <path d="M9 4v16" />
      <path d="m16 9-3 3 3 3" />
    </svg>
  );
}

function IconEdit() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}

function IconSearch() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round">
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  );
}

function IconCross() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round">
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

/* ----------------------------------------------------------------- */

export default function SidebarNav() {
  const pathname = usePathname();
  const router = useRouter();
  const { collapsed, toggle } = useSidebar();
  const [reviews, setReviews] = useState<Review[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api.listReviews().then((d) => alive && setReviews(d.reviews)).catch(() => {});
    load();
    const t = setInterval(load, 4000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  useEffect(() => {
    if (searchOpen) searchRef.current?.focus();
  }, [searchOpen]);

  const collapse = () => {
    setSearchOpen(false);
    setQuery("");
    toggle();
  };

  const visible = reviews.filter((r) =>
    (r.name || r.prompt).toLowerCase().includes(query.trim().toLowerCase())
  );

  return (
    <aside
      data-sidebar-collapsed={collapsed}
      aria-label="Navigation"
      className="relative flex h-screen shrink-0 overflow-hidden border-r border-line bg-white transition-[width]"
      style={{
        width: collapsed ? MOTION.collapsedWidth : MOTION.expandedWidth,
        transitionDuration: `${MOTION.duration}ms`,
        transitionTimingFunction: MOTION.easing,
        "--sidebar-copy-duration": `${MOTION.copyDuration}ms`,
        "--sidebar-copy-offset": `${MOTION.copyOffset}px`,
        "--sidebar-easing": MOTION.easing,
      } as CSSProperties}
    >
      <div className="flex min-h-0 w-[224px] shrink-0 flex-col pt-3">
        {/* header: brand control ↔ expand control occupy the same spot */}
        <div className="relative mb-2.5 h-10 shrink-0">
          <Link
            href="/"
            aria-hidden={collapsed}
            tabIndex={collapsed ? -1 : 0}
            className="sidebar-brand-control absolute left-2 top-0.5 flex h-9 w-[164px] items-center rounded-lg px-2 hover:bg-paper"
          >
            <span className="flex size-6 shrink-0 items-center justify-center rounded-[7px] bg-brand text-[11px] font-semibold text-white">
              A
            </span>
            <span className="sidebar-copy ml-2 min-w-0 flex-1">
              <span className="block truncate text-[13.5px] font-semibold leading-tight text-ink">
                Arca Bulk Review
              </span>
              <span className="block text-[10.5px] leading-tight text-ink-soft">
                Regulatory portfolio
              </span>
            </span>
          </Link>

          <button
            type="button"
            aria-label="Collapse sidebar"
            aria-hidden={collapsed}
            tabIndex={collapsed ? -1 : 0}
            onClick={collapse}
            className="sidebar-collapse-control absolute right-2 top-1 flex size-8 items-center justify-center rounded-lg text-ink-soft/70 hover:bg-paper hover:text-ink"
          >
            <IconSidebarArrow />
          </button>
          <button
            type="button"
            aria-label="Expand sidebar"
            aria-hidden={!collapsed}
            tabIndex={collapsed ? 0 : -1}
            onClick={toggle}
            className="sidebar-expand-control absolute left-2 top-1 flex size-8 items-center justify-center rounded-lg text-ink-soft/70 hover:bg-paper hover:text-ink"
          >
            <IconSidebarArrow flipped />
          </button>
        </div>

        {/* primary nav */}
        <div className="flex flex-col gap-px">
          <button
            type="button"
            title="New review"
            onClick={() => router.push("/")}
            className={`sidebar-row relative mx-2 flex h-8 items-center rounded-lg px-2 text-left transition-colors ${
              pathname === "/" ? "bg-brand-tint/40" : "hover:bg-paper"
            }`}
          >
            <span className={`flex size-5 shrink-0 items-center justify-center ${pathname === "/" ? "text-brand" : "text-ink-soft"}`}>
              <IconEdit />
            </span>
            <span className={`sidebar-copy ml-1.5 min-w-0 flex-1 truncate text-[13.5px] font-medium ${pathname === "/" ? "text-brand" : "text-ink-soft"}`}>
              New review
            </span>
          </button>
        </div>

        {/* reviews history + growing search field */}
        <div className="sidebar-copy mt-4 min-h-0 flex-1 overflow-y-auto">
          <div className="relative mx-2 mb-1 h-8">
            <div
              aria-hidden={searchOpen}
              className={`absolute inset-0 flex items-center px-2 text-[11px] font-semibold uppercase tracking-wide text-ink-soft transition-[opacity,transform] ${
                searchOpen ? "pointer-events-none -translate-x-1 opacity-0" : "translate-x-0 opacity-100"
              }`}
              style={{ transitionDuration: `${SEARCH_MOTION.duration}ms`, transitionTimingFunction: SEARCH_MOTION.easing }}
            >
              Reviews
            </div>
            <button
              type="button"
              aria-label="Search reviews"
              onClick={() => setSearchOpen(true)}
              className={`absolute right-0 top-0 z-10 flex size-8 items-center justify-center rounded-lg text-ink-soft/70 transition-opacity hover:bg-paper hover:text-ink ${
                searchOpen ? "pointer-events-none opacity-0" : "opacity-100"
              }`}
              style={{ transitionDuration: `${SEARCH_MOTION.duration}ms` }}
            >
              <IconSearch />
            </button>
            <div
              className={`absolute right-0 top-0 z-20 flex h-8 items-center overflow-hidden rounded-lg bg-paper text-ink-soft ring-1 ring-line transition-[width,opacity] ${
                searchOpen ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
              }`}
              style={{
                width: searchOpen ? "100%" : 28,
                transitionDuration: `${SEARCH_MOTION.duration}ms`,
                transitionTimingFunction: SEARCH_MOTION.easing,
              }}
            >
              <span className="ml-2 flex shrink-0 items-center justify-center">
                <IconSearch />
              </span>
              <input
                ref={searchRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Escape") {
                    setSearchOpen(false);
                    setQuery("");
                  }
                }}
                placeholder="Search reviews"
                aria-label="Search reviews"
                className="ml-1.5 min-w-0 flex-1 bg-transparent text-[12.5px] font-medium text-ink outline-none placeholder:text-ink-soft/60"
              />
              <button
                type="button"
                aria-label="Close search"
                onClick={() => {
                  setSearchOpen(false);
                  setQuery("");
                }}
                className="flex size-8 shrink-0 items-center justify-center rounded-lg text-ink-soft/70 hover:text-ink"
              >
                <IconCross />
              </button>
            </div>
          </div>

          <div className="flex flex-col gap-px pb-4">
            {visible.map((r) => {
              const active = pathname?.includes(r.review_id);
              return (
                <Link
                  key={r.review_id}
                  href={`/reviews/${r.review_id}`}
                  title={r.name || r.prompt}
                  className={`relative mx-2 flex h-8 w-[208px] items-center gap-1.5 rounded-lg px-2 ${
                    active ? "bg-brand-tint/40" : "hover:bg-paper"
                  }`}
                >
                  <StatusDot status={r.status} />
                  <span className={`min-w-0 flex-1 truncate text-[13px] font-medium ${active ? "text-ink" : "text-ink-soft"}`}>
                    {r.name || r.prompt.slice(0, 40)}
                  </span>
                </Link>
              );
            })}
            {query && visible.length === 0 && (
              <div className="mx-2 px-2 py-2 text-[12px] text-ink-soft">No reviews found</div>
            )}
            {!query && reviews.length === 0 && (
              <div className="mx-2 px-2 py-2 text-[12px] text-ink-soft">No reviews yet</div>
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}

function StatusDot({ status }: { status: string }) {
  const color =
    status === "COMPLETE"
      ? "bg-brand"
      : status === "FAILED"
        ? "bg-red-500"
        : "bg-accent animate-pulse";
  return <span className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${color}`} />;
}
