import { useState } from "react";

import { LoginForm } from "./auth/LoginForm";
import { RegisterForm } from "./auth/RegisterForm";
import { useAuth } from "./auth/AuthContext";

type AuthMode = "login" | "register";

export default function App() {
  const { user, isRestoring, login, logout } = useAuth();
  const [mode, setMode] = useState<AuthMode>("login");
  const [notice, setNotice] = useState("");

  if (isRestoring) {
    return (
      <main className="app-shell">
        <div className="loading-state" role="status">
          Restoring your session…
        </div>
      </main>
    );
  }

  if (user) {
    return (
      <main className="app-shell">
        <section className="workspace-card" aria-labelledby="workspace-title">
          <div>
            <p className="eyebrow">Authenticated workspace</p>
            <h1 id="workspace-title">Negotia</h1>
          </div>
          <p className="welcome-message">
            Signed in as <strong>{user.username}</strong>
          </p>
          <p className="workspace-placeholder">
            Negotiation workspace coming next.
          </p>
          <button className="secondary-button" type="button" onClick={logout}>
            Log out
          </button>
        </section>
      </main>
    );
  }

  function selectMode(nextMode: AuthMode) {
    setMode(nextMode);
    setNotice("");
  }

  function handleRegistered(username: string) {
    setMode("login");
    setNotice(`Account for ${username} created. Sign in to continue.`);
  }

  return (
    <main className="app-shell">
      <section className="auth-card" aria-labelledby="auth-title">
        <header className="auth-header">
          <p className="eyebrow">Negotiation practice</p>
          <h1 id="auth-title">Negotia</h1>
          <p>Build confidence through realistic negotiation practice.</p>
        </header>

        <div className="auth-tabs" role="tablist" aria-label="Authentication">
          <button
            className={mode === "login" ? "auth-tab active" : "auth-tab"}
            type="button"
            role="tab"
            aria-selected={mode === "login"}
            onClick={() => selectMode("login")}
          >
            Sign in
          </button>
          <button
            className={mode === "register" ? "auth-tab active" : "auth-tab"}
            type="button"
            role="tab"
            aria-selected={mode === "register"}
            onClick={() => selectMode("register")}
          >
            Register
          </button>
        </div>

        {notice ? (
          <p className="form-message success-message" role="status">
            {notice}
          </p>
        ) : null}

        {mode === "login" ? (
          <LoginForm onLogin={login} />
        ) : (
          <RegisterForm onRegistered={handleRegistered} />
        )}
      </section>
    </main>
  );
}
