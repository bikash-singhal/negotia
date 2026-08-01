import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";

import {
  getCurrentUser,
  login as requestLogin,
  type AuthenticatedUser,
} from "../api/auth";
import {
  registerAuthenticationFailureHandler,
  SESSION_EXPIRED_MESSAGE,
} from "../api/client";

const TOKEN_STORAGE_KEY = "negotia_access_token";

interface AuthContextValue {
  user: AuthenticatedUser | null;
  accessToken: string | null;
  sessionNotice: string;
  isRestoring: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  clearSessionNotice: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [sessionNotice, setSessionNotice] = useState("");
  const [isRestoring, setIsRestoring] = useState(true);
  const activeTokenRef = useRef<string | null>(null);
  const sessionExpirationHandledRef = useRef(false);

  const expireSession = useCallback((rejectedToken: string) => {
    if (
      activeTokenRef.current !== rejectedToken ||
      sessionExpirationHandledRef.current
    ) {
      return;
    }

    sessionExpirationHandledRef.current = true;
    activeTokenRef.current = null;
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setAccessToken(null);
    setUser(null);
    setSessionNotice(SESSION_EXPIRED_MESSAGE);
  }, []);

  useEffect(
    () => registerAuthenticationFailureHandler(expireSession),
    [expireSession],
  );

  useEffect(() => {
    let isActive = true;
    const token = localStorage.getItem(TOKEN_STORAGE_KEY);

    if (!token) {
      setIsRestoring(false);
      return () => {
        isActive = false;
      };
    }

    activeTokenRef.current = token;
    sessionExpirationHandledRef.current = false;

    void getCurrentUser(token)
      .then((authenticatedUser) => {
        if (isActive) {
          setAccessToken(token);
          setUser(authenticatedUser);
        }
      })
      .catch(() => {
        if (isActive) {
          localStorage.removeItem(TOKEN_STORAGE_KEY);
          activeTokenRef.current = null;
          setAccessToken(null);
        }
      })
      .finally(() => {
        if (isActive) {
          setIsRestoring(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    sessionExpirationHandledRef.current = false;
    setSessionNotice("");
    const { access_token: token } = await requestLogin({ username, password });
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
    activeTokenRef.current = token;

    try {
      const authenticatedUser = await getCurrentUser(token);
      setAccessToken(token);
      setUser(authenticatedUser);
    } catch (error) {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      activeTokenRef.current = null;
      setAccessToken(null);
      throw error;
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    activeTokenRef.current = null;
    sessionExpirationHandledRef.current = false;
    setAccessToken(null);
    setUser(null);
    setSessionNotice("");
  }, []);

  const clearSessionNotice = useCallback(() => {
    setSessionNotice("");
  }, []);

  const value = useMemo(
    () => ({
      user,
      accessToken,
      sessionNotice,
      isRestoring,
      login,
      logout,
      clearSessionNotice,
    }),
    [
      accessToken,
      clearSessionNotice,
      isRestoring,
      login,
      logout,
      sessionNotice,
      user,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider.");
  }
  return context;
}
