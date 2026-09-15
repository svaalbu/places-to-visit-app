import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

import { seedLists, seedPlaces } from '@/src/data/seed';
import { createId } from '@/src/lib/id';
import type { Place, PlaceList } from '@/src/types';

type BordbokState = {
  lists: PlaceList[];
  places: Place[];
  addList: (input: Pick<PlaceList, 'name' | 'subtitle' | 'accent'>) => string;
  updateList: (id: string, patch: Partial<PlaceList>) => void;
  deleteList: (id: string) => void;
  addPlace: (input: Omit<Place, 'id'>) => string;
  updatePlace: (id: string, patch: Partial<Place>) => void;
  deletePlace: (id: string) => void;
  toggleVisited: (id: string) => void;
  restoreOsloStarter: () => void;
};

export const useBordbok = create<BordbokState>()(
  persist(
    (set) => ({
      lists: seedLists,
      places: seedPlaces,
      addList: (input) => {
        const id = createId('list');
        set((state) => ({
          lists: [...state.lists, { id, ...input }],
        }));
        return id;
      },
      updateList: (id, patch) => {
        set((state) => ({
          lists: state.lists.map((list) => (list.id === id ? { ...list, ...patch } : list)),
        }));
      },
      deleteList: (id) => {
        set((state) => ({
          lists: state.lists.filter((list) => list.id !== id),
          places: state.places.filter((place) => place.listId !== id),
        }));
      },
      addPlace: (input) => {
        const id = createId('place');
        set((state) => ({
          places: [{ ...input, id }, ...state.places],
        }));
        return id;
      },
      updatePlace: (id, patch) => {
        set((state) => ({
          places: state.places.map((place) => (place.id === id ? { ...place, ...patch } : place)),
        }));
      },
      deletePlace: (id) => {
        set((state) => ({
          places: state.places.filter((place) => place.id !== id),
        }));
      },
      toggleVisited: (id) => {
        set((state) => ({
          places: state.places.map((place) => {
            if (place.id !== id) {
              return place;
            }
            const visited = !place.visited;
            return {
              ...place,
              visited,
              visitedAt: visited ? new Date().toISOString().slice(0, 10) : undefined,
            };
          }),
        }));
      },
      restoreOsloStarter: () => {
        set({ lists: seedLists, places: seedPlaces });
      },
    }),
    {
      name: 'bordbok-oslo-v2',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (state) => ({ lists: state.lists, places: state.places }),
    },
  ),
);

export function placesForList(places: Place[], listId: string): Place[] {
  return places
    .filter((place) => place.listId === listId)
    .sort((a, b) => a.name.localeCompare(b.name, 'nb'));
}

export function visitedCount(places: Place[], listId?: string): { visited: number; total: number } {
  const scoped = listId ? places.filter((place) => place.listId === listId) : places;
  return {
    visited: scoped.filter((place) => place.visited).length,
    total: scoped.length,
  };
}
