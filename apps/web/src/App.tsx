import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import Audit from "./pages/Audit";
import Capabilities from "./pages/Capabilities";
import CapabilityDetail from "./pages/CapabilityDetail";
import CaseWorkspace from "./pages/CaseWorkspace";
import Connectors from "./pages/Connectors";
import InboxPage from "./pages/Inbox";
import Overview from "./pages/Overview";

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
        <Route path="/inbox" element={<InboxPage />} />
        <Route path="/capabilities" element={<Capabilities />} />
        <Route path="/capabilities/:id" element={<CapabilityDetail />} />
        <Route path="/cases/:caseId" element={<CaseWorkspace />} />
        <Route path="/audit" element={<Audit />} />
        <Route path="/connectors" element={<Connectors />} />
      </Route>
    </Routes>
  );
}

export default App;
