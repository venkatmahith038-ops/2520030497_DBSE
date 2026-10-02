import React from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

/**
 * Catches render errors from the lazily loaded views.
 *
 * Without this, one thrown error in any panel unmounts the whole dashboard and
 * leaves a blank page with no way back. Resetting by key lets the user switch
 * tabs and recover without a full reload.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null, resetKey: props.resetKey };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  static getDerivedStateFromProps(props, state) {
    // A new resetKey means the user navigated somewhere else — clear the error
    // so the next view gets a chance to render. Deriving it here rather than in
    // componentDidUpdate avoids a second render pass.
    if (props.resetKey !== state.resetKey) {
      return { error: null, resetKey: props.resetKey };
    }
    return null;
  }

  componentDidCatch(error, info) {
    console.error("View crashed:", error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="error-boundary" role="alert">
        <AlertTriangle size={30} className="error-boundary-icon" />
        <h3>This section failed to load</h3>
        <p>
          Something went wrong while rendering this view. Your data is safe —
          switching to another tab or retrying usually clears it.
        </p>
        <p className="error-boundary-detail">{this.state.error?.message}</p>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => this.setState({ error: null })}
        >
          <RotateCcw size={15} />
          Retry
        </button>
      </div>
    );
  }
}
