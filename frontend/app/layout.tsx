// Destination path: frontend/app/layout.tsx
// Replaces the existing file in full. (Supersedes the earlier draft
// from the previous session, which only mounted a bare NotificationBell
// with no logout or role-aware nav -- see AppHeader.tsx for the full
// fix.)

import type { ReactNode } from "react";
import "./globals.css";
import AppHeader from "../components/AppHeader";

export const metadata = {
  title: "AISafetyBenchExplorer",
  description: "AI safety benchmark catalogue -- admin panel and researcher dashboard",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AppHeader />
        {children}
      </body>
    </html>
  );
}
