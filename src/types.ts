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
  visitedAt?: string;
};

export type VisitFilter = 'all' | 'visited' | 'to-try';

export const OSLO_REGION = {
  latitude: 59.9139,
  longitude: 10.7522,
  latitudeDelta: 0.08,
  longitudeDelta: 0.08,
};
