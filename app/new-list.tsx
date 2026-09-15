import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { useBordbok } from '@/src/store';
import { colors, fonts, layout } from '@/src/theme';

const PRESETS = ['#6B4A32', '#6E2430', '#2F4A6E', '#2C4A3E', '#C4622D', '#4A3B6E'];

export default function NewListScreen() {
  const addList = useBordbok((state) => state.addList);
  const [name, setName] = useState('');
  const [subtitle, setSubtitle] = useState('');
  const [accent, setAccent] = useState(PRESETS[0]);

  const save = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    const id = addList({
      name: trimmed,
      subtitle: subtitle.trim() || 'A new collection',
      accent,
    });
    router.replace(`/list/${id}`);
  };

  return (
    <View style={[layout.screen, styles.wrap]}>
      <Text style={styles.label}>List name</Text>
      <TextInput
        value={name}
        onChangeText={setName}
        placeholder="Wine bars, bakeries, pizza…"
        placeholderTextColor={colors.muted}
        style={styles.input}
      />
      <Text style={styles.label}>Short description</Text>
      <TextInput
        value={subtitle}
        onChangeText={setSubtitle}
        placeholder="What belongs on this list"
        placeholderTextColor={colors.muted}
        style={styles.input}
      />
      <Text style={styles.label}>Color</Text>
      <View style={styles.swatches}>
        {PRESETS.map((color) => (
          <Pressable
            key={color}
            onPress={() => setAccent(color)}
            style={[
              styles.swatch,
              { backgroundColor: color },
              accent === color && styles.swatchOn,
            ]}
          />
        ))}
      </View>
      <Pressable onPress={save} disabled={!name.trim()} style={[styles.save, !name.trim() && styles.disabled]}>
        <Text style={styles.saveLabel}>Create list</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    padding: 20,
  },
  label: {
    fontFamily: fonts.sans,
    fontSize: 12,
    letterSpacing: 1.2,
    textTransform: 'uppercase',
    color: colors.muted,
    fontWeight: '700',
    marginTop: 16,
    marginBottom: 8,
  },
  input: {
    backgroundColor: colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.line,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontFamily: fonts.sans,
    fontSize: 16,
    color: colors.ink,
  },
  swatches: {
    flexDirection: 'row',
    gap: 10,
  },
  swatch: {
    width: 36,
    height: 36,
    borderRadius: 18,
  },
  swatchOn: {
    borderWidth: 3,
    borderColor: colors.ink,
  },
  save: {
    marginTop: 32,
    backgroundColor: colors.ink,
    borderRadius: 16,
    alignItems: 'center',
    paddingVertical: 14,
  },
  disabled: {
    opacity: 0.4,
  },
  saveLabel: {
    color: colors.white,
    fontWeight: '700',
  },
});
