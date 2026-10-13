import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor to inject Authorization Bearer token or role test headers
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("postvisit_token");
      const role = localStorage.getItem("postvisit_role") || "doctor";
      const userId = localStorage.getItem("postvisit_user_id");

      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      } else {
        // Fallback sandbox test headers for local development verification
        config.headers["X-User-Role"] = role;
        if (userId) {
          config.headers["X-User-Id"] = userId;
        }
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for unified error formatting
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<any>) => {
    let message = "An unexpected error occurred.";
    let code = "UNKNOWN_ERROR";

    if (error.response) {
      const data = error.response.data;
      if (data?.error?.message) {
        message = data.error.message;
        code = data.error.code || code;
      } else if (typeof data?.detail === "string") {
        message = data.detail;
      } else if (data?.detail?.message) {
        message = data.detail.message;
        code = data.detail.code || code;
      } else if (error.response.status === 401) {
        message = "Authentication required. Please log in.";
        code = "UNAUTHORIZED";
      } else if (error.response.status === 403) {
        message = "Access restricted. You do not have permission to view this resource.";
        code = "FORBIDDEN";
      } else if (error.response.status === 404) {
        message = "Requested clinical record was not found.";
        code = "NOT_FOUND";
      }
    } else if (error.request) {
      message = "Unable to connect to the PostVisit AI server. Check your connection.";
      code = "NETWORK_ERROR";
    }

    return Promise.reject({
      status: error.response?.status,
      code,
      message,
      originalError: error,
    });
  }
);
