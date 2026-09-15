import { ScrollViewStyleReset } from 'expo-router/html';
import type { ReactNode } from 'react';

export default function Root({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta httpEquiv="X-UA-Compatible" content="IE=edge" />
        <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
        <link
          rel="stylesheet"
          href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
          crossOrigin=""
        />
        <ScrollViewStyleReset />
        <style dangerouslySetInnerHTML={{ __html: css }} />
      </head>
      <body>{children}</body>
    </html>
  );
}

const css = `
body {
  background-color: #1C1814;
}
.leaflet-container {
  width: 100%;
  height: 100%;
  background: #1A1F18;
  font-family: ui-sans-serif, system-ui, sans-serif;
}
.leaflet-div-icon.bordbok-pin {
  background: transparent !important;
  border: 0 !important;
  width: 44px !important;
  height: 44px !important;
}
.bordbok-pin-inner {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  border: 2.5px solid #fff;
  overflow: hidden;
  box-shadow: 0 6px 16px rgba(0,0,0,0.35);
  background: #1c1814;
  box-sizing: border-box;
}
.bordbok-pin-inner.selected {
  width: 52px;
  height: 52px;
  box-shadow: 0 0 0 3px rgba(243, 237, 227, 0.9);
}
.bordbok-pin-inner img {
  width: 100%;
  height: 100%;
  max-width: 52px;
  max-height: 52px;
  object-fit: cover;
  display: block;
}
`;
