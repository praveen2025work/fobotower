// Generated from apps/web/src/components/ErrorBoundary.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see office/README.md.
import { Component } from "react";
import { AlertTriangle } from "lucide-react";

/**
 * Route-level error boundary (QA fix): a crashing page must degrade to a readable
 * panel instead of unmounting the whole app to a white screen (/governance did
 * exactly that when an API shape drifted). Wraps the routed Outlet in Layout.
 */
export default class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Surfaced in dev tooling; the UI shows the friendly panel below.
    console.error("Route crashed:", error, info.componentStack);
  }

  componentDidUpdate(prevProps) {
    // Navigating to another route gets a fresh chance to render.
    if (this.state.error && prevProps.children !== this.props.children) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error) {
      return (
        <div data-testid="route-error" className="m-6 rounded-xl border border-red-200 bg-red-50 p-6">
          <div className="flex items-center gap-2 text-red-700">
            <AlertTriangle size={18} />
            <span className="font-semibold">This page hit an error</span>
          </div>
          <p className="mt-2 text-sm text-red-600">
            {this.state.error.message || "Unexpected rendering error."} The rest of the app keeps working — use the
            navigation to continue.
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}
