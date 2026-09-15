import * as Haptics from 'expo-haptics';
import { router } from 'expo-router';
import { useCallback, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { FilterChips } from '@/src/components/FilterChips';
import { MapPlaceCard } from '@/src/components/MapPlaceCard';
import { PlaceMap } from '@/src/components/PlaceMap';
import { useBordbok } from '@/src/store';
import { colors, fonts } from '@/src/theme';
import type { Place, VisitFilter } from '@/src/types';

export default function MapHomeScreen() {
  const lists = useBordbok((state) => state.lists);
  const places = useBordbok((state) => state.places);
  const toggleVisited = useBordbok((state) => state.toggleVisited);
  const [listFilter, setListFilter] = useState('all');
  const [visitFilter, setVisitFilter] = useState<VisitFilter>('all');
  const [selectedId, setSelectedId] = useState<string | undefined>();

  const visible = useMemo(() => {
    return places.filter((place) => {
      const listOk = listFilter === 'all' || place.listId === listFilter;
      const visitOk =
        visitFilter === 'all' || (visitFilter === 'visited' ? place.visited : !place.visited);
      return listOk && visitOk;
    });
  }, [listFilter, places, visitFilter]);

  const selected = visible.find((place) => place.id === selectedId) ?? visible[0];

  const accentFor = useCallback(
    (place: Place) => lists.find((list) => list.id === place.listId)?.accent ?? colors.forest,
    [lists],
  );

  return (
    <View style={styles.root}>
      <PlaceMap
        places={visible}
        selectedId={selected?.id}
        accentFor={accentFor}
        onSelect={(id) => {
          void Haptics.selectionAsync();
          setSelectedId(id);
        }}
      />
      <SafeAreaView pointerEvents="box-none" style={styles.overlay} edges={['top']}>
        <View style={styles.top}>
          <Text style={styles.brand}>Bordbok</Text>
          <Text style={styles.sub}>Oslo · photo pins on the map</Text>
          <FilterChips
            selected={listFilter}
            onSelect={(key) => {
              setListFilter(key);
              setSelectedId(undefined);
            }}
            chips={[
              { key: 'all', label: 'All' },
              ...lists.map((list) => ({ key: list.id, label: list.name })),
            ]}
          />
          <FilterChips
            selected={visitFilter}
            onSelect={(key) => setVisitFilter(key as VisitFilter)}
            chips={[
              { key: 'all', label: 'All' },
              { key: 'to-try', label: 'To try' },
              { key: 'visited', label: 'Visited' },
            ]}
          />
        </View>
      </SafeAreaView>
      <View style={styles.bottom} pointerEvents="box-none">
        {selected ? (
          <MapPlaceCard
            place={selected}
            list={lists.find((list) => list.id === selected.listId)}
            onOpen={() => router.push(`/place/${selected.id}`)}
            onToggleVisited={() => {
              void Haptics.selectionAsync();
              toggleVisited(selected.id);
            }}
          />
        ) : (
          <Text style={styles.empty}>No places in this filter.</Text>
        )}
        <Pressable style={styles.fab} onPress={() => router.push('/new-place')}>
          <Text style={styles.fabLabel}>Add a place</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#1A1F18',
  },
  overlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
  },
  top: {
    marginHorizontal: 12,
    marginTop: 4,
    padding: 12,
    borderRadius: 20,
    backgroundColor: 'rgba(243, 237, 227, 0.94)',
    gap: 6,
  },
  brand: {
    fontFamily: fonts.serif,
    fontSize: 28,
    color: colors.ink,
  },
  sub: {
    fontFamily: fonts.sans,
    fontSize: 13,
    color: colors.muted,
    marginBottom: 4,
  },
  bottom: {
    position: 'absolute',
    left: 12,
    right: 12,
    bottom: 12,
    gap: 10,
  },
  empty: {
    color: colors.paper,
    textAlign: 'center',
    fontFamily: fonts.sans,
  },
  fab: {
    alignSelf: 'flex-end',
    backgroundColor: colors.forest,
    borderRadius: 999,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  fabLabel: {
    color: colors.white,
    fontFamily: fonts.sans,
    fontWeight: '700',
  },
});
