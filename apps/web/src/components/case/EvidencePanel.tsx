// Evidence attached to the case (readable by the capability's document tools
// and the model), and the case's evidence pack for an auditor.

import { useRef, useState } from "react";
import { FileArchive, Paperclip, Upload } from "lucide-react";

import { download } from "../../api/client";
import { useUploadEvidence, type CaseDetail } from "../../api/aof";
import { ErrorState, formatTime } from "../ui";

export default function EvidencePanel({ c, canUpload }: { c: CaseDetail; canUpload: boolean }) {
  const upload = useUploadEvidence(c.case_id);
  const input = useRef<HTMLInputElement | null>(null);
  const [note, setNote] = useState("");
  const files = c.evidence ?? [];

  return (
    <div className="rounded-lg border border-surface-200 bg-card p-3" aria-label="Evidence">
      <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-surface-500"><Paperclip size={12} /> Evidence</h2>
      <ul className="mt-2 space-y-1">
        {files.map((f) => (
          <li key={f.name}>
            <button
              onClick={() => void download(f.url.replace(/^\/api/, ""), f.name)}
              className="w-full rounded-md border border-surface-100 px-2 py-1 text-left text-xs hover:bg-surface-50"
              title={`sha256 ${f.sha256}`}
            >
              <span className="block truncate font-medium text-surface-800">{f.name.split("--").slice(1).join("--") || f.name}</span>
              <span className="text-[10px] text-surface-500">{f.uploaded_by} · {formatTime(f.uploaded_at)}{f.note ? ` · ${f.note}` : ""}</span>
            </button>
          </li>
        ))}
        {files.length === 0 && <li className="text-xs text-surface-400">None attached.</li>}
      </ul>
      {canUpload && (
        <div className="mt-2 space-y-1">
          <input aria-label="Evidence note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="What it shows (optional)"
            className="block w-full rounded-md border border-surface-300 px-2 py-1 text-xs" />
          <input
            ref={input}
            type="file"
            accept=".pdf,.xlsx,.xlsm"
            aria-label="Evidence file"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) upload.mutate({ file, note }, { onSuccess: () => setNote("") });
              e.target.value = "";
            }}
          />
          <button
            disabled={upload.isPending}
            onClick={() => input.current?.click()}
            className="inline-flex items-center gap-1.5 rounded-md border border-surface-300 px-2 py-1 text-xs font-medium text-surface-700 hover:bg-surface-50 disabled:opacity-50"
          >
            <Upload size={12} /> Attach PDF or workbook
          </button>
          {upload.error && <ErrorState error={upload.error} />}
        </div>
      )}
      <button
        onClick={() => void download(`/cases/${encodeURIComponent(c.case_id)}/evidence-pack`, `evidence-pack-${c.case_id}.pdf`)}
        className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-primary-700 hover:underline"
      >
        <FileArchive size={12} /> Evidence pack (PDF)
      </button>
    </div>
  );
}
