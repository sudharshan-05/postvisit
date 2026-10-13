import { apiClient } from "./axios";
import { UserProfile, UserRole } from "@/types";

export const authApi = {
  async getMe(): Promise<UserProfile> {
    const res = await apiClient.get<UserProfile>("/api/v1/auth/me");
    return res.data;
  },

  setAuthSession(token: string | null, role: UserRole, userId: string, name?: string) {
    if (typeof window !== "undefined") {
      if (token) {
        localStorage.setItem("postvisit_token", token);
      } else {
        localStorage.removeItem("postvisit_token");
      }
      localStorage.setItem("postvisit_role", role);
      localStorage.setItem("postvisit_user_id", userId);
      if (name) localStorage.setItem("postvisit_user_name", name);
    }
  },

  clearSession() {
    if (typeof window !== "undefined") {
      localStorage.removeItem("postvisit_token");
      localStorage.removeItem("postvisit_role");
      localStorage.removeItem("postvisit_user_id");
      localStorage.removeItem("postvisit_user_name");
    }
  },

  getCurrentRole(): UserRole {
    if (typeof window !== "undefined") {
      return (localStorage.getItem("postvisit_role") as UserRole) || "doctor";
    }
    return "doctor";
  },

  getCurrentUserId(): string {
    if (typeof window !== "undefined") {
      return localStorage.getItem("postvisit_user_id") || "dr_ramanathan";
    }
    return "dr_ramanathan";
  }
};
