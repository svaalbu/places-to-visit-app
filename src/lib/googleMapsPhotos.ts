import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';

import { googleMapsApiKey } from '@/src/lib/googleMapsKey';
import type { Place } from '@/src/types';

const CACHE_KEY = 'bordbok-google-photo-names-v1';
const CACHE_MS = 1000 * 60 * 60 * 24;

type PhotoNameCache = Record<string, { name: string; at: number }>;

type PhotoMapState = {
  byId: Record<string, string>;
  setPhoto: (id: string, uri: string) => void;
};

export const useGooglePhotoMap = create<PhotoMapState>((set) => ({
  byId: {},
  setPhoto: (id, uri) =>
    set((state) => {
      if (state.byId[id] === uri) {
        return state;
      }
      return { byId: { ...state.byId, [id]: uri } };
    }),
}));

let nameCache: PhotoNameCache | null = null;
const inflight = new Map<string, Promise<void>>();
let active = 0;
const waiters: Array<() => void> = [];

function streetViewUrl(place: Place, key: string): string {
  const params = new URLSearchParams({
    size: '800x800',
    location: `${place.latitude},${place.longitude}`,
    fov: '70',
    pitch: '8',
    source: 'outdoor',
    key,
  });
  return `https://maps.googleapis.com/maps/api/streetview?${params.toString()}`;
}

async function lookupPlacePhotoUri(place: Place, key: string): Promise<string | undefined> {
  const photoName = await lookupPlacePhotoName(place, key);
  if (!photoName) {
    return undefined;
  }

  const media = await fetch(
    `https://places.googleapis.com/v1/${encodeURI(photoName)}/media?maxHeightPx=800&maxWidthPx=800&skipHttpRedirect=true&key=${encodeURIComponent(key)}`,
  );
  if (!media.ok) {
    return undefined;
  }
  const payload = (await media.json()) as { photoUri?: string };
  return payload.photoUri;
}

async function loadNameCache(): Promise<PhotoNameCache> {
  if (nameCache) {
    return nameCache;
  }
  try {
    const raw = await AsyncStorage.getItem(CACHE_KEY);
    nameCache = raw ? (JSON.parse(raw) as PhotoNameCache) : {};
  } catch {
    nameCache = {};
  }
  return nameCache;
}

async function saveNameCache(): Promise<void> {
  if (!nameCache) {
    return;
  }
  try {
    await AsyncStorage.setItem(CACHE_KEY, JSON.stringify(nameCache));
  } catch {
    // Ignore disk errors; memory cache still works for this session.
  }
}

async function withLimit<T>(task: () => Promise<T>): Promise<T> {
  if (active >= 3) {
    await new Promise<void>((resolve) => waiters.push(resolve));
  }
  active += 1;
  try {
    return await task();
  } finally {
    active -= 1;
    const next = waiters.shift();
    next?.();
  }
}

async function lookupPlacePhotoName(place: Place, key: string): Promise<string | undefined> {
  const cache = await loadNameCache();
  const hit = cache[place.id];
  if (hit && Date.now() - hit.at < CACHE_MS) {
    return hit.name;
  }

  const response = await fetch('https://places.googleapis.com/v1/places:searchText', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Goog-Api-Key': key,
      'X-Goog-FieldMask': 'places.photos.name',
    },
    body: JSON.stringify({
      textQuery: `${place.name}, ${place.address}, Oslo, Norway`,
      maxResultCount: 1,
      languageCode: 'en',
      locationBias: {
        circle: {
          center: { latitude: place.latitude, longitude: place.longitude },
          radius: 150,
        },
      },
    }),
  });

  if (!response.ok) {
    return hit?.name;
  }

  const data = (await response.json()) as { places?: Array<{ photos?: Array<{ name?: string }> }> };
  const name = data.places?.[0]?.photos?.[0]?.name;
  if (!name) {
    return undefined;
  }
  cache[place.id] = { name, at: Date.now() };
  await saveNameCache();
  return name;
}

async function resolveOne(place: Place): Promise<void> {
  const key = googleMapsApiKey();
  if (!key) {
    return;
  }

  const setPhoto = useGooglePhotoMap.getState().setPhoto;
  setPhoto(place.id, streetViewUrl(place, key));

  try {
    const photoUri = await withLimit(() => lookupPlacePhotoUri(place, key));
    if (photoUri) {
      setPhoto(place.id, photoUri);
    }
  } catch {
    // Street View cover stays in place if Places lookup fails (billing, CORS on web, etc.).
  }
}

export function prefetchGooglePhotos(places: Place[]): void {
  if (!googleMapsApiKey()) {
    return;
  }
  for (const place of places) {
    if (inflight.has(place.id)) {
      continue;
    }
    const run = resolveOne(place).finally(() => {
      inflight.delete(place.id);
    });
    inflight.set(place.id, run);
  }
}
