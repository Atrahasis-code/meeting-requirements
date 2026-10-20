import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { Notifications } from "./components/shared";
import App from "./App";
import "./styles.css";

const client = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 1000, refetchOnWindowFocus: true },
  },
});
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <Notifications>
          <App />
        </Notifications>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
