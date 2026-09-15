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
  overflow: visible !important;
}
.bordbok-pin-wrap {
  position: relative;
  width: 54px;
  height: 54px;
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
  margin: 5px;
}
.bordbok-pin-inner.selected {
  width: 52px;
  height: 52px;
  margin: 1px;
}
.bordbok-pin-inner:not(.visited) img {
  filter: grayscale(0.75) brightness(0.7);
}
.bordbok-pin-inner.visited {
  border-color: #0B8A4B !important;
  border-width: 3px;
}
.bordbok-pin-inner img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.bordbok-check {
  position: absolute;
  right: 0;
  bottom: 0;
  z-index: 2;
  width: 22px;
  height: 22px;
  border-radius: 11px;
  background: #0B8A4B;
  color: #fff;
  border: 2px solid #fff;
  font: 800 13px/18px system-ui, sans-serif;
  text-align: center;
}
`;
