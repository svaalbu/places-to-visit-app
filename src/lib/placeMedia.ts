import { useGooglePhotoMap } from '@/src/lib/googleMapsPhotos';
import type { Place } from '@/src/types';

export function coverPhoto(place: Place, googleUri?: string): string | undefined {
  return place.photoUri || googleUri || place.coverPhotoUrl;
}

export function useCoverPhoto(place: Place): string | undefined {
  const googleUri = useGooglePhotoMap((state) => state.byId[place.id]);
  return coverPhoto(place, googleUri);
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
