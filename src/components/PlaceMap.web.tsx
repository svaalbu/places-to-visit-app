import { createElement, useEffect, useRef, useState, type CSSProperties } from 'react';
import { StyleSheet, View } from 'react-native';
import type { LayerGroup, Map as LeafletMap } from 'leaflet';

import { coverPhoto } from '@/src/lib/placeMedia';
import { OSLO_REGION, type Place } from '@/src/types';

type Props = {
  places: Place[];
  accentFor: (place: Place) => string;
  selectedId?: string;
  onSelect: (placeId: string) => void;
};

const PIN_CSS = `
.leaflet-div-icon.bordbok-pin { background: transparent !important; border: 0 !important; overflow: visible !important; }
.bordbok-pin-wrap { position: relative; width: 54px; height: 54px; }
.bordbok-pin-inner { width: 44px; height: 44px; border-radius: 14px; border: 2.5px solid #fff; overflow: hidden; box-shadow: 0 6px 16px rgba(0,0,0,0.35); background: #1c1814; box-sizing: border-box; margin: 5px; }
.bordbok-pin-inner.selected { width: 52px; height: 52px; margin: 1px; }
.bordbok-pin-inner:not(.visited) img { filter: grayscale(0.75) brightness(0.7); }
.bordbok-pin-inner.visited { border-color: #0B8A4B !important; border-width: 3px; }
.bordbok-pin-inner img { width: 100%; height: 100%; object-fit: cover; display: block; }
.bordbok-check { position: absolute; right: 0; bottom: 0; z-index: 2; width: 22px; height: 22px; border-radius: 11px; background: #0B8A4B; color: #fff; border: 2px solid #fff; font: 800 13px/18px system-ui, sans-serif; text-align: center; box-shadow: 0 2px 6px rgba(0,0,0,0.35); }
`;

function ensureLeafletCss() {
  if (typeof document === 'undefined') return;
  if (!document.querySelector('link[data-bordbok-leaflet]')) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    link.setAttribute('data-bordbok-leaflet', 'true');
    document.head.appendChild(link);
  }
  if (!document.querySelector('style[data-bordbok-pins]')) {
    const style = document.createElement('style');
    style.setAttribute('data-bordbok-pins', 'true');
    style.textContent = PIN_CSS;
    document.head.appendChild(style);
  }
}

export function PlaceMap({ places, accentFor, selectedId, onSelect }: Props) {
  const host = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const layerRef = useRef<LayerGroup | null>(null);
  const leafletRef = useRef<typeof import('leaflet') | null>(null);
  const placesRef = useRef(places);
  const accentRef = useRef(accentFor);
  const selectRef = useRef(onSelect);
  const selectedRef = useRef(selectedId);
  const [ready, setReady] = useState(false);

  placesRef.current = places;
  accentRef.current = accentFor;
  selectRef.current = onSelect;
  selectedRef.current = selectedId;

  useEffect(() => {
    let cancelled = false;
    let resize: (() => void) | undefined;
    ensureLeafletCss();

    const start = async () => {
      const L = await import('leaflet');
      if (cancelled || !host.current) {
        return;
      }
      leafletRef.current = L;

      const map = L.map(host.current, {
        zoomControl: true,
        attributionControl: true,
      }).setView([OSLO_REGION.latitude, OSLO_REGION.longitude], 13);

      L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        {
          attribution: 'Tiles © Esri',
          maxZoom: 19,
        },
      ).addTo(map);
      L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Reference_Overlay/MapServer/tile/{z}/{y}/{x}',
        {
          attribution: '',
          maxZoom: 19,
        },
      ).addTo(map);

      mapRef.current = map;
      layerRef.current = L.layerGroup().addTo(map);
      paint(
        L,
        layerRef.current,
        placesRef.current,
        accentRef.current,
        selectRef.current,
        selectedRef.current,
      );

      resize = () => {
        map.invalidateSize();
        paint(
          L,
          layerRef.current!,
          placesRef.current,
          accentRef.current,
          selectRef.current,
          selectedRef.current,
        );
      };
      window.setTimeout(resize, 50);
      window.setTimeout(resize, 300);
      window.addEventListener('resize', resize);
      setReady(true);
    };

    void start();

    return () => {
      cancelled = true;
      if (resize) {
        window.removeEventListener('resize', resize);
      }
      mapRef.current?.remove();
      mapRef.current = null;
      layerRef.current = null;
      setReady(false);
    };
  }, []);

  useEffect(() => {
    const L = leafletRef.current;
    const layer = layerRef.current;
    if (!ready || !L || !layer) {
      return;
    }
    paint(L, layer, places, accentRef.current, selectRef.current, selectedId);
    mapRef.current?.invalidateSize();
  }, [places, ready, selectedId]);

  return (
    <View style={styles.wrap}>
      {createElement('div', { ref: host, style: webMapStyle })}
    </View>
  );
}

function paint(
  L: typeof import('leaflet'),
  layer: LayerGroup,
  places: Place[],
  accentFor: (place: Place) => string,
  onSelect: (placeId: string) => void,
  selectedId?: string,
) {
  layer.clearLayers();
  places.forEach((place) => {
    const accent = accentFor(place);
    const photo = coverPhoto(place);
    const selected = place.id === selectedId;
    const size = selected ? 52 : 44;
    const img = photo
      ? `<img src="${photo.replace(/&/g, '&amp;').replace(/"/g, '&quot;')}" alt="" />`
      : `<span style="background:${accent};display:block;width:100%;height:100%"></span>`;
    const check = place.visited ? '<span class="bordbok-check">✓</span>' : '';
    const icon = L.divIcon({
      className: 'bordbok-pin',
      html: `<div class="bordbok-pin-wrap">${check}<div class="bordbok-pin-inner${place.visited ? ' visited' : ''}${selected ? ' selected' : ''}" style="border-color:${place.visited ? '#0B8A4B' : accent}">${img}</div></div>`,
      iconSize: [size + 10, size + 10],
      iconAnchor: [(size + 10) / 2, (size + 10) / 2],
    });
    const marker = L.marker([place.latitude, place.longitude], { icon });
    const rating = place.googleRating ? ` · ${place.googleRating.toFixed(1)}` : '';
    marker.bindTooltip(`${place.name}${rating} · ${place.visited ? 'Visited' : 'To try'}`, {
      direction: 'top',
    });
    marker.on('click', () => onSelect(place.id));
    marker.addTo(layer);
  });
}

const webMapStyle: CSSProperties = {
  position: 'absolute',
  inset: 0,
  width: '100%',
  height: '100%',
};

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    minHeight: 420,
    position: 'relative',
    backgroundColor: '#1A1F18',
  },
});
