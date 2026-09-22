import './globals.css';

export const metadata = {
  title: 'FOBO Control Tower — Agent One',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
