import * as Haptics from 'expo-haptics';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { confirmAction } from '@/src/lib/confirm';

import { PlaceRow } from '@/src/components/PlaceRow';
import { placesForList, useBordbok, visitedCount } from '@/src/store';
import { colors, fonts, layout } from '@/src/theme';

export default function ListDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const lists = useBordbok((state) => state.lists);
  const places = useBordbok((state) => state.places);
  const toggleVisited = useBordbok((state) => state.toggleVisited);
  const deleteList = useBordbok((state) => state.deleteList);
  const list = lists.find((entry) => entry.id === id);

  if (!list) {
    return (
      <View style={layout.screen}>
        <Text style={styles.missing}>That list is gone.</Text>
      </View>
    );
  }

  const items = placesForList(places, list.id);
  const counts = visitedCount(places, list.id);

  const confirmDelete = () => {
    confirmAction(`Delete ${list.name}?`, 'Places in this list will be removed from Bordbok.', () => {
      deleteList(list.id);
      router.back();
    });
  };

  return (
    <View style={layout.screen}>
      <Stack.Screen
        options={{
          title: list.name,
          headerRight: () => (
            <Pressable onPress={confirmDelete}>
              <Text style={styles.delete}>Delete</Text>
            </Pressable>
          ),
        }}
      />
      <ScrollView contentContainerStyle={styles.content}>
        <View style={[styles.hero, { borderLeftColor: list.accent }]}>
          <Text style={layout.subtitle}>{list.subtitle}</Text>
          <Text style={styles.count}>
            {counts.visited} of {counts.total} visited
          </Text>
        </View>
        <Pressable
          style={styles.add}
          onPress={() => router.push({ pathname: '/new-place', params: { listId: list.id } })}>
          <Text style={styles.addLabel}>Add a place to {list.name}</Text>
        </Pressable>
        {items.map((place) => (
          <View key={place.id} style={styles.rowWrap}>
            <PlaceRow
              place={place}
              accent={list.accent}
              onOpen={() => router.push(`/place/${place.id}`)}
              onToggleVisited={() => {
                void Haptics.selectionAsync();
                toggleVisited(place.id);
              }}
            />
          </View>
        ))}
        {items.length === 0 ? (
          <Text style={styles.empty}>This list is empty. Add the first café or restaurant.</Text>
        ) : null}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingHorizontal: 20,
    paddingBottom: 40,
  },
  hero: {
    borderLeftWidth: 6,
    paddingLeft: 14,
    marginTop: 12,
    marginBottom: 18,
  },
  count: {
    fontFamily: fonts.serif,
    fontSize: 22,
    color: colors.ink,
    marginTop: 8,
  },
  add: {
    backgroundColor: colors.forest,
    borderRadius: 16,
    paddingVertical: 14,
    alignItems: 'center',
    marginBottom: 12,
  },
  addLabel: {
    color: colors.white,
    fontFamily: fonts.sans,
    fontWeight: '700',
  },
  rowWrap: {
    marginBottom: 12,
  },
  empty: {
    fontFamily: fonts.sans,
    color: colors.muted,
    marginTop: 24,
  },
  missing: {
    fontFamily: fonts.sans,
    color: colors.muted,
    padding: 24,
  },
  delete: {
    color: colors.copper,
    fontWeight: '700',
  },
});
