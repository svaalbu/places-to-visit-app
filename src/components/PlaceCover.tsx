import { Image } from 'expo-image';
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';

import { useCoverPhoto } from '@/src/lib/placeMedia';
import { colors, fonts } from '@/src/theme';
import type { Place } from '@/src/types';

type Props = {
  place: Place;
  accent: string;
  style?: StyleProp<ViewStyle>;
};

export function PlaceCover({ place, accent, style }: Props) {
  const photo = useCoverPhoto(place);

  return (
    <View style={[styles.frame, { backgroundColor: accent }, style]}>
      {photo ? (
        <Image source={{ uri: photo }} style={StyleSheet.absoluteFill} contentFit="cover" />
      ) : (
        <Text style={styles.initial}>{place.name.slice(0, 1)}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  frame: {
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  initial: {
    fontFamily: fonts.serif,
    fontSize: 28,
    color: colors.white,
  },
});
