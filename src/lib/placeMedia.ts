import type { Place } from '@/src/types';

export function coverPhoto(place: Place): string | undefined {
  return place.photoUri || place.coverPhotoUrl;
}

export function googleMapsUrl(place: Pick<Place, 'name' | 'address'>): string {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
    `${place.name}, ${place.address}, Oslo`,
  )}`;
}

export function formatGoogleRating(place: Place): string | undefined {
  if (place.googleRating == null) {
    return undefined;
  }
  const count =
    place.googleRatingsCount != null ? ` (${place.googleRatingsCount.toLocaleString('nb-NO')})` : '';
  return `${place.googleRating.toFixed(1)}${count}`;
}
