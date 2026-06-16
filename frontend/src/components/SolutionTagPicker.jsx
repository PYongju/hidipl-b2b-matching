import { useState } from "react";
import { SOLUTION_OPTIONS } from "../utils/projectRequestText";

export { SOLUTION_OPTIONS };

export function SolutionTagChipList({ value = [], onChange }) {
  const selected = Array.isArray(value) ? value : [];
  if (selected.length === 0) return null;

  const removeSolution = (tag) => {
    onChange(selected.filter((item) => item !== tag));
  };

  return (
    <div className="solution-chip-row">
      {selected.map((tag) => (
        <span className="solution-chip priority-chip" key={tag}>
          {tag}
          <button
            aria-label={`${tag} 삭제`}
            className="solution-chip-remove"
            onClick={() => removeSolution(tag)}
            type="button"
          >
            ×
          </button>
        </span>
      ))}
    </div>
  );
}

export default function SolutionTagPicker({
  value = [],
  onChange,
  showChips = true,
}) {
  const selected = Array.isArray(value) ? value : [];
  const [pickerValue, setPickerValue] = useState("");

  const availableOptions = SOLUTION_OPTIONS.filter((tag) => !selected.includes(tag));

  const addSolution = (tag) => {
    if (!tag || selected.includes(tag)) return;
    onChange([...selected, tag]);
    setPickerValue("");
  };

  const handleSelectChange = (event) => {
    const nextTag = event.target.value;
    setPickerValue(nextTag);
    if (nextTag) {
      addSolution(nextTag);
    }
  };

  return (
    <div className="solution-picker">
      <select
        disabled={availableOptions.length === 0 && selected.length > 0}
        onChange={handleSelectChange}
        value={pickerValue}
      >
        <option value="">
          {availableOptions.length === 0 && selected.length > 0
            ? "선택할 수 있는 솔루션이 없어요"
            : "솔루션 선택"}
        </option>
        {availableOptions.map((tag) => (
          <option key={tag} value={tag}>
            {tag}
          </option>
        ))}
      </select>

      {showChips && (
        <SolutionTagChipList onChange={onChange} value={selected} />
      )}
    </div>
  );
}
