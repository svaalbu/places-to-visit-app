import { Pressable, ScrollView, StyleSheet, Text } from 'react-native';

import { colors, fonts } from '@/src/theme';

type Chip = {
  key: string;
  label: string;
};

type Props = {
  chips: Chip[];
  selected: string;
  onSelect: (key: string) => void;
};

export function FilterChips({ chips, selected, onSelect }: Props) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.row}>
      {chips.map((chip) => {
        const active = chip.key === selected;
        return (
          <Pressable
            key={chip.key}
            onPress={() => onSelect(chip.key)}
            style={[styles.chip, active && styles.active]}>
            <Text style={[styles.label, active && styles.activeLabel]}>{chip.label}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  row: {
    gap: 8,
    paddingVertical: 4,
  },
  chip: {
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.line,
  },
  active: {
    backgroundColor: colors.forest,
    borderColor: colors.forest,
  },
  label: {
    fontFamily: fonts.sans,
    fontSize: 13,
    color: colors.ink,
    fontWeight: '600',
  },
  activeLabel: {
    color: colors.white,
  },
});
