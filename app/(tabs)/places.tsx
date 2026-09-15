import * as Haptics from 'expo-haptics';
import { router } from 'expo-router';
import { useMemo, useState } from 'react';
import { FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { FilterChips } from '@/src/components/FilterChips';
import { PlaceRow } from '@/src/components/PlaceRow';
import { hasGoogleMapsKey } from '@/src/lib/googleMapsKey';
import { useBordbok } from '@/src/store';
import { colors, fonts, layout } from '@/src/theme';
import type { VisitFilter } from '@/src/types';

export default function PlacesScreen() {
  const lists = useBordbok((state) => state.lists);
  const places = useBordbok((state) => state.places);
  const toggleVisited = useBordbok((state) => state.toggleVisited);
  const [listFilter, setListFilter] = useState('all');
  const [visitFilter, setVisitFilter] = useState<VisitFilter>('all');

  const visible = useMemo(() => {
    return places
      .filter((place) => (listFilter === 'all' ? true : place.listId === listFilter))
      .filter((place) => {
        if (visitFilter === 'visited') return place.visited;
        if (visitFilter === 'to-try') return !place.visited;
        return true;
      })
      .sort((a, b) => Number(a.visited) - Number(b.visited) || a.name.localeCompare(b.name, 'nb'));
  }, [listFilter, places, visitFilter]);

  return (
    <SafeAreaView style={layout.screen} edges={['top']}>
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <Text style={layout.title}>Places</Text>
          <Pressable onPress={() => router.push('/new-place')} style={styles.add}>
            <Text style={styles.addLabel}>Add</Text>
          </Pressable>
        </View>
        <Text style={layout.subtitle}>
          {hasGoogleMapsKey()
            ? 'Covers come from Google Maps. Check off visits from the photo row.'
            : 'Add EXPO_PUBLIC_GOOGLE_MAPS_API_KEY to load Google Maps photos in this list.'}
        </Text>
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
      </View>
      <FlatList
        data={visible}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.list}
        ListEmptyComponent={<Text style={styles.empty}>No places in this filter yet.</Text>}
        renderItem={({ item }) => {
          const list = lists.find((entry) => entry.id === item.listId);
          return (
            <PlaceRow
              place={item}
              accent={list?.accent ?? colors.forest}
              onOpen={() => router.push(`/place/${item.id}`)}
              onToggleVisited={() => {
                void Haptics.selectionAsync();
                toggleVisited(item.id);
              }}
            />
          );
        }}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  header: {
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 8,
  },
  titleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  add: {
    backgroundColor: colors.forest,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 999,
  },
  addLabel: {
    color: colors.white,
    fontFamily: fonts.sans,
    fontWeight: '700',
  },
  chips: {
    marginTop: 16,
    gap: 8,
  },
  list: {
    paddingHorizontal: 16,
    paddingBottom: 40,
    gap: 12,
  },
  empty: {
    fontFamily: fonts.sans,
    color: colors.muted,
    textAlign: 'center',
    marginTop: 40,
  },
});
