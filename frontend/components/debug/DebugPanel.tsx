'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Bug } from 'lucide-react';
import { AGENT_LABELS } from '@/lib/constants';
import { cn } from '@/lib/utils';

interface DebugPanelProps {
  routingReason?: string;
  agentOutputs?: Record<string, string>;
  debugLog?: string;
  latencyMs?: number;
}

export function DebugPanel({
  routingReason,
  agentOutputs,
  debugLog,
  latencyMs,
}: DebugPanelProps) {
  const [open, setOpen] = useState(false);
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);

  const hasContent =
    routingReason ||
    (agentOutputs && Object.keys(agentOutputs).length > 0) ||
    debugLog;

  if (!hasContent) return null;

  return (
    <div className="mt-3 border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden text-xs">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-3 py-2 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700/80 text-slate-500 dark:text-slate-400 transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <Bug className="w-3.5 h-3.5" />
          Orchestration details
          {latencyMs !== undefined && (
            <span className="ml-1.5 text-slate-400 dark:text-slate-500 font-mono">
              {latencyMs.toLocaleString()}ms
            </span>
          )}
        </span>
        {open ? (
          <ChevronDown className="w-3.5 h-3.5" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5" />
        )}
      </button>

      {open && (
        <div className="p-3 bg-white dark:bg-slate-900 space-y-3 divide-y divide-slate-100 dark:divide-slate-800">
          {routingReason && (
            <div className="pt-0">
              <p className="font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-widest text-[10px] mb-1">
                Routing Reason
              </p>
              <p className="text-slate-700 dark:text-slate-300">{routingReason}</p>
            </div>
          )}

          {agentOutputs &&
            Object.entries(agentOutputs).map(([agent, output]) => (
              <div key={agent} className="pt-2">
                <button
                  onClick={() =>
                    setExpandedAgent(expandedAgent === agent ? null : agent)
                  }
                  className="w-full flex items-center justify-between text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 transition-colors"
                >
                  <span className="font-medium">
                    {AGENT_LABELS[agent] ?? agent} raw output
                  </span>
                  {expandedAgent === agent ? (
                    <ChevronDown className="w-3 h-3" />
                  ) : (
                    <ChevronRight className="w-3 h-3" />
                  )}
                </button>
                {expandedAgent === agent && (
                  <div className="mt-2 p-2.5 rounded bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-mono text-[11px] leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
                    {output}
                  </div>
                )}
              </div>
            ))}

          {debugLog && (
            <div className="pt-2">
              <p className="font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-widest text-[10px] mb-1">
                Debug Log
              </p>
              <pre className="p-2.5 rounded bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-mono text-[11px] leading-relaxed whitespace-pre-wrap">
                {debugLog}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
