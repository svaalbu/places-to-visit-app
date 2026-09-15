import * as Haptics from 'expo-haptics';
import { router } from 'expo-router';
import { useCallback, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { FilterChips } from '@/src/components/FilterChips';
import { PlaceMap } from '@/src/components/PlaceMap';
import { VisitLegend } from '@/src/components/VisitLegend';
import { useBordbok } from '@/src/store';
import { colors, fonts, layout } from '@/src/theme';
import type { Place, VisitFilter } from '@/src/types';

export default function MapScreen() {
  const lists = useBordbok((state) => state.lists);
  const places = useBordbok((state) => state.places);
  const [listFilter, setListFilter] = useState('all');
  const [visitFilter, setVisitFilter] = useState<VisitFilter>('all');

  const visible = useMemo(() => {
    return places.filter((place) => {
      const listOk = listFilter === 'all' || place.listId === listFilter;
      const visitOk =
        visitFilter === 'all' || (visitFilter === 'visited' ? place.visited : !place.visited);
      return listOk && visitOk;
    });
  }, [listFilter, places, visitFilter]);

  const accentFor = useCallback(
    (place: Place) => lists.find((list) => list.id === place.listId)?.accent ?? colors.forest,
    [lists],
  );

  return (
    <SafeAreaView style={layout.screen} edges={['top']}>
      <View style={styles.header}>
        <Text style={layout.title}>Oslo map</Text>
        <Text style={layout.subtitle}>Filled pins are places you have checked off.</Text>
        <View style={styles.chips}>
          <FilterChips
            selected={listFilter}
            onSelect={setListFilter}
            chips={[
              { key: 'all', label: 'All lists' },
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
        <View style={styles.legend}>
          <VisitLegend visited accent={colors.copper} />
          <VisitLegend visited={false} accent={colors.forest} />
          <Text style={styles.count}>{visible.length} on map</Text>
        </View>
      </View>
      <View style={styles.mapCard}>
        <PlaceMap
          places={visible}
          accentFor={accentFor}
          onSelect={(id) => {
            void Haptics.selectionAsync();
            router.push(`/place/${id}`);
          }}
        />
      </View>
      <Pressable style={styles.fab} onPress={() => router.push('/new-place')}>
        <Text style={styles.fabLabel}>Add a place</Text>
      </Pressable>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  header: {
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 12,
  },
  chips: {
    marginTop: 12,
    gap: 8,
  },
  legend: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    marginTop: 12,
  },
  count: {
    marginLeft: 'auto',
    fontFamily: fonts.sans,
    fontSize: 12,
    color: colors.muted,
    fontWeight: '600',
  },
  mapCard: {
    flex: 1,
    marginHorizontal: 16,
    marginBottom: 20,
    borderRadius: 24,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: colors.line,
  },
  fab: {
    position: 'absolute',
    right: 28,
    bottom: 28,
    backgroundColor: colors.forest,
    borderRadius: 999,
    paddingHorizontal: 18,
    paddingVertical: 12,
  },
  fabLabel: {
    color: colors.white,
    fontFamily: fonts.sans,
    fontWeight: '700',
  },
});
