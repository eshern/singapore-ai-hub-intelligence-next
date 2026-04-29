import { AGENT_COLORS, AGENT_ICONS, AGENT_LABELS } from '@/lib/constants';
import { cn } from '@/lib/utils';

interface AgentBadgeRowProps {
  agents: string[];
  className?: string;
}

export function AgentBadgeRow({ agents, className }: AgentBadgeRowProps) {
  if (!agents.length) return null;

  return (
    <div className={cn('flex flex-wrap gap-1.5 mt-2', className)}>
      {agents.map(agent => (
        <span
          key={agent}
          className={cn(
            'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium',
            AGENT_COLORS[agent] ?? 'bg-slate-100 text-slate-700',
          )}
        >
          <span role="img" aria-label={AGENT_LABELS[agent] ?? agent}>
            {AGENT_ICONS[agent] ?? '🤖'}
          </span>
          <span>{AGENT_LABELS[agent] ?? agent}</span>
        </span>
      ))}
    </div>
  );
}
