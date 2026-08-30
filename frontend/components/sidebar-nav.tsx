"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, Review } from "@/lib/api";
import { useSidebar } from "./app-shell";

function Chevrons({ dir }: { dir: "left" | "right" }) {
  return (
    <svg
      width="15"
      height="15"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={dir === "right" ? "rotate-180" : undefined}
    >
      <path d="m11 17-5-5 5-5" />
      <path d="m18 17-5-5 5-5" />
    </svg>
  );
}

export default function SidebarNav() {
  const pathname = usePathname();
  const { collapsed, toggle } = useSidebar();
  const [reviews, setReviews] = useState<Review[]>([]);

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

  return (
    <aside
      className={`flex h-screen shrink-0 flex-col overflow-hidden border-r border-line bg-white transition-[width] duration-300 ease-in-out ${
        collapsed ? "w-14" : "w-64"
      }`}
    >
      <div
        className={`flex items-center py-5 ${
          collapsed ? "flex-col gap-2.5" : "gap-2.5 px-5"
        }`}
      >
        <Link
          href="/"
          title="Arca Bulk Review"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-brand text-sm font-bold text-white"
        >
          A
        </Link>
        {!collapsed && (
          <div className="min-w-0 flex-1 whitespace-nowrap">
            <div className="text-sm font-semibold leading-tight">
              Arca Bulk Review
            </div>
            <div className="text-[11px] text-ink-soft">Regulatory portfolio</div>
          </div>
        )}
        <button
          onClick={toggle}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-ink-soft hover:bg-paper hover:text-ink"
        >
          <Chevrons dir={collapsed ? "right" : "left"} />
        </button>
      </div>

      {collapsed ? (
        <nav className="flex flex-col items-center gap-1.5">
          <Link
            href="/"
            title="New review"
            className={`flex h-8 w-8 items-center justify-center rounded-lg text-lg ${
              pathname === "/"
                ? "bg-brand-tint/50 text-brand"
                : "text-ink-soft hover:bg-paper"
            }`}
          >
            +
          </Link>
        </nav>
      ) : (
        <>
          <nav className="px-3">
            <Link
              href="/"
              className={`block whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium ${
                pathname === "/"
                  ? "bg-brand-tint/50 text-brand"
                  : "text-ink-soft hover:bg-paper"
              }`}
            >
              New review
            </Link>
          </nav>

          <div className="mt-5 whitespace-nowrap px-5 text-[11px] font-semibold uppercase tracking-wide text-ink-soft">
            Recent reviews
          </div>
          <div className="mt-1 flex-1 overflow-y-auto px-3 pb-4">
            {reviews.map((r) => (
              <Link
                key={r.review_id}
                href={`/reviews/${r.review_id}`}
                className={`mt-0.5 block rounded-lg px-3 py-2 ${
                  pathname?.includes(r.review_id)
                    ? "bg-brand-tint/50"
                    : "hover:bg-paper"
                }`}
              >
                <div className="truncate text-[13px] font-medium">
                  {r.name || r.prompt.slice(0, 40)}
                </div>
                <div className="mt-0.5 flex items-center gap-1.5 whitespace-nowrap text-[11px] text-ink-soft">
                  <StatusDot status={r.status} />
                  {r.status.toLowerCase()}
                </div>
              </Link>
            ))}
            {reviews.length === 0 && (
              <div className="whitespace-nowrap px-3 py-2 text-[12px] text-ink-soft">
                No reviews yet
              </div>
            )}
          </div>
        </>
      )}
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
  return <span className={`inline-block h-1.5 w-1.5 rounded-full ${color}`} />;
}
