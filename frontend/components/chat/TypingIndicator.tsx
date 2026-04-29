export function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 px-1 py-2" aria-label="Thinking…">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="w-2 h-2 rounded-full bg-indigo-400 dark:bg-indigo-500 animate-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}
