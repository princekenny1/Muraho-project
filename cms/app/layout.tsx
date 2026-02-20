import type { Metadata } from "next";
import React from "react";

export const metadata: Metadata = {
  title: "Muraho Rwanda CMS",
  description: "Payload CMS Admin & API",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
