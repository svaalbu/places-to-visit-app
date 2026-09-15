import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, fonts } from '@/src/theme';
import type { Place } from '@/src/types';

type Props = {
  place: Place;
  accent: string;
  onOpen: () => void;
  onToggleVisited: () => void;
};

export function PlaceRow({ place, accent, onOpen, onToggleVisited }: Props) {
  return (
    <Pressable onPress={onOpen} style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
      <Pressable
        onPress={onToggleVisited}
        hitSlop={8}
        accessibilityRole="checkbox"
        accessibilityState={{ checked: place.visited }}
        accessibilityLabel={place.visited ? 'Mark as not visited' : 'Mark as visited'}
        style={[
          styles.check,
          { borderColor: accent },
          place.visited && { backgroundColor: accent },
        ]}>
        {place.visited ? <Text style={styles.tick}>✓</Text> : null}
      </Pressable>
      <View style={styles.body}>
        <Text style={styles.name}>{place.name}</Text>
        <Text style={styles.meta}>
          {place.neighborhood}
          {place.note ? ' · note' : ''}
          {place.photoUri ? ' · photo' : ''}
        </Text>
      </View>
      <Text style={[styles.status, place.visited && { color: accent }]}>
        {place.visited ? 'Been' : 'To try'}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 14,
    paddingHorizontal: 4,
  },
  pressed: {
    opacity: 0.7,
  },
  check: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.card,
  },
  tick: {
    color: colors.white,
    fontSize: 14,
    fontWeight: '700',
    marginTop: -1,
  },
  body: {
    flex: 1,
  },
  name: {
    fontFamily: fonts.serif,
    fontSize: 18,
    color: colors.ink,
  },
  meta: {
    fontFamily: fonts.sans,
    fontSize: 13,
    color: colors.muted,
    marginTop: 2,
  },
  status: {
    fontFamily: fonts.sans,
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.4,
    color: colors.muted,
    textTransform: 'uppercase',
  },
});
