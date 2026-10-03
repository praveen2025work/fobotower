import { useState } from 'react';
import { humanize } from './workflowModel';

const inputStyle = {
  background: 'var(--bg-muted)',
  border: '1px solid var(--border)',
  color: 'var(--text-primary)',
};
const inputClass = 'w-full text-[12px] rounded-lg px-2 py-1.5 mt-0.5';

// A cleared field is sent as '' so the server says what is wrong with it.
const toNumber = (raw) => (raw === '' ? '' : Number(raw));
const splitList = (raw) =>
  raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

const range = (meta) => {
  const low = meta.min ?? (meta.exclusive_min !== undefined ? `>${meta.exclusive_min}` : null);
  if (low === null && meta.max === undefined) return '';
  return ` (${low ?? ''}–${meta.max ?? ''})`;
};

function ListInput({ id, value, onChange }) {
  const [text, setText] = useState((value || []).join(', '));
  return (
    <input
      id={id}
      type="text"
      className={inputClass}
      style={inputStyle}
      value={text}
      onChange={(e) => {
        setText(e.target.value);
        onChange(splitList(e.target.value));
      }}
    />
  );
}

function Field({ id, name, meta, value, onChange }) {
  let input;
  if (meta.type === 'enum') {
    input = (
      <select
        id={id}
        className={inputClass}
        style={inputStyle}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {meta.options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    );
  } else if (meta.type === 'string_list') {
    input = <ListInput id={id} value={value} onChange={onChange} />;
  } else {
    input = (
      <input
        id={id}
        type="number"
        className={inputClass}
        style={inputStyle}
        min={meta.min ?? meta.exclusive_min}
        max={meta.max}
        step={meta.type === 'integer' ? 1 : 'any'}
        value={value ?? ''}
        onChange={(e) => onChange(toNumber(e.target.value))}
      />
    );
  }
  return (
    <div className="mt-2">
      <label
        htmlFor={id}
        className="text-[12px] font-semibold"
        style={{ color: 'var(--text-primary)' }}
      >
        {humanize(name)}
      </label>
      {input}
      <div className="text-[10.5px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
        {meta.description}
        {range(meta)}
      </div>
    </div>
  );
}

export function SettingsForm({ config, schema, onChange }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {Object.entries(schema).map(([section, fields]) => (
        <fieldset
          key={section}
          className="rounded-xl px-3 pb-3"
          style={{ border: '1px solid var(--border)' }}
        >
          <legend
            className="text-[11px] font-bold px-1 uppercase tracking-wide"
            style={{ color: 'var(--text-muted)' }}
          >
            {section}
          </legend>
          {Object.entries(fields).map(([key, meta]) => (
            <Field
              key={key}
              id={`setting-${section}-${key}`}
              name={key}
              meta={meta}
              value={config.settings[section]?.[key]}
              onChange={(v) => onChange(section, key, v)}
            />
          ))}
        </fieldset>
      ))}
    </div>
  );
}
