import { AGENT_COLORS, AGENT_ICONS, AGENT_LABELS, STATIC_AGENTS } from '@/lib/constants';
import { cn } from '@/lib/utils';

export function AgentRoster() {
  return (
    <div className="space-y-2">
      {STATIC_AGENTS.map(agent => (
        <div
          key={agent.name}
          className="flex items-start gap-2.5 p-2.5 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800"
        >
          <span
            className={cn(
              'flex-shrink-0 inline-flex items-center justify-center w-7 h-7 rounded-full text-sm',
              AGENT_COLORS[agent.name] ?? 'bg-slate-100 text-slate-700',
            )}
          >
            {AGENT_ICONS[agent.name] ?? '🤖'}
          </span>
          <div className="min-w-0">
            <p className="text-xs font-semibold text-slate-700 dark:text-slate-300 leading-tight">
              {AGENT_LABELS[agent.name] ?? agent.name}
            </p>
            <p className="text-[10px] text-slate-500 dark:text-slate-500 leading-snug mt-0.5">
              {agent.description}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
