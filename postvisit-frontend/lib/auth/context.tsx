"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { UserProfile, UserRole } from "@/types";
import { authApi } from "@/lib/api/auth";
import { useQueryClient } from "@tanstack/react-query";

interface AuthContextType {
  user: UserProfile | null;
  role: UserRole;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (role: UserRole, token?: string, userId?: string, name?: string) => Promise<void>;
  logout: () => void;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [role, setRole] = useState<UserRole>("doctor");
  const [isLoading, setIsLoading] = useState(true);
  const queryClient = useQueryClient();

  const loadUserProfile = async () => {
    setIsLoading(true);
    try {
      const profile = await authApi.getMe();
      setUser(profile);
      setRole(profile.role);
    } catch (err) {
      // In sandbox/local dev mode, provide active fallback role from localStorage
      const savedRole = authApi.getCurrentRole();
      const savedUserId = authApi.getCurrentUserId();
      setRole(savedRole);
      setUser({
        user_id: savedUserId,
        name: savedRole === "doctor" ? "Dr. A. Ramanathan" : "Ananya Patel",
        role: savedRole,
        permissions: savedRole === "doctor" ? ["doctor:all"] : ["patient:all"],
        is_test_identity: true,
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadUserProfile();
  }, []);

  const login = async (newRole: UserRole, token?: string, userId?: string, name?: string) => {
    const assignedUserId = userId || (newRole === "doctor" ? "dr_ramanathan" : "pt_89241");
    authApi.setAuthSession(token || null, newRole, assignedUserId, name);
    queryClient.clear(); // Clear all clinical caches on user/role change
    await loadUserProfile();
  };

  const logout = () => {
    authApi.clearSession();
    setUser(null);
    queryClient.clear(); // Safe data isolation on logout
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        role,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        refreshProfile: loadUserProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
