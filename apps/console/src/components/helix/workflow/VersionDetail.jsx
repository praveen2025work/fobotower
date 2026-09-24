import { useEffect, useState } from 'react';
import { approveVersion, downloadYaml, fetchRebased, fetchVersion, rejectVersion } from '../data/workflowApi';
import { StatusChip } from './VersionList';
import { Check, WorkflowDialog } from './WorkflowDialog';
import { describeChange, when } from './workflowModel';

const pillButton = 'text-[12px] font-semibold px-3 py-1.5 rounded-full disabled:opacity-40';

function ApproveDialog({ version, onCancel, onDone }) {
  // One key per confirmation: a retried click can never approve twice.
  const [key] = useState(() => crypto.randomUUID());
  const [ackDiff, setAckDiff] = useState(false);
  const [ackLive, setAckLive] = useState(false);
  const [state, setState] = useState({ busy: false, error: null });
  const confirm = async () => {
    setState({ busy: true, error: null });
    try {
      await approveVersion(version.number, key);
      onDone();
    } catch (e) {
      setState({ busy: false, error: e.message });
    }
  };
  return (
    <WorkflowDialog
      title={`Approve v${version.number}`}
      confirmLabel="Approve and activate"
      ready={ackDiff && ackLive}
      {...state}
      onCancel={onCancel}
      onConfirm={confirm}
    >
      <Check checked={ackDiff} onChange={setAckDiff}>
        I have reviewed every change against v{version.active_number}.
      </Check>
      <Check checked={ackLive} onChange={setAckLive}>
        New investigations run on v{version.number} from now on. Runs already started keep their version.
      </Check>
    </WorkflowDialog>
  );
}

function RejectDialog({ version, own, onCancel, onDone }) {
  const [reason, setReason] = useState('');
  const [state, setState] = useState({ busy: false, error: null });
  const confirm = async () => {
    setState({ busy: true, error: null });
    try {
      await rejectVersion(version.number, reason.trim());
      onDone();
    } catch (e) {
      setState({ busy: false, error: e.message });
    }
  };
  return (
    <WorkflowDialog
      title={`${own ? 'Withdraw' : 'Reject'} v${version.number}`}
      confirmLabel="Reject draft"
      ready={reason.trim().length > 0}
      {...state}
      onCancel={onCancel}
      onConfirm={confirm}
    >
      <label className="text-[12px] font-semibold flex flex-col gap-1" style={{ color: 'var(--text-primary)' }}>
        Reason
        <textarea
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="text-[12px] rounded-lg px-2 py-1.5 font-normal"
          style={{ background: 'var(--bg-muted)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
        />
      </label>
    </WorkflowDialog>
  );
}

function Changes({ v }) {
  if (v.number === v.active_number) {
    return (
      <p className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
        This is the active version.
      </p>
    );
  }
  return (
    <div>
      <h4 className="text-[11px] font-bold uppercase tracking-wide mb-1" style={{ color: 'var(--text-muted)' }}>
        Compared with active v{v.active_number}
      </h4>
      {v.diff.length ? (
        <ul className="list-disc pl-4 text-[12.5px]" style={{ color: 'var(--text-primary)' }}>
          {v.diff.map((c) => (
            <li key={`${c.path}-${c.kind}`}>{describeChange(c)}</li>
          ))}
        </ul>
      ) : (
        <p className="text-[12px]" style={{ color: 'var(--text-secondary)' }}>
          Identical to the active version.
        </p>
      )}
    </div>
  );
}

function Actions({ v, caller, onApprove, onReject, onRedraft, redraftError }) {
  const isPc = caller?.roles?.includes('PC');
  const own = v.drafted_by === caller?.id;
  const stale = v.based_on !== v.active_number;
  return (
    <div className="flex flex-col gap-2">
      {stale ? (
        <div
          className="rounded-lg px-3 py-2 text-[12px] flex flex-col gap-1.5"
          style={{ background: 'var(--clr-amber-bg)', color: 'var(--clr-amber)' }}
        >
          <span>v{v.active_number} went live after this was drafted.</span>
          <button
            type="button"
            onClick={onRedraft}
            disabled={!isPc}
            className={pillButton}
            style={{ border: '1px solid var(--clr-amber)' }}
          >
            Redraft on v{v.active_number}
          </button>
          {redraftError && <span role="alert">{redraftError}</span>}
        </div>
      ) : (
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            disabled={own || !isPc}
            onClick={onApprove}
            className={pillButton}
            style={{ background: 'var(--clr-green)', color: 'var(--text-on-brand)' }}
          >
            Approve
          </button>
          {own && (
            <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
              A second PC user must approve
            </span>
          )}
        </div>
      )}
      {isPc && (
        <button
          type="button"
          onClick={onReject}
          className={pillButton}
          style={{ border: '1px solid var(--border)', color: 'var(--text-secondary)' }}
        >
          {own ? 'Withdraw' : 'Reject'}
        </button>
      )}
    </div>
  );
}

export function VersionDetail({ number, caller, onChanged, onRedraft }) {
  const [state, setState] = useState({ status: 'loading' });
  const [dialog, setDialog] = useState(null);
  const [redraftError, setRedraftError] = useState(null);
  useEffect(() => {
    let live = true;
    // A new number means a new review: drop any dialog and error bound to
    // the version we were just looking at before the next one loads.
    setState({ status: 'loading' });
    setDialog(null);
    setRedraftError(null);
    fetchVersion(number)
      .then((v) => live && setState({ status: 'ready', v }))
      .catch((e) => live && setState({ status: 'error', error: e.message }));
    return () => {
      live = false;
    };
  }, [number]);

  if (state.status === 'loading') {
    return (
      <p className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
        Loading v{number}…
      </p>
    );
  }
  if (state.status === 'error') {
    return (
      <p role="alert" className="text-[12px]" style={{ color: 'var(--clr-red)' }}>
        {state.error}
      </p>
    );
  }
  const { v } = state;
  const redraft = async () => {
    setRedraftError(null);
    try {
      const body = await fetchRebased(v.number);
      onRedraft({ config: body.config, basedOn: body.based_on, conflicts: body.conflicts });
    } catch (e) {
      setRedraftError(e.message);
    }
  };
  const done = () => {
    setDialog(null);
    onChanged();
  };
  const decided = v.decided_by && `${v.status === 'rejected' ? 'rejected' : 'approved'} by ${v.decided_by} · ${when(v.decided_at)}`;
  return (
    <section aria-label={`Version ${v.number}`} className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <h3 className="text-[15px] font-bold" style={{ color: 'var(--text-primary)' }}>
          v{v.number}
        </h3>
        <StatusChip status={v.status} />
        <button
          type="button"
          onClick={() => downloadYaml(v.number)}
          className="ml-auto text-[11px] underline"
          style={{ color: 'var(--text-secondary)' }}
        >
          Download YAML
        </button>
      </div>
      <p className="text-[11.5px]" style={{ color: 'var(--text-muted)' }}>
        Drafted by {v.drafted_by} · {when(v.drafted_at)}
        {decided && ` · ${decided}`}
      </p>
      <blockquote className="text-[12.5px] pl-2" style={{ borderLeft: '2px solid var(--border)', color: 'var(--text-primary)' }}>
        {v.note}
      </blockquote>
      {v.reject_reason && (
        <p className="text-[12px]" style={{ color: 'var(--clr-red)' }}>
          Rejected: {v.reject_reason}
        </p>
      )}
      <Changes v={v} />
      {v.status === 'draft' && (
        <Actions
          v={v}
          caller={caller}
          onApprove={() => setDialog('approve')}
          onReject={() => setDialog('reject')}
          onRedraft={redraft}
          redraftError={redraftError}
        />
      )}
      {dialog === 'approve' && <ApproveDialog version={v} onCancel={() => setDialog(null)} onDone={done} />}
      {dialog === 'reject' && (
        <RejectDialog version={v} own={v.drafted_by === caller?.id} onCancel={() => setDialog(null)} onDone={done} />
      )}
    </section>
  );
}
