import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import {
  getCurrentUser,
  login as requestLogin,
  type AuthenticatedUser,
} from "../api/auth";

const TOKEN_STORAGE_KEY = "negotia_access_token";

interface AuthContextValue {
  user: AuthenticatedUser | null;
  isRestoring: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [isRestoring, setIsRestoring] = useState(true);

  useEffect(() => {
    let isActive = true;
    const token = localStorage.getItem(TOKEN_STORAGE_KEY);

    if (!token) {
      setIsRestoring(false);
      return () => {
        isActive = false;
      };
    }

    void getCurrentUser(token)
      .then((authenticatedUser) => {
        if (isActive) {
          setUser(authenticatedUser);
        }
      })
      .catch(() => {
        if (isActive) {
          localStorage.removeItem(TOKEN_STORAGE_KEY);
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
    const { access_token: token } = await requestLogin({ username, password });
    localStorage.setItem(TOKEN_STORAGE_KEY, token);

    try {
      const authenticatedUser = await getCurrentUser(token);
      setUser(authenticatedUser);
    } catch (error) {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      throw error;
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, isRestoring, login, logout }),
    [isRestoring, login, logout, user],
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
