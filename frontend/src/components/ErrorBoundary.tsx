import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertOctagon, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Terminal Caught Render Error:', error, errorInfo);
    this.setState({ error, errorInfo });
  }

  private handleReload = () => {
    window.location.reload();
  };

  private handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-[#0a0d14] text-gray-200 flex items-center justify-center p-6 font-sans">
          <div className="max-w-xl w-full bg-[#111620] border border-red-500/40 rounded-2xl p-6 sm:p-8 shadow-2xl flex flex-col gap-5">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400">
                <AlertOctagon className="h-7 w-7" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-white tracking-wide">
                  {this.props.fallbackTitle || 'Kalshi Terminal Runtime Shield'}
                </h2>
                <p className="text-xs text-red-400/90 font-mono">
                  UI Component Error Intercepted — Core Execution Bot Protected
                </p>
              </div>
            </div>

            <div className="bg-[#0a0d14] border border-[#21262d] rounded-xl p-4 font-mono text-xs text-gray-300 overflow-x-auto max-h-48">
              <div className="text-red-400 font-bold mb-1">
                {this.state.error?.name}: {this.state.error?.message}
              </div>
              {this.state.errorInfo?.componentStack && (
                <pre className="text-[10px] text-gray-500 whitespace-pre-wrap">
                  {this.state.errorInfo.componentStack.slice(0, 500)}
                </pre>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={this.handleReset}
                className="px-4 py-2 bg-[#21262d] hover:bg-[#30363d] text-gray-200 rounded-xl text-xs font-bold transition-all"
              >
                Attempt In-Place Recovery
              </button>
              <button
                type="button"
                onClick={this.handleReload}
                className="flex items-center gap-2 px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-bold transition-all shadow-lg shadow-emerald-600/20"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span>Reload Terminal</span>
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
