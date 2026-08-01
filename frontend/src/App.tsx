import { useState } from "react";

import { LoginForm } from "./auth/LoginForm";
import { RegisterForm } from "./auth/RegisterForm";
import { useAuth } from "./auth/AuthContext";
import { Workspace } from "./workspace/Workspace";

type AuthMode = "login" | "register";

export default function App() {
  const {
    user,
    accessToken,
    sessionNotice,
    isRestoring,
    login,
    logout,
    clearSessionNotice,
  } = useAuth();
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

  if (user && accessToken) {
    return (
      <Workspace
        username={user.username}
        token={accessToken}
        onLogout={logout}
      />
    );
  }

  function selectMode(nextMode: AuthMode) {
    setMode(nextMode);
    setNotice("");
    clearSessionNotice();
  }

  function handleRegistered(username: string) {
    setMode("login");
    clearSessionNotice();
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

        {sessionNotice || notice ? (
          <p
            className={`form-message ${
              sessionNotice ? "error-message" : "success-message"
            }`}
            role={sessionNotice ? "alert" : "status"}
          >
            {sessionNotice || notice}
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
