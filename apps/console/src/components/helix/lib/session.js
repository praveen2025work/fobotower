import { askSession } from '../data/helixApi';

/** Agent One answers from the orchestrator: deterministic intents first, the
 *  reasoning service for anything else. Nothing is generated in the browser. */
export const AgentOneClient = {
  send: ({ rec, message }) => askSession(rec.id, message),
};

/** The session as the API last served it: the analysis turn, then every
 *  stored question, answer and decision note. */
export const initialSession = (rec) => rec.session || [];
