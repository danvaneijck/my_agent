import { FileCode, Tag } from "lucide-react";
import type { SkillSummary } from "@/hooks/useSkills";

const CATEGORY_COLORS: Record<string, string> = {
  code: "bg-blue-500/20 text-blue-400",
  config: "bg-purple-500/20 text-purple-400",
  procedure: "bg-green-500/20 text-green-400",
  template: "bg-yellow-500/20 text-yellow-400",
  reference: "bg-gray-500/20 text-gray-400",
};

interface SkillCardProps {
  skill: SkillSummary;
  onClick: () => void;
}

export default function SkillCard({ skill, onClick }: SkillCardProps) {
  const categoryColor = skill.category
    ? CATEGORY_COLORS[skill.category] || CATEGORY_COLORS.code
    : "bg-gray-500/20 text-gray-400";

  return (
    <button
      onClick={onClick}
      className="bg-white dark:bg-surface-light border border-light-border dark:border-border rounded-xl p-4 text-left hover:border-border-light transition-colors w-full"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <FileCode size={16} className="text-accent flex-shrink-0" />
          <h3 className="font-medium text-white truncate">{skill.name}</h3>
        </div>
        {skill.category && (
          <span
            className={`text-xs px-2 py-0.5 rounded-full whitespace-nowrap flex-shrink-0 ${categoryColor}`}
          >
            {skill.category}
          </span>
        )}
      </div>

      {skill.description && (
        <p className="text-sm text-gray-400 line-clamp-2 mb-3">
          {skill.description}
        </p>
      )}

      <div className="flex items-center gap-2 flex-wrap">
        {skill.language && (
          <span className="text-xs px-2 py-0.5 bg-surface-lighter rounded text-gray-400">
            {skill.language}
          </span>
        )}
        {skill.is_template && (
          <span className="text-xs px-2 py-0.5 bg-yellow-500/10 text-yellow-400 rounded">
            Template
          </span>
        )}
        {skill.tags && skill.tags.length > 0 && (
          <>
            {skill.tags.slice(0, 3).map((tag) => (
              <span
                key={tag}
                className="text-xs px-2 py-0.5 bg-surface-lighter rounded text-gray-500 flex items-center gap-1"
              >
                <Tag size={10} />
                {tag}
              </span>
            ))}
            {skill.tags.length > 3 && (
              <span className="text-xs text-gray-500">
                +{skill.tags.length - 3} more
              </span>
            )}
          </>
        )}
      </div>
    </button>
  );
}
