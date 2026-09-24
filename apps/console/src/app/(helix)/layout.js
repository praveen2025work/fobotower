import { Inter, JetBrains_Mono, Manrope } from 'next/font/google';

import './helix.css';

// Self-hosted at build time, so the app does not block on fonts.googleapis.com.
const manrope = Manrope({
  subsets: ['latin'],
  weight: ['600', '700', '800'],
  variable: '--font-manrope',
});

const inter = Inter({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-inter',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-mono',
});

export const metadata = {
  title: 'FOBO Control Tower — Agent One',
  description:
    'Helix · Agent One sessions across CATS vs MOTIF and Rec Factory recs',
};

/**
 * The loaded family alone, without next/font's metric-adjusted Arial fallback.
 * The mock let glyphs these fonts lack (→, ↔) fall through to the system font,
 * and the Arial fallback would draw them differently.
 */
const family = (font) => font.style.fontFamily.split(',')[0].trim();

const FONT_VARS = {
  '--hx-font-manrope': family(manrope),
  '--hx-font-inter': family(inter),
  '--hx-font-mono': family(jetbrainsMono),
};

export default function HelixLayout({ children }) {
  return (
    <html lang="en" style={FONT_VARS}>
      <body>{children}</body>
    </html>
  );
}
