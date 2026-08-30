"use client";

/** Beautiful UI-style tooltip with an ⓘ icon trigger (hover/focus). */
export default function InfoTip({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex">
      <button
        type="button"
        aria-label="What is this metric?"
        className="flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-semibold text-ink-soft/60 ring-1 ring-line hover:text-ink hover:ring-ink-soft/50 focus:outline-none"
      >
        i
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-2 w-60 -translate-x-1/2 rounded-xl bg-ink px-3 py-2 text-left text-[11.5px] font-normal leading-relaxed text-white opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100"
      >
        {text}
        <span className="absolute left-1/2 top-full -ml-1 border-4 border-transparent border-t-ink" />
      </span>
    </span>
  );
}
