import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AppThemeProvider } from "@langchain/macaw-components/hooks/AppThemeProvider";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import App from "./App";
import "./style.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppThemeProvider>
      <TooltipProvider>
        <App />
      </TooltipProvider>
    </AppThemeProvider>
  </StrictMode>,
);
