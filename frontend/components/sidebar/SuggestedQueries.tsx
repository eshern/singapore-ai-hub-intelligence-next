'use client';

import { SUGGESTED_QUESTIONS } from '@/lib/constants';

interface SuggestedQueriesProps {
  onSelect: (question: string) => void;
}

const CATEGORIES = [
  { label: '🇸🇬 SG Policy', range: [0, 3] as const },
  { label: '💼 Investment', range: [3, 6] as const },
  { label: '🌏 Regional', range: [6, 12] as const },
  { label: '🔒 Cybersecurity', range: [12, 16] as const },
  { label: '🌐 Live Search', range: [16, 18] as const },
];

export function SuggestedQueries({ onSelect }: SuggestedQueriesProps) {
  return (
    <div className="space-y-4">
      {CATEGORIES.map(cat => (
        <div key={cat.label}>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-400 dark:text-slate-500 mb-1.5 px-1">
            {cat.label}
          </p>
          <div className="space-y-0.5">
            {SUGGESTED_QUESTIONS.slice(...cat.range).map(q => (
              <button
                key={q}
                onClick={() => onSelect(q)}
                className="w-full text-left text-xs px-2.5 py-2 rounded-lg text-slate-600 dark:text-slate-400 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors leading-snug"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
