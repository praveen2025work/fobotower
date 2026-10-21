import { useQueryClient } from "@tanstack/react-query";
import { Suspense, lazy, useEffect, useState, type ReactNode } from "react";
import { Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import { Loading } from "./components/ui";
import Overview from "./pages/Overview";

// Every page but the home page loads when first opened, so the first download stays small.
const Audit = lazy(() => import("./pages/Audit"));
const Authoring = lazy(() => import("./pages/Authoring"));
const Agents = lazy(() => import("./pages/Agents"));
const AgentDetail = lazy(() => import("./pages/AgentDetail"));
const TaskWorkspace = lazy(() => import("./pages/TaskWorkspace"));
const Connectors = lazy(() => import("./pages/Connectors"));
const GroupDetail = lazy(() => import("./pages/GroupDetail"));
const InboxPage = lazy(() => import("./pages/Inbox"));
const Operations = lazy(() => import("./pages/Operations"));

const page = (el: ReactNode) => <Suspense fallback={<Loading what="page" />}>{el}</Suspense>;

function App(): JSX.Element {
  const qc = useQueryClient();
  // Switching user (development) must drop every cached answer: what a user
  // may see is decided per request by the server.
  const [generation, setGeneration] = useState(0);
  const onUserChange = () => {
    qc.clear();
    setGeneration((g) => g + 1);
  };
  return (
    <Routes key={generation}>
      {/* The pitch page is a static file (public/pitch/index.html). A server that sends
          unknown paths to the console would show a blank page for /pitch: go to the file. */}
      <Route path="/pitch/*" element={<StaticPage href="/pitch/index.html" />} />
      <Route element={<Layout onUserChange={onUserChange} />}>
        <Route path="/" element={<Overview />} />
        <Route path="/inbox" element={page(<InboxPage />)} />
        <Route path="/agents" element={page(<Agents />)} />
        <Route path="/agents/:id" element={page(<AgentDetail />)} />
        <Route path="/agents/:id/groups/:group" element={page(<GroupDetail />)} />
        <Route path="/tasks/:taskId" element={page(<TaskWorkspace />)} />
        <Route path="/authoring" element={page(<Authoring />)} />
        <Route path="/operations" element={page(<Operations />)} />
        <Route path="/audit" element={page(<Audit />)} />
        <Route path="/connectors" element={page(<Connectors />)} />
      </Route>
    </Routes>
  );
}

/** Leaves the console for a static page served beside it. */
function StaticPage({ href }: { href: string }) {
  useEffect(() => {
    window.location.replace(href);
  }, [href]);
  return null;
}

export default App;
