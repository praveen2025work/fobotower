import { useState } from 'react';
import { uploadYaml } from '../data/workflowApi';
import { Drawer } from '../ui/Drawer';
import { ErrorList } from './ErrorList';

const fieldStyle = { background: 'var(--bg-muted)', border: '1px solid var(--border)', color: 'var(--text-primary)' };

export function YamlUpload({ onUploaded, onClose }) {
  const [text, setText] = useState('');
  const [note, setNote] = useState('');
  const [state, setState] = useState({ busy: false, error: null });
  const pick = async (e) => {
    const file = e.target.files?.[0];
    if (file) setText(await file.text());
  };
  const submit = async () => {
    setState({ busy: true, error: null });
    try {
      onUploaded(await uploadYaml({ yaml: text, note: note.trim() }));
    } catch (e) {
      setState({ busy: false, error: e });
    }
  };
  const ready = text.trim() && note.trim() && !state.busy;
  return (
    <Drawer title="Upload YAML" subtitle="It becomes a draft. A second Product Control user must approve it." width={560} onClose={onClose}>
      <div className="flex flex-col gap-3 text-[12px]" style={{ color: 'var(--text-primary)' }}>
        <label className="flex flex-col gap-1 font-semibold">
          YAML file
          <input type="file" accept=".yaml,.yml,text/yaml" onChange={pick} className="font-normal" />
        </label>
        <label className="flex flex-col gap-1 font-semibold">
          Or paste it
          <textarea
            aria-label="YAML text"
            rows={14}
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="rounded-lg px-2 py-1.5 font-mono text-[11.5px]"
            style={fieldStyle}
          />
        </label>
        <label className="flex flex-col gap-1 font-semibold">
          Change note
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={500}
            className="rounded-lg px-2 py-1.5 font-normal"
            style={fieldStyle}
          />
        </label>
        <ErrorList error={state.error} />
        <div>
          <button
            type="button"
            disabled={!ready}
            onClick={submit}
            className="text-[12px] font-semibold px-4 py-1.5 rounded-full disabled:opacity-40"
            style={{ background: 'var(--clr-blue)', color: 'var(--text-on-brand)' }}
          >
            {state.busy ? 'Uploading…' : 'Create draft'}
          </button>
        </div>
      </div>
    </Drawer>
  );
}
