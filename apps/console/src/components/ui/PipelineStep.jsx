export function PipelineStep({
  step,
  status,
  isLast,
  isCurrent,
  target,
  onGo,
}) {
  const Icon = step.icon;
  let cls =
    'flex items-center justify-center rounded-full border-2 w-8 h-8 shrink-0 transition-colors';
  if (status === 'done') cls += ' bg-emerald-500 border-emerald-500 text-white';
  else if (status === 'active') cls += ' border-2 bg-white';
  else if (status === 'blocked')
    cls += ' bg-rose-500 border-rose-500 text-white';
  else cls += ' bg-white border-slate-200 text-slate-400';
  return (
    <div className="flex items-center flex-1 min-w-0">
      <button
        onClick={onGo}
        className="flex flex-col items-center rounded-lg py-0.5 hover:opacity-80"
        style={{
          minWidth: '5rem',
          maxWidth: '7rem',
          flex: '1 1 5rem',
        }}
        title={`${step.label}: go to ${target}`}
        aria-label={`${step.label}${isCurrent ? ' (current step)' : ''}: go to ${target}`}
        aria-current={isCurrent ? 'step' : undefined}
      >
        <div
          className={cls}
          style={
            status === 'active'
              ? {
                  borderColor: 'var(--barcl-eagle)',
                  color: 'var(--barcl-eagle)',
                  boxShadow:
                    '0 0 0 4px color-mix(in srgb, var(--barcl-eagle) 12%, transparent)',
                }
              : {}
          }
        >
          <Icon size={14} strokeWidth={2.25} />
        </div>
        <div className="mt-1.5 text-center leading-snug w-full px-0.5">
          <div
            className="text-[9px] font-semibold leading-tight"
            style={{
              color: 'var(--text-secondary)',
              whiteSpace: 'normal',
              wordBreak: 'break-word',
            }}
          >
            {step.label}
          </div>
          <div
            className="text-[8px] mt-0.5 leading-tight"
            style={{
              color: 'var(--text-muted)',
            }}
          >
            {step.sub}
          </div>
        </div>
      </button>
      {!isLast && (
        <div
          className="h-0.5 shrink-0 -mt-5"
          style={{
            width: '20px',
            background:
              status === 'done'
                ? 'linear-gradient(90deg, var(--clr-green), rgba(26,122,69,0.4))'
                : 'var(--border-subtle)',
          }}
        />
      )}
    </div>
  );
}
