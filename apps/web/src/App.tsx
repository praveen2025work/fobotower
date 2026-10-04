import { useQueryClient } from "@tanstack/react-query";
import { Suspense, lazy, useState, type ReactNode } from "react";
import { Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import { Loading } from "./components/ui";
import Overview from "./pages/Overview";

// Every page but the home page loads when first opened, so the first download stays small.
const Audit = lazy(() => import("./pages/Audit"));
const Authoring = lazy(() => import("./pages/Authoring"));
const Capabilities = lazy(() => import("./pages/Capabilities"));
const CapabilityDetail = lazy(() => import("./pages/CapabilityDetail"));
const CaseWorkspace = lazy(() => import("./pages/CaseWorkspace"));
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
      <Route element={<Layout onUserChange={onUserChange} />}>
        <Route path="/" element={<Overview />} />
        <Route path="/inbox" element={page(<InboxPage />)} />
        <Route path="/capabilities" element={page(<Capabilities />)} />
        <Route path="/capabilities/:id" element={page(<CapabilityDetail />)} />
        <Route path="/capabilities/:id/groups/:group" element={page(<GroupDetail />)} />
        <Route path="/cases/:caseId" element={page(<CaseWorkspace />)} />
        <Route path="/authoring" element={page(<Authoring />)} />
        <Route path="/operations" element={page(<Operations />)} />
        <Route path="/audit" element={page(<Audit />)} />
        <Route path="/connectors" element={page(<Connectors />)} />
      </Route>
    </Routes>
  );
}

export default App;
