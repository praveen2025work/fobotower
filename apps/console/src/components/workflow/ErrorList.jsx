/** An API failure: the server's message, then every problem it listed. */
export function ErrorList({ error }) {
  if (!error) return null;
  return (
    <div
      role="alert"
      className="rounded-lg px-3 py-2 text-[12px]"
      style={{ background: 'var(--clr-red-bg)', color: 'var(--clr-red)' }}
    >
      <div className="font-semibold">{error.message}</div>
      {error.errors?.length > 0 && (
        <ul className="list-disc pl-4 mt-1">
          {error.errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
