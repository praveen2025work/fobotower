// Generated from apps/web/src/components/TaskLink.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see office/README.md.
// A link to a task. In a snapshot that holds a task only as a row of a summary (a day of
// thousands of books), it is text instead of a link that would open nothing.

import { Link } from "../office/router";

import { recorded } from "../scope";

export default function TaskLink({ id, className, title, children }) {
  const to = `/tasks/${encodeURIComponent(id)}`;
  if (recorded(to))
    return (
      <Link to={to} className={className} title={title}>
        {children}
      </Link>
    );
  return (
    <span className={className} title="Open it in the live console: this snapshot holds a few tasks in full">
      {children}
    </span>
  );
}
