// The skill editor: change only the model's instructions and submit them as a
// draft version; another owner approves it. History is the versions tab.

import { useState } from "react";

import { useDraftInstructions } from "../../api/helix";
import { ErrorState } from "../ui";

export default function InstructionsEditor({ capabilityId, current, teamGroup }: {
  capabilityId: string;
  current: string;
  teamGroup?: string | null;
}) {
  const draft = useDraftInstructions(capabilityId);
  const [skill, setSkill] = useState(current);
  const [note, setNote] = useState("");
  return (
    <div className="space-y-2">
      <p className="text-xs text-surface-500">
        What the model is told for {teamGroup ? `the ${teamGroup} group` : "this capability"}. Saving drafts a new
        version; it takes effect when another owner approves it.
      </p>
      <label className="block text-xs font-medium text-surface-600">
        Instructions
        <textarea value={skill} onChange={(e) => setSkill(e.target.value)} rows={12}
          className="mt-1 block w-full rounded-lg border border-surface-300 bg-code-bg px-3 py-2 font-mono text-xs text-code-fg focus:outline-none" />
      </label>
      <label className="block text-xs font-medium text-surface-600">
        Why
        <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="What changes and why"
          className="mt-1 block w-full rounded-lg border border-surface-300 px-3 py-1.5 text-sm font-normal" />
      </label>
      <button
        disabled={draft.isPending || !skill.trim() || skill === current}
        onClick={() => draft.mutate({ skill, note, team_group: teamGroup ?? null })}
        className="rounded-lg bg-brand px-4 py-2 text-sm font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50"
      >
        Submit instructions for approval
      </button>
      {draft.data && <p className="text-xs text-green-700">Drafted version {draft.data.version} — waiting for another owner.</p>}
      {draft.error && <ErrorState error={draft.error} />}
    </div>
  );
}
