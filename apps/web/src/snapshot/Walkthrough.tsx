// The snapshot's walkthrough (walkthrough.ts) in a panel beside the console: on wide
// screens a column on the right, on phones a full-screen sheet. Each step's "Show me"
// opens the page it talks about, picks the tab or proposal and points at the spot.
import { useEffect, useState } from "react";
import { useNavigate, type NavigateFunction } from "react-router-dom";
import clsx from "clsx";
import { ArrowRight, BookOpen, X } from "lucide-react";
import { WALKTHROUGH, type Block, type Target } from "./walkthrough";

const OPEN_KEY = "aof.walkthrough.open";

function readOpen(): boolean {
  try {
    return localStorage.getItem(OPEN_KEY) !== "0";
  } catch {
    return true;
  }
}

const CSS = `
@media (min-width: 1024px) {
  body.wt-open #root > div:first-child { margin-right: 24rem; }
  body.wt-open .wt-banner { right: calc(24rem + 0.75rem); }
}
.wt-flash { outline: 3px solid rgb(var(--c-accent-400)); outline-offset: 3px; border-radius: 6px; animation: wt-flash 2.6s ease-out forwards; }
@keyframes wt-flash { 0%, 70% { outline-color: rgb(var(--c-accent-400)); } 100% { outline-color: transparent; } }
`;

const sleep = (ms: number) => new Promise((done) => setTimeout(done, ms));

async function find<T>(get: () => T | null | undefined, ms = 5000): Promise<T | null> {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    const found = get();
    if (found) return found;
    await sleep(100);
  }
  return null;
}

const buttons = (selector: string, test: (text: string) => boolean) =>
  [...document.querySelectorAll<HTMLElement>(selector)].find((el) => test((el.textContent ?? "").trim()));

/** The element whose own text holds `text`, inside the page (not the navigation). */
function textElement(text: string): HTMLElement | null {
  const main = document.querySelector("main");
  if (!main) return null;
  const walk = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) if (n.textContent?.includes(text)) return n.parentElement;
  return null;
}

function flash(els: (HTMLElement | null)[]) {
  const shown = els.filter((el): el is HTMLElement => !!el);
  shown[shown.length - 1]?.scrollIntoView({ block: "center", behavior: "smooth" });
  for (const el of shown) {
    el.classList.remove("wt-flash");
    void el.offsetWidth; // restart the animation
    el.classList.add("wt-flash");
    setTimeout(() => el.classList.remove("wt-flash"), 2700);
  }
}

async function show(t: Target, navigate: NavigateFunction) {
  if (location.hash.slice(1) !== t.route) {
    navigate(t.route);
    await sleep(150); // the old page goes before we look for the new one
  }
  const spots: (HTMLElement | null)[] = [];
  if (t.proposal) {
    const pick = await find(() => buttons('aside[aria-label="Proposals"] li button', (s) => s.startsWith(t.proposal!)));
    pick?.click();
    spots.push(pick);
  }
  if (t.tab) {
    const tab = await find(() => buttons('main [role="tab"]', (s) => s === t.tab));
    tab?.click();
    spots.push(tab);
  }
  if (t.highlight) {
    await sleep(100);
    spots.push(await find(() => textElement(t.highlight!)));
  } else if (t.proposal || t.tab) {
    await sleep(100);
    spots.push(document.querySelector<HTMLElement>('main section[aria-label="Proposal"]'));
  }
  if (!spots.some(Boolean)) spots.push(await find(() => document.querySelector<HTMLElement>("main h1")));
  flash(spots);
}

/** **Bold** for what the screen shows, `code` for configuration and event fields. */
function Text({ text }: { text: string }) {
  return (
    <>
      {text.split("`").map((chunk, j) =>
        j % 2 ? (
          <code key={j} className="rounded bg-surface-100 px-1 font-mono text-[0.85em] text-surface-800">{chunk}</code>
        ) : (
          chunk.split("**").map((part, i) => (i % 2 ? <strong key={`${j}-${i}`} className="font-semibold text-surface-900">{part}</strong> : part))
        ),
      )}
    </>
  );
}

function Blocks({ blocks }: { blocks: Block[] }) {
  return (
    <div className="space-y-2">
      {blocks.map((b, i) =>
        typeof b === "string" ? (
          <p key={i}><Text text={b} /></p>
        ) : (
          <ul key={i} className="list-disc space-y-1.5 pl-4">
            {b.map((point, j) => <li key={j}><Text text={point} /></li>)}
          </ul>
        ),
      )}
    </div>
  );
}

/** `recorded` says whether the snapshot holds the page a step points at. */
export default function Walkthrough({ recorded }: { recorded: (route: string) => boolean }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(readOpen);
  const [at, setAt] = useState<string | null>(null);

  useEffect(() => {
    document.body.classList.toggle("wt-open", open);
    try {
      localStorage.setItem(OPEN_KEY, open ? "1" : "0");
    } catch {
      /* storage unavailable: the panel opens next time too */
    }
  }, [open]);

  const go = (id: string, t: Target) => {
    setAt(id);
    if (window.matchMedia("(max-width: 1023px)").matches) setOpen(false);
    void show(t, navigate);
  };

  return (
    <>
      <style>{CSS}</style>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-[calc(env(safe-area-inset-bottom)+6.5rem)] right-3 z-50 inline-flex items-center gap-1.5 rounded-full bg-brand px-3.5 py-2 text-sm font-medium text-brand-fg shadow-lg hover:bg-brand-strong lg:bottom-14"
        >
          <BookOpen size={15} /> Walkthrough
        </button>
      )}
      {open && (
        <aside
          aria-label="Walkthrough"
          className="fixed inset-0 z-50 flex flex-col bg-card text-surface-700 lg:inset-y-0 lg:left-auto lg:right-0 lg:z-40 lg:w-96 lg:border-l lg:border-surface-200 lg:shadow-xl"
        >
          <div className="flex items-center gap-2 border-b border-surface-200 px-4 py-3">
            <BookOpen size={16} className="shrink-0 text-primary-600" />
            <h2 className="min-w-0 flex-1 text-sm font-semibold text-surface-900">{WALKTHROUGH.title}</h2>
            <button onClick={() => setOpen(false)} aria-label="Close the walkthrough" className="rounded-md p-1 text-surface-500 hover:bg-surface-100 hover:text-surface-800">
              <X size={16} />
            </button>
          </div>
          <div className="flex-1 space-y-5 overflow-y-auto px-4 py-4 text-[13px] leading-relaxed">
            <Blocks blocks={WALKTHROUGH.intro} />
            {WALKTHROUGH.examples.map((ex, e) => (
              <section key={ex.title} className="space-y-3">
                <div className="border-t border-surface-200 pt-4">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-primary-600">Example {e + 1}</p>
                  <h3 className="mt-0.5 text-[15px] font-semibold text-surface-900">{ex.title}</h3>
                  <p className="mt-1 text-surface-500">{ex.subtitle}</p>
                </div>
                <ol className="space-y-3">
                  {ex.steps.map((step, s) => {
                    const id = `${e}-${s}`;
                    return (
                      <li
                        key={id}
                        className={clsx("rounded-lg border px-3 py-2.5", at === id ? "border-accent-400 bg-accent-50/60" : "border-surface-200")}
                      >
                        <div className="mb-1.5 flex items-baseline gap-2">
                          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-surface-100 text-[11px] font-semibold text-surface-700">{s + 1}</span>
                          <h4 className="font-semibold text-surface-900">{step.title}</h4>
                        </div>
                        <Blocks blocks={step.body} />
                        {step.show && recorded(step.show.route) && (
                          <button
                            onClick={() => go(id, step.show!)}
                            className="mt-2 inline-flex items-center gap-1 rounded-md border border-primary-200 px-2 py-1 text-xs font-medium text-primary-700 hover:bg-primary-50"
                          >
                            Show me <ArrowRight size={12} />
                          </button>
                        )}
                      </li>
                    );
                  })}
                </ol>
              </section>
            ))}
            <div className="border-t border-surface-200 pt-4 text-surface-500">
              <Blocks blocks={WALKTHROUGH.outro} />
            </div>
          </div>
        </aside>
      )}
    </>
  );
}
