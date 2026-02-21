/**
 * ModelSelect — Dropdown for selecting an LLM model from a preset list.
 *
 * Groups options by provider. Selecting "Custom…" reveals a free-text
 * input so users can type any model name not in the preset list.
 */

import { useState, useEffect } from "react";
import type { ModelPreset } from "@/config/modelPresets";

interface ModelSelectProps {
  presets: ModelPreset[];
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  id?: string;
}

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: "Anthropic",
  openai: "OpenAI",
  google: "Google",
};

const CUSTOM_VALUE = "__custom__";

export default function ModelSelect({
  presets,
  value,
  onChange,
  placeholder = "Select a model…",
  id,
}: ModelSelectProps) {
  const isPresetValue = presets.some((p) => p.value === value);
  const [customText, setCustomText] = useState(
    !isPresetValue && value ? value : ""
  );
  const [selectVal, setSelectVal] = useState(
    isPresetValue ? value : value ? CUSTOM_VALUE : ""
  );

  // Keep select in sync if parent changes value externally
  useEffect(() => {
    const isPreset = presets.some((p) => p.value === value);
    if (isPreset) {
      setSelectVal(value);
      setCustomText("");
    } else if (value) {
      setSelectVal(CUSTOM_VALUE);
      setCustomText(value);
    } else {
      setSelectVal("");
      setCustomText("");
    }
  }, [value, presets]);

  const handleSelectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const v = e.target.value;
    setSelectVal(v);
    if (v === CUSTOM_VALUE) {
      // Switch to custom text input; don't update parent until user types
      setCustomText("");
      onChange("");
    } else {
      setCustomText("");
      onChange(v);
    }
  };

  const handleCustomChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCustomText(e.target.value);
    onChange(e.target.value);
  };

  // Group presets by provider
  const groups = Object.entries(PROVIDER_LABELS).reduce<
    Record<string, ModelPreset[]>
  >((acc, [providerKey]) => {
    const group = presets.filter((p) => p.provider === providerKey);
    if (group.length > 0) acc[providerKey] = group;
    return acc;
  }, {});

  return (
    <div className="space-y-2">
      <select
        id={id}
        value={selectVal}
        onChange={handleSelectChange}
        className="w-full bg-gray-50 dark:bg-surface border border-light-border dark:border-border rounded-lg px-3 py-2 text-sm text-gray-900 dark:text-white focus:outline-none focus:border-accent"
      >
        <option value="" disabled>
          {placeholder}
        </option>

        {Object.entries(groups).map(([providerKey, options]) => (
          <optgroup key={providerKey} label={PROVIDER_LABELS[providerKey]}>
            {options.map((preset) => (
              <option key={preset.value} value={preset.value}>
                {preset.label}
                {preset.useCase ? ` — ${preset.useCase}` : ""}
              </option>
            ))}
          </optgroup>
        ))}

        <optgroup label="Other">
          <option value={CUSTOM_VALUE}>Custom model name…</option>
        </optgroup>
      </select>

      {selectVal === CUSTOM_VALUE && (
        <input
          type="text"
          value={customText}
          onChange={handleCustomChange}
          placeholder="Enter model identifier, e.g. claude-sonnet-4-20250514"
          className="w-full bg-gray-50 dark:bg-surface border border-light-border dark:border-border rounded-lg px-3 py-2 text-sm text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-600 font-mono focus:outline-none focus:border-accent"
        />
      )}
    </div>
  );
}
