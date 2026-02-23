interface WaveProgressProps {
  currentWave: number;
  totalWaves: number;
}

export default function WaveProgress({ currentWave, totalWaves }: WaveProgressProps) {
  if (totalWaves === 0) return null;

  return (
    <div className="flex items-center gap-2">
      {Array.from({ length: totalWaves }, (_, i) => {
        const wave = i + 1;
        const isComplete = wave < currentWave;
        const isCurrent = wave === currentWave;

        return (
          <div key={wave} className="flex items-center gap-1">
            {i > 0 && (
              <div
                className={`w-6 h-0.5 ${isComplete ? "bg-green-500" : "bg-gray-300 dark:bg-surface-lighter"}`}
              />
            )}
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium transition-colors ${
                isComplete
                  ? "bg-green-500 text-white"
                  : isCurrent
                    ? "bg-accent text-white ring-2 ring-accent/30"
                    : "bg-gray-200 dark:bg-surface-lighter text-gray-500 dark:text-gray-400"
              }`}
            >
              {isComplete ? "\u2713" : wave}
            </div>
          </div>
        );
      })}
    </div>
  );
}
