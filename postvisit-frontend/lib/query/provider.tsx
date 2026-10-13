"use client";

import React, { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 1000 * 30, // 30 seconds
            gcTime: 1000 * 60 * 5, // 5 minutes
            retry: (failureCount, error: any) => {
              // Never retry on 401 or 403 authorization errors
              if (error?.status === 401 || error?.status === 403 || error?.status === 404) {
                return false;
              }
              return failureCount < 2;
            },
            refetchOnWindowFocus: false,
          },
          mutations: {
            retry: false, // Never automatically retry sensitive clinical mutations
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}
