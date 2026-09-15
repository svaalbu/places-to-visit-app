import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, fonts } from '@/src/theme';
import type { PlaceList } from '@/src/types';

type Props = {
  list: PlaceList;
  visited: number;
  total: number;
  onPress: () => void;
};

export function ListCard({ list, visited, total, onPress }: Props) {
  const ratio = total === 0 ? 0 : visited / total;

  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.card, pressed && styles.pressed]}>
      <View style={[styles.stripe, { backgroundColor: list.accent }]} />
      <View style={styles.body}>
        <Text style={styles.kicker}>{total} places</Text>
        <Text style={styles.name}>{list.name}</Text>
        <Text style={styles.subtitle}>{list.subtitle}</Text>
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
  stripe: {
    width: 10,
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
