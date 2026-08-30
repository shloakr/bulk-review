"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, Review } from "@/lib/api";

export default function SidebarNav() {
  const pathname = usePathname();
  const [reviews, setReviews] = useState<Review[]>([]);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem("sidebar-collapsed") === "1");
    } catch {}
  }, []);
  const toggle = () => {
    setCollapsed((c) => {
      try {
        localStorage.setItem("sidebar-collapsed", c ? "0" : "1");
      } catch {}
      return !c;
    });
  };

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

  if (collapsed) {
    return (
      <aside className="flex h-screen w-14 shrink-0 flex-col items-center gap-3 border-r border-line bg-white py-5">
        <button
          onClick={toggle}
          title="Expand sidebar"
          className="flex h-8 w-8 items-center justify-center rounded-xl bg-brand text-sm font-bold text-white"
        >
          A
        </button>
        <Link
          href="/"
          title="New review"
          className="flex h-8 w-8 items-center justify-center rounded-lg text-lg text-ink-soft hover:bg-paper"
        >
          +
        </Link>
      </aside>
    );
  }

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-line bg-white">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-brand text-sm font-bold text-white">
          A
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold leading-tight">Arca Bulk Review</div>
          <div className="text-[11px] text-ink-soft">Regulatory portfolio</div>
        </div>
        <button
          onClick={toggle}
          title="Collapse sidebar"
          className="rounded-lg px-1.5 py-1 text-ink-soft hover:bg-paper"
        >
          «
        </button>
      </div>

      <nav className="px-3">
        <Link
          href="/"
          className={`block rounded-lg px-3 py-2 text-sm font-medium ${
            pathname === "/"
              ? "bg-brand-tint/50 text-brand"
              : "text-ink-soft hover:bg-paper"
          }`}
        >
          New review
        </Link>
      </nav>

      <div className="mt-5 px-5 text-[11px] font-semibold uppercase tracking-wide text-ink-soft">
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
            <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-ink-soft">
              <StatusDot status={r.status} />
              {r.status.toLowerCase()}
            </div>
          </Link>
        ))}
        {reviews.length === 0 && (
          <div className="px-3 py-2 text-[12px] text-ink-soft">No reviews yet</div>
        )}
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
  return <span className={`inline-block h-1.5 w-1.5 rounded-full ${color}`} />;
}
