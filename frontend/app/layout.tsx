import type { ReactNode } from "react";
import "./globals.css";

export const metadata = {
  title: "AISafetyBenchExplorer Admin",
  description: "Admin CRUD panel for the AISafetyBenchExplorer catalogue",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
