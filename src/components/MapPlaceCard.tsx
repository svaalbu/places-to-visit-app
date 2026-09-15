import { Image } from 'expo-image';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { coverPhoto, formatGoogleRating } from '@/src/lib/placeMedia';
import { colors, fonts } from '@/src/theme';
import type { Place, PlaceList } from '@/src/types';

type Props = {
  place: Place;
  list?: PlaceList;
  onOpen: () => void;
  onToggleVisited: () => void;
};

export function MapPlaceCard({ place, list, onOpen, onToggleVisited }: Props) {
  const photo = coverPhoto(place);
  const rating = formatGoogleRating(place);

  return (
    <Pressable onPress={onOpen} style={styles.card}>
      {photo ? (
        <Image source={{ uri: photo }} style={styles.photo} contentFit="cover" />
      ) : (
        <View style={[styles.photo, { backgroundColor: list?.accent ?? colors.forest }]} />
      )}
      <View style={styles.body}>
        <Text style={styles.kicker}>
          {list?.name}
          {rating ? ` · Google ${rating}` : ''}
        </Text>
        <Text style={styles.name} numberOfLines={1}>
          {place.name}
        </Text>
        {place.visited ? <Text style={styles.been}>Visited</Text> : <Text style={styles.toTry}>Still to try</Text>}
        <Text style={styles.meta} numberOfLines={1}>
          {place.neighborhood} · {place.address}
        </Text>
        <Pressable onPress={onToggleVisited} style={styles.check}>
          <Text style={[styles.checkLabel, place.visited && { color: colors.visited }]}>
            {place.visited ? 'Visited · tap to undo' : 'Check off visit'}
          </Text>
        </Pressable>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    backgroundColor: colors.card,
    borderRadius: 22,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: colors.line,
    minHeight: 118,
  },
  photo: {
    width: 118,
    height: '100%',
    minHeight: 118,
  },
  body: {
    flex: 1,
    padding: 12,
    justifyContent: 'center',
  },
  kicker: {
    fontFamily: fonts.sans,
    fontSize: 11,
    letterSpacing: 0.6,
    textTransform: 'uppercase',
    color: colors.copper,
    fontWeight: '700',
  },
  name: {
    fontFamily: fonts.serif,
    fontSize: 20,
    color: colors.ink,
    marginTop: 4,
  },
  been: {
    fontFamily: fonts.sans,
    fontSize: 13,
    fontWeight: '800',
    color: colors.visited,
    marginTop: 2,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  toTry: {
    fontFamily: fonts.sans,
    fontSize: 13,
    fontWeight: '700',
    color: colors.muted,
    marginTop: 2,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
  },
  meta: {
    fontFamily: fonts.sans,
    fontSize: 13,
    color: colors.muted,
    marginTop: 2,
  },
  check: {
    marginTop: 8,
    alignSelf: 'flex-start',
  },
  checkLabel: {
    fontFamily: fonts.sans,
    fontSize: 13,
    fontWeight: '700',
    color: colors.forest,
  },
});
