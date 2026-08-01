import { useState, type FormEvent } from "react";

import {
  type ScenarioCreateRequest,
  type ScenarioDifficulty,
} from "../api/scenarios";

interface ScenarioFormProps {
  isSubmitting: boolean;
  error: string;
  onSubmit: (request: ScenarioCreateRequest) => Promise<boolean>;
  onCancel: () => void;
}

interface ScenarioFormState {
  title: string;
  description: string;
  difficulty: ScenarioDifficulty;
}

const initialState: ScenarioFormState = {
  title: "",
  description: "",
  difficulty: "intermediate",
};

export function ScenarioForm({
  isSubmitting,
  error,
  onSubmit,
  onCancel,
}: ScenarioFormProps) {
  const [form, setForm] = useState<ScenarioFormState>(initialState);

  function updateField<K extends keyof ScenarioFormState>(
    field: K,
    value: ScenarioFormState[K],
  ) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const created = await onSubmit({
      title: form.title.trim(),
      description: form.description.trim(),
      difficulty: form.difficulty,
    });

    if (created) {
      setForm(initialState);
    }
  }

  return (
    <section className="content-panel" aria-labelledby="create-scenario-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">AI-assisted practice setup</p>
          <h2 id="create-scenario-title">Generate a scenario</h2>
        </div>
        <button className="text-button" type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>

      <form className="scenario-form" onSubmit={handleSubmit}>
        <TextField
          id="scenario-title"
          label="Title"
          value={form.title}
          onChange={(value) => updateField("title", value)}
          disabled={isSubmitting}
          placeholder="e.g. Negotiate a senior engineering offer"
          minLength={3}
        />
        <div className="field">
          <label htmlFor="scenario-difficulty">Difficulty</label>
          <select
            id="scenario-difficulty"
            value={form.difficulty}
            onChange={(event) =>
              updateField(
                "difficulty",
                event.target.value as ScenarioDifficulty,
              )
            }
            disabled={isSubmitting}
          >
            <option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option>
            <option value="advanced">Advanced</option>
          </select>
        </div>
        <TextAreaField
          id="scenario-description"
          label="Description"
          value={form.description}
          onChange={(value) => updateField("description", value)}
          disabled={isSubmitting}
          wide
          placeholder="Describe the situation, what you want, and any important context."
          minLength={10}
        />

        {error ? (
          <p className="form-message error-message form-wide" role="alert">
            {error}
          </p>
        ) : null}

        <div className="form-actions form-wide">
          <button
            className="secondary-button"
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button
            className="primary-button"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Generating..." : "Generate Scenario"}
          </button>
        </div>
      </form>
    </section>
  );
}

interface TextFieldProps {
  id: string;
  label: string;
  value: string;
  disabled: boolean;
  placeholder: string;
  minLength: number;
  onChange: (value: string) => void;
}

function TextField({
  id,
  label,
  value,
  disabled,
  placeholder,
  minLength,
  onChange,
}: TextFieldProps) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        placeholder={placeholder}
        minLength={minLength}
        required
      />
    </div>
  );
}

interface TextAreaFieldProps extends TextFieldProps {
  wide?: boolean;
}

function TextAreaField({
  id,
  label,
  value,
  disabled,
  placeholder,
  minLength,
  onChange,
  wide = false,
}: TextAreaFieldProps) {
  return (
    <div className={wide ? "field form-wide" : "field"}>
      <label htmlFor={id}>{label}</label>
      <textarea
        id={id}
        rows={4}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        placeholder={placeholder}
        minLength={minLength}
        required
      />
    </div>
  );
}
