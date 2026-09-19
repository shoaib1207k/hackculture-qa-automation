import React from "react";
import { createRoot } from "react-dom/client";
import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import App from "./App.jsx";

createRoot(document.getElementById("root")).render(
  <ThemeProvider theme={createTheme({ palette: { mode: "light" } })}>
    <CssBaseline />
    <App />
  </ThemeProvider>
);
