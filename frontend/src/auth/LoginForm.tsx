import { useState, type FormEvent } from "react";

import { toErrorMessage } from "../api/client";

interface LoginFormProps {
  onLogin: (username: string, password: string) => Promise<void>;
}

export function LoginForm({ onLogin }: LoginFormProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const normalizedUsername = username.trim();
    if (!normalizedUsername || !password) {
      setError("Enter your username and password.");
      return;
    }

    setIsSubmitting(true);
    try {
      await onLogin(normalizedUsername, password);
    } catch (requestError) {
      setError(toErrorMessage(requestError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label htmlFor="login-username">Username</label>
        <input
          id="login-username"
          name="username"
          type="text"
          autoComplete="username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          disabled={isSubmitting}
          required
        />
      </div>

      <div className="field">
        <label htmlFor="login-password">Password</label>
        <input
          id="login-password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          disabled={isSubmitting}
          required
        />
      </div>

      {error ? (
        <p className="form-message error-message" role="alert">
          {error}
        </p>
      ) : null}

      <button className="primary-button" type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
