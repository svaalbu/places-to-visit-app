export type PlaceList = {
  id: string;
  name: string;
  subtitle: string;
  accent: string;
};

export type Place = {
  id: string;
  listId: string;
  name: string;
  neighborhood: string;
  address: string;
  latitude: number;
  longitude: number;
  visited: boolean;
  note: string;
  photoUri?: string;
  coverPhotoUrl?: string;
  googleRating?: number;
  googleRatingsCount?: number;
  visitedAt?: string;
};

export type VisitFilter = 'all' | 'visited' | 'to-try';

export const OSLO_REGION = {
  latitude: 59.9139,
  longitude: 10.7522,
  latitudeDelta: 0.07,
  longitudeDelta: 0.07,
};

export const CAFE_MIN_RATING = 4.0;
export const RESTAURANT_MIN_RATING = 4.5;
