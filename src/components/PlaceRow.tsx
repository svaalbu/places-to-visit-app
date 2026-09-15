import { Pressable, StyleSheet, Text, View } from 'react-native';

import { PlaceCover } from '@/src/components/PlaceCover';
import { formatGoogleRating } from '@/src/lib/placeMedia';
import { colors, fonts } from '@/src/theme';
import type { Place } from '@/src/types';

type Props = {
  place: Place;
  accent: string;
  onOpen: () => void;
  onToggleVisited: () => void;
};

export function PlaceRow({ place, accent, onOpen, onToggleVisited }: Props) {
  const rating = formatGoogleRating(place);

  return (
    <Pressable onPress={onOpen} style={({ pressed }) => [styles.row, pressed && styles.pressed]}>
      <PlaceCover place={place} accent={accent} style={styles.photo} />
      <View style={styles.body}>
        <Text style={styles.name} numberOfLines={1}>
          {place.name}
        </Text>
        <Text style={styles.meta} numberOfLines={1}>
          {place.neighborhood}
          {rating ? ` · Google ${place.googleRating?.toFixed(1)}` : ''}
        </Text>
        {place.visited ? (
          <Text style={styles.been}>Visited</Text>
        ) : (
          <Text style={styles.toTry}>Still to try</Text>
        )}
        <Pressable
          onPress={onToggleVisited}
          hitSlop={8}
          accessibilityRole="checkbox"
          accessibilityState={{ checked: place.visited }}
          accessibilityLabel={place.visited ? 'Mark as not visited' : 'Mark as visited'}
          style={styles.check}>
          <View
            style={[
              styles.box,
              { borderColor: place.visited ? colors.visited : accent },
              place.visited && { backgroundColor: colors.visited },
            ]}>
            {place.visited ? <Text style={styles.tick}>✓</Text> : null}
          </View>
          <Text style={[styles.checkLabel, place.visited && { color: colors.visited }]}>
            {place.visited ? 'Visited' : 'Check off'}
          </Text>
        </Pressable>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 20,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: colors.line,
    minHeight: 112,
  },
  pressed: {
    opacity: 0.85,
  },
  photo: {
    width: 112,
    minHeight: 112,
    alignSelf: 'stretch',
  },
  body: {
    flex: 1,
    paddingHorizontal: 14,
    paddingVertical: 12,
    justifyContent: 'center',
  },
  name: {
    fontFamily: fonts.serif,
    fontSize: 20,
    color: colors.ink,
  },
  meta: {
    fontFamily: fonts.sans,
    fontSize: 13,
    color: colors.muted,
    marginTop: 2,
  },
  been: {
    fontFamily: fonts.sans,
    fontSize: 12,
    fontWeight: '800',
    color: colors.visited,
    marginTop: 4,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  toTry: {
    fontFamily: fonts.sans,
    fontSize: 12,
    fontWeight: '700',
    color: colors.muted,
    marginTop: 4,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  check: {
    marginTop: 8,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    alignSelf: 'flex-start',
  },
  box: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.card,
  },
  tick: {
    color: colors.white,
    fontSize: 12,
    fontWeight: '700',
    marginTop: -1,
  },
  checkLabel: {
    fontFamily: fonts.sans,
    fontSize: 13,
    fontWeight: '700',
    color: colors.forest,
  },
});
