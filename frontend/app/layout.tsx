import type { ReactNode } from "react";
import "./globals.css";
import AppHeader from "../components/AppHeader";
import { Ubuntu_Mono } from "next/font/google";

const ubuntuMono = Ubuntu_Mono({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-ubuntu-mono",
});

export const metadata = {
  title: "AISafetyBenchExplorer",
  description: "AI safety benchmark catalogue -- admin panel and researcher dashboard",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className={ubuntuMono.variable}>
        <AppHeader />
        {children}
      </body>
    </html>
  );
}
