import { Pressable, StyleSheet, Text, View } from 'react-native';

import { PlaceCover } from '@/src/components/PlaceCover';
import { colors, fonts } from '@/src/theme';
import type { Place, PlaceList } from '@/src/types';

type Props = {
  list: PlaceList;
  places: Place[];
  visited: number;
  total: number;
  onPress: () => void;
};

export function ListCard({ list, places, visited, total, onPress }: Props) {
  const ratio = total === 0 ? 0 : visited / total;
  const covers = places.slice(0, 3);

  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.card, pressed && styles.pressed]}>
      <View style={styles.mosaic}>
        {covers.length === 0 ? (
          <View style={[styles.photo, { backgroundColor: list.accent }]} />
        ) : (
          covers.map((place) => (
            <PlaceCover key={place.id} place={place} accent={list.accent} style={styles.photo} />
          ))
        )}
      </View>
      <View style={styles.body}>
        <Text style={styles.kicker}>{total} places</Text>
        <Text style={styles.name}>{list.name}</Text>
        <Text style={styles.subtitle} numberOfLines={2}>
          {list.subtitle}
        </Text>
        <View style={styles.track}>
          <View style={[styles.fill, { width: `${Math.round(ratio * 100)}%`, backgroundColor: list.accent }]} />
        </View>
        <Text style={styles.progress}>
          {visited} visited · {Math.max(total - visited, 0)} still to try
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.line,
    overflow: 'hidden',
    flexDirection: 'row',
    minHeight: 148,
  },
  pressed: {
    transform: [{ scale: 0.99 }],
    opacity: 0.94,
  },
  mosaic: {
    width: 108,
    alignSelf: 'stretch',
  },
  photo: {
    flex: 1,
    width: '100%',
  },
  body: {
    flex: 1,
    paddingHorizontal: 18,
    paddingVertical: 18,
  },
  kicker: {
    fontFamily: fonts.sans,
    fontSize: 12,
    letterSpacing: 1.3,
    textTransform: 'uppercase',
    color: colors.muted,
    fontWeight: '600',
  },
  name: {
    fontFamily: fonts.serif,
    fontSize: 28,
    color: colors.ink,
    marginTop: 6,
  },
  subtitle: {
    fontFamily: fonts.sans,
    fontSize: 14,
    color: colors.muted,
    marginTop: 4,
    marginBottom: 16,
  },
  track: {
    height: 6,
    borderRadius: 99,
    backgroundColor: colors.paperDeep,
    overflow: 'hidden',
  },
  fill: {
    height: 6,
    borderRadius: 99,
  },
  progress: {
    fontFamily: fonts.sans,
    fontSize: 13,
    color: colors.ink,
    marginTop: 10,
  },
});
