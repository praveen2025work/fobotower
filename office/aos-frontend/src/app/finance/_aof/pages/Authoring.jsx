// Generated from apps/web/src/pages/Authoring.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see office/README.md.
// Authoring, three ways in: answer a few questions (no model), describe the
// work in a BRD (a model drafts it when one is connected), or start from a
// template. Whichever way, the platform's own validator judges the draft, the
// author fixes what it lists, and another owner approves before it goes live.

import { useState } from "react";
import { Link } from "../office/router";
import clsx from "clsx";
import { CheckCircle2, FileText, LayoutTemplate, ListChecks, Sparkles, Upload } from "lucide-react";

import GuidedForm from "../components/authoring/GuidedForm";
import {
  useApproveVersion,
  useAuthoringModes,
  useGuidedDraft,
  useDraftFromBrd,
  useDrafts,
  useImportBundle,
  useSubmitDraft,
  useTemplates,
} from "../api/aof";
import { Card, Empty, ErrorState, Fold, Loading, PageHeader, WorkflowStepper, formatTime } from "../components/ui";

export default function Authoring() {
  const [brd, setBrd] = useState("");
  const [yamlText, setYamlText] = useState("");
  const [note, setNote] = useState("");
  const draft = useDraftFromBrd();
  const submit = useSubmitDraft();
  const templates = useTemplates();
  const guided = useGuidedDraft();
  const modes = useAuthoringModes();
  const [way, setWay] = useState("guided");
  const [fromTemplate, setFromTemplate] = useState(null);
  const [latest, setLatest] = useState(null);
  const result = fromTemplate ?? latest;

  const applyTemplate = (id) => {
    const t = templates.data?.find((x) => x.id === id);
    if (!t) return;
    setYamlText(t.yaml);
    setFromTemplate({
      yaml: t.yaml,
      manifest: null,
      problems: [],
      author: `template: ${t.name}`,
      assumptions: ["Replace every YOUR_… placeholder (roles, entity, service account) and the id before submitting."],
    });
    submit.reset();
  };

  const show = (r) => {
    setFromTemplate(null);
    setLatest(r);
    setYamlText(r.yaml);
    submit.reset();
  };
  const onDraft = () => draft.mutate(brd, { onSuccess: show });
  const onGuided = (answers) => guided.mutate(answers, { onSuccess: show });
  const WAYS = [
    { id: "guided", label: "Answer questions", icon: ListChecks, note: "no model needed" },
    {
      id: "brd",
      label: "Describe it (BRD)",
      icon: Sparkles,
      note: modes.data?.brd_model ? "a model drafts it" : "no model connected",
    },
    { id: "template", label: "Start from a template", icon: LayoutTemplate, note: "edit it after" },
  ];

  return (
    <div>
      <PageHeader
        title="Authoring"
        subtitle="Build a capability in four short steps, from a BRD, or from a template. The platform checks it; another owner approves it."
      />
      <div className="grid gap-4 xl:grid-cols-2">
        <Card
          title={
            <span className="flex items-center gap-2">
              <FileText size={14} /> How do you want to start?
            </span>
          }
        >
          <div
            role="tablist"
            aria-label="How to author"
            className="mb-3 grid grid-cols-3 gap-1 rounded-lg border border-surface-200 p-1"
          >
            {WAYS.map((w) => (
              <button
                key={w.id}
                role="tab"
                aria-selected={way === w.id}
                onClick={() => setWay(w.id)}
                className={clsx(
                  "rounded-md px-2 py-1.5 text-left text-xs",
                  way === w.id ? "bg-primary-50 text-primary-800" : "text-surface-600 hover:bg-surface-50",
                )}
              >
                <span className="flex items-center gap-1 font-medium">
                  <w.icon size={12} /> {w.label}
                </span>
                <span className="text-[10px] text-surface-500">{w.note}</span>
              </button>
            ))}
          </div>
          {way === "guided" && (
            <>
              <GuidedForm onBuild={onGuided} pending={guided.isPending} />
              {guided.error && (
                <div className="mt-3">
                  <ErrorState error={guided.error} />
                </div>
              )}
            </>
          )}
          {way === "brd" && (
            <>
              {modes.data?.brd_note && (
                <p className="mb-2 rounded-lg bg-orange-50 px-3 py-2 text-xs text-orange-900">{modes.data.brd_note}</p>
              )}
              <label className="block text-xs font-medium text-surface-600">
                BRD
                <textarea
                  value={brd}
                  onChange={(e) => setBrd(e.target.value)}
                  rows={14}
                  placeholder="What is reviewed, from which systems, how it is grouped, what is material, who signs off, where approved results go…"
                  className="mt-1 block w-full rounded-lg border border-surface-300 px-3 py-2 text-sm font-normal focus:border-primary-400 focus:outline-none"
                />
              </label>
              <button
                onClick={onDraft}
                disabled={draft.isPending || !brd.trim()}
                className="mt-3 inline-flex items-center gap-2 rounded-lg bg-brand-accent px-4 py-2 text-sm font-medium text-brand-accent-fg hover:bg-brand-accent-strong disabled:opacity-50"
              >
                <Sparkles size={14} /> {draft.isPending ? "Drafting…" : "Draft capability"}
              </button>
              {draft.error && (
                <div className="mt-3">
                  <ErrorState error={draft.error} />
                </div>
              )}
            </>
          )}
          {way === "template" && (
            <label className="block text-xs font-medium text-surface-600">
              Start from a template
              <select
                aria-label="Template"
                defaultValue=""
                onChange={(e) => applyTemplate(e.target.value)}
                className="mt-1 block w-full rounded-lg border border-surface-300 px-2 py-1.5 text-sm font-normal"
              >
                <option value="" disabled>
                  Choose a template…
                </option>
                {(templates.data ?? []).map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} — {t.description}
                  </option>
                ))}
              </select>
            </label>
          )}
        </Card>

        <Card
          title="Draft manifest"
          aside={result?.author && <span className="text-xs text-surface-500">drafted by {result.author}</span>}
        >
          {!result && <Empty>Your draft appears here, checked by the platform, ready to edit and submit.</Empty>}
          {result && (
            <div className="space-y-3">
              {result.manifest && (
                <WorkflowStepper steps={result.manifest.steps} pauseBefore={result.manifest.pause_before} />
              )}
              {result.problems.length > 0 ? (
                <div
                  role="alert"
                  className="rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm text-orange-800"
                >
                  <p className="font-medium">Fix before submitting:</p>
                  <ul className="mt-1 list-disc pl-5">
                    {result.problems.map((p) => (
                      <li key={p}>{p}</li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="flex items-center gap-1.5 text-sm text-green-700">
                  <CheckCircle2 size={14} /> Passes every platform check.
                </p>
              )}
              {result.assumptions.length > 0 && (
                <div className="rounded-lg bg-surface-50 p-3 text-xs text-surface-600">
                  <p className="font-semibold">Assumptions to confirm</p>
                  <ul className="mt-1 list-disc pl-4">
                    {result.assumptions.map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                </div>
              )}
              <label className="block text-xs font-medium text-surface-600">
                Manifest (YAML) — edit freely; it is judged again on submit
                <textarea
                  value={yamlText}
                  onChange={(e) => setYamlText(e.target.value)}
                  rows={16}
                  spellCheck={false}
                  className="mt-1 block w-full rounded-lg border border-surface-300 bg-code-bg px-3 py-2 font-mono text-xs text-code-fg focus:outline-none"
                />
              </label>
              <div className="flex flex-wrap items-end gap-2">
                <label className="flex-1 text-xs font-medium text-surface-600">
                  Note for the approver
                  <input
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    className="mt-1 block w-full rounded-lg border border-surface-300 px-3 py-1.5 text-sm font-normal"
                  />
                </label>
                <button
                  onClick={() => submit.mutate({ yaml: yamlText, note })}
                  disabled={submit.isPending || !yamlText.trim()}
                  className="inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50"
                >
                  <Upload size={14} /> Submit for approval
                </button>
              </div>
              {submit.error && <ErrorState error={submit.error} />}
              {submit.data && (
                <p className="text-sm text-green-700">
                  Submitted {submit.data.capability_id} v{submit.data.version}. It goes live when another owner approves
                  it.
                </p>
              )}
            </div>
          )}
        </Card>
      </div>
      <PendingDrafts />
      <PromoteIn />
    </div>
  );
}

/** A version exported from another environment arrives here as a draft. */
function PromoteIn() {
  const imp = useImportBundle();
  const [text, setText] = useState("");
  const [bad, setBad] = useState(null);
  return (
    <Fold className="mt-4" title="Promote from another environment" summary="paste a version exported elsewhere">
      <p className="mb-2 text-xs text-surface-500">
        Paste a version exported from another environment (its Versions tab, download icon). It arrives as a draft and
        goes live only when an owner here approves it. Its checksum (and signature, when this deployment has a promotion
        key) is verified.
      </p>
      <textarea
        aria-label="Version bundle"
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={5}
        spellCheck={false}
        className="block w-full rounded-lg border border-surface-300 bg-code-bg px-3 py-2 font-mono text-xs text-code-fg focus:outline-none"
      />
      <button
        disabled={!text.trim() || imp.isPending}
        onClick={() => {
          setBad(null);
          try {
            imp.mutate(JSON.parse(text));
          } catch {
            setBad("That is not a bundle (JSON expected).");
          }
        }}
        className="mt-2 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50"
      >
        Import as draft
      </button>
      {bad && <p className="mt-2 text-xs text-red-700">{bad}</p>}
      {imp.error && (
        <div className="mt-2">
          <ErrorState error={imp.error} />
        </div>
      )}
      {imp.data && (
        <p className="mt-2 text-sm text-green-700">
          Drafted {imp.data.capability_id} v{imp.data.version} — {imp.data.note}
        </p>
      )}
    </Fold>
  );
}

function PendingDrafts() {
  const drafts = useDrafts();
  const approve = useApproveVersion();
  if (drafts.data?.length === 0 && !approve.data) return null; // nothing waiting: no empty card
  return (
    <Card title="Drafts awaiting approval" className="mt-4">
      {drafts.isLoading && <Loading what="drafts" />}
      {drafts.error && <ErrorState error={drafts.error} />}
      {drafts.data?.length === 0 && <Empty>No drafts waiting.</Empty>}
      <ul className="divide-y divide-surface-100">
        {drafts.data?.map((d) => (
          <li key={`${d.capability_id}-${d.version}`} className="flex flex-wrap items-center gap-3 py-2.5 text-sm">
            <span className="font-medium">{d.name}</span>
            <span className="font-mono text-xs text-surface-400">
              {d.capability_id} v{d.version}
            </span>
            {d.new && (
              <span className="rounded bg-accent-50 px-1.5 py-0.5 text-[10px] font-medium text-accent-700">
                new capability
              </span>
            )}
            <span className="text-xs text-surface-500">
              by {d.drafted_by} {formatTime(d.drafted_at)}
              {d.note && ` — ${d.note}`}
            </span>
            <span className="ml-auto">
              {d.can_approve ? (
                <button
                  onClick={() => approve.mutate({ capabilityId: d.capability_id, version: d.version })}
                  disabled={approve.isPending}
                  className="rounded-lg bg-brand-accent px-3 py-1 text-xs font-medium text-brand-accent-fg hover:bg-brand-accent-strong disabled:opacity-50"
                >
                  Approve
                </button>
              ) : (
                <span className="text-xs text-surface-400">needs another owner</span>
              )}
            </span>
          </li>
        ))}
      </ul>
      {approve.error && <ErrorState error={approve.error} />}
      {approve.data && (
        <p className="mt-2 text-sm text-green-700">
          Approved — now live in{" "}
          <Link className="underline" to="/capabilities">
            Capabilities
          </Link>
          .
        </p>
      )}
    </Card>
  );
}
