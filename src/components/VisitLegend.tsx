import { StyleSheet, Text, View } from 'react-native';

import { colors, fonts } from '@/src/theme';

type Props = {
  visited: boolean;
  accent: string;
};

export function VisitLegend({ visited, accent }: Props) {
  return (
    <View style={styles.row}>
      <View
        style={[
          styles.dot,
          { borderColor: accent, backgroundColor: visited ? accent : colors.card },
        ]}
      />
      <Text style={styles.label}>{visited ? 'Visited' : 'Still to try'}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  dot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    borderWidth: 2,
  },
  label: {
    fontFamily: fonts.sans,
    fontSize: 12,
    color: colors.muted,
    fontWeight: '600',
  },
});
