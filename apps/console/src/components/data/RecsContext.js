'use client';

import { createContext, useContext } from 'react';

/** The recs as the API last served them. Components read them from here
 *  rather than importing data, so everything on screen is the server's. */
export const RecsContext = createContext([]);

export const useRecs = () => useContext(RecsContext);
