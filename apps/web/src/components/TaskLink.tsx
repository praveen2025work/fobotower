// A link to a task. In a snapshot that holds a task only as a row of a summary (a day of
// thousands of books), it is text instead of a link that would open nothing.
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { recorded } from "../scope";

export default function TaskLink({ id, className, title, children }: { id: string; className?: string; title?: string; children: ReactNode }) {
  const to = `/cases/${encodeURIComponent(id)}`;
  if (recorded(to)) return <Link to={to} className={className} title={title}>{children}</Link>;
  return <span className={className} title="Open it in the live console: this snapshot holds a few tasks in full">{children}</span>;
}
