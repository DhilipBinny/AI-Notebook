import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'AI Notebook',
  description: 'Jupyter Notebook with LLM capabilities',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  )
}
