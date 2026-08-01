import { useState, type FormEvent } from "react";

import { register } from "../api/auth";
import { toErrorMessage } from "../api/client";

interface RegisterFormProps {
  onRegistered: (username: string) => void;
}

export function RegisterForm({ onRegistered }: RegisterFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const normalizedUsername = username.trim();
    if (normalizedUsername.length < 3) {
      setError("Username must be at least 3 characters.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setIsSubmitting(true);
    try {
      await register({ username: normalizedUsername, password });
      setPassword("");
      onRegistered(normalizedUsername);
    } catch (requestError) {
      setError(toErrorMessage(requestError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label htmlFor="register-username">Username</label>
        <input
          id="register-username"
          name="username"
          type="text"
          autoComplete="username"
          minLength={3}
          maxLength={50}
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          disabled={isSubmitting}
          required
        />
      </div>

      <div className="field">
        <label htmlFor="register-password">Password</label>
        <input
          id="register-password"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={8}
          maxLength={72}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          disabled={isSubmitting}
          required
        />
        <span className="field-hint">Use at least 8 characters.</span>
      </div>

      {error ? (
        <p className="form-message error-message" role="alert">
          {error}
        </p>
      ) : null}

      <button className="primary-button" type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Creating account…" : "Create account"}
      </button>
    </form>
  );
}
