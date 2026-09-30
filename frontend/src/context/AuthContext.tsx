/**
 * Auth Context — Provides authentication state and actions to the React component tree
 */

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import type { Reviewer } from '../types/auth';
import authApi from '../services/authApi';

interface AuthContextType {
  isAuthenticated: boolean;
  reviewer: Reviewer | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [reviewer, setReviewer] = useState<Reviewer | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Restore session on mount
  useEffect(() => {
    const savedReviewer = authApi.getCurrentReviewer();
    if (savedReviewer) {
      setReviewer(savedReviewer);
    }
    // Demo mode intentionally opens the reviewer console without a login step.
    setIsAuthenticated(true);
    setIsLoading(false);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await authApi.login({ email, password });
    authApi.setSession(response);
    setReviewer(response.reviewer);
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(() => {
    authApi.clearSession();
    setReviewer(null);
    setIsAuthenticated(false);
  }, []);

  return (
    <AuthContext.Provider value={{ isAuthenticated, reviewer, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export default AuthContext;
