import { createElement, useEffect, useRef, type CSSProperties } from 'react';
import { StyleSheet, View } from 'react-native';
import type { LayerGroup, Map as LeafletMap } from 'leaflet';

import { OSLO_REGION, type Place } from '@/src/types';

type Props = {
  places: Place[];
  accentFor: (place: Place) => string;
  onSelect: (placeId: string) => void;
};

export function PlaceMap({ places, accentFor, onSelect }: Props) {
  const host = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const layerRef = useRef<LayerGroup | null>(null);
  const leafletRef = useRef<typeof import('leaflet') | null>(null);
  const accentRef = useRef(accentFor);
  const selectRef = useRef(onSelect);
  accentRef.current = accentFor;
  selectRef.current = onSelect;

  useEffect(() => {
    let cancelled = false;
    let resize: (() => void) | undefined;

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

      L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap &copy; CARTO',
        subdomains: 'abcd',
        maxZoom: 19,
      }).addTo(map);

      mapRef.current = map;
      layerRef.current = L.layerGroup().addTo(map);
      resize = () => map.invalidateSize();
      window.setTimeout(resize, 250);
      window.addEventListener('resize', resize);
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
    };
  }, []);

  useEffect(() => {
    const L = leafletRef.current;
    const layer = layerRef.current;
    if (!L || !layer) {
      const retry = window.setTimeout(() => {
        const lateL = leafletRef.current;
        const lateLayer = layerRef.current;
        if (!lateL || !lateLayer) {
          return;
        }
        paint(lateL, lateLayer, places, accentRef.current, selectRef.current);
      }, 300);
      return () => window.clearTimeout(retry);
    }
    paint(L, layer, places, accentRef.current, selectRef.current);
  }, [places]);

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
) {
  layer.clearLayers();
  places.forEach((place) => {
    const accent = accentFor(place);
    const marker = L.circleMarker([place.latitude, place.longitude], {
      radius: place.visited ? 9 : 8,
      color: accent,
      weight: 2.5,
      fillColor: place.visited ? accent : '#FFFBF5',
      fillOpacity: 1,
    });
    marker.bindTooltip(`${place.name} · ${place.visited ? 'visited' : 'to try'}`, {
      direction: 'top',
    });
    marker.on('click', () => onSelect(place.id));
    marker.addTo(layer);
  });
}

const webMapStyle: CSSProperties = {
  width: '100%',
  height: '100%',
  minHeight: 320,
};

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    minHeight: 320,
  },
});
