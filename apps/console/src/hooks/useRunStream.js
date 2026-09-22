'use client';

import { useEffect } from 'react';

import { WebSocketClient } from '@/lib/WebSocketClient';
import { useFoboSessionStore } from '@/store/foboSessionStore';

export function useRunStream(sessionId) {
  const setProgress = useFoboSessionStore((s) => s.setProgress);

  useEffect(() => {
    if (!sessionId) return undefined;

    const client = new WebSocketClient('/api/ws/runs', {
      onEvent: (event) => {
        if (event.type === 'run.progress') setProgress(event);
      },
    }).connect();

    client.send({ session_id: sessionId });
    return () => client.close();
  }, [sessionId, setProgress]);
}
