import { useCallback, useEffect, useState } from 'react';

/** Load `fn()` when `deps` change; returns {data, error, loading, reload, setData}. */
export function useAsync(fn, deps) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const [tick, setTick] = useState(0);
  // `deps` decide when to reload, the same contract as useEffect's array.
  const run = useCallback(fn, deps);

  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    run()
      .then((data) => live && setState({ data, error: null, loading: false }))
      .catch((error) => live && setState({ data: null, error, loading: false }));
    return () => {
      live = false;
    };
  }, [run, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  const setData = useCallback((data) => setState({ data, error: null, loading: false }), []);
  return { ...state, reload, setData };
}
