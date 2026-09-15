import * as Haptics from 'expo-haptics';
import { Image } from 'expo-image';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { confirmAction } from '@/src/lib/confirm';

import { pickPlacePhoto } from '@/src/lib/photo';
import { useBordbok } from '@/src/store';
import { colors, fonts, layout } from '@/src/theme';

export default function PlaceDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const lists = useBordbok((state) => state.lists);
  const places = useBordbok((state) => state.places);
  const updatePlace = useBordbok((state) => state.updatePlace);
  const toggleVisited = useBordbok((state) => state.toggleVisited);
  const deletePlace = useBordbok((state) => state.deletePlace);
  const place = places.find((entry) => entry.id === id);
  const [note, setNote] = useState(place?.note ?? '');

  useEffect(() => {
    setNote(place?.note ?? '');
  }, [place?.id, place?.note]);

  if (!place) {
    return (
      <View style={layout.screen}>
        <Text style={styles.missing}>That place is gone.</Text>
      </View>
    );
  }

  const list = lists.find((entry) => entry.id === place.listId);

  const saveNote = () => {
    updatePlace(place.id, { note });
  };

  const addPhoto = async () => {
    const uri = await pickPlacePhoto();
    if (uri) {
      updatePlace(place.id, { photoUri: uri });
    }
  };

  return (
    <KeyboardAvoidingView
      style={layout.screen}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Stack.Screen
        options={{
          title: place.name,
          headerRight: () => (
            <Pressable
              onPress={() => {
                confirmAction('Remove place?', place.name, () => {
                  deletePlace(place.id);
                  router.back();
                });
              }}>
              <Text style={styles.delete}>Remove</Text>
            </Pressable>
          ),
        }}
      />
      <ScrollView contentContainerStyle={styles.content}>
        <Pressable
          onPress={() => {
            void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
            toggleVisited(place.id);
          }}
          style={[
            styles.visit,
            { backgroundColor: place.visited ? list?.accent ?? colors.forest : colors.card },
            !place.visited && styles.visitOutline,
          ]}>
          <Text style={[styles.visitLabel, place.visited && styles.visitLabelOn]}>
            {place.visited ? 'Visited — tap to undo' : 'Check off as visited'}
          </Text>
          {place.visited && place.visitedAt ? (
            <Text style={styles.visitDate}>{place.visitedAt}</Text>
          ) : null}
        </Pressable>

        <Text style={styles.meta}>
          {list?.name} · {place.neighborhood}
        </Text>
        <Text style={styles.address}>{place.address}, Oslo</Text>

        <Text style={styles.section}>Photo from the table</Text>
        {place.photoUri ? (
          <Image source={{ uri: place.photoUri }} style={styles.photo} contentFit="cover" />
        ) : (
          <View style={styles.photoEmpty}>
            <Text style={styles.photoHint}>No photo yet</Text>
          </View>
        )}
        <Pressable onPress={() => void addPhoto()} style={styles.secondary}>
          <Text style={styles.secondaryLabel}>{place.photoUri ? 'Replace photo' : 'Add a photo'}</Text>
        </Pressable>

        <Text style={styles.section}>Short note</Text>
        <TextInput
          value={note}
          onChangeText={setNote}
          onBlur={saveNote}
          placeholder="What did you eat, who were you with, would you go back…"
          placeholderTextColor={colors.muted}
          multiline
          style={styles.note}
        />
        <Pressable onPress={saveNote} style={styles.save}>
          <Text style={styles.saveLabel}>Save note</Text>
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: 20,
    paddingBottom: 48,
  },
  visit: {
    borderRadius: 20,
    paddingVertical: 18,
    paddingHorizontal: 16,
    marginBottom: 16,
  },
  visitOutline: {
    borderWidth: 1.5,
    borderColor: colors.line,
  },
  visitLabel: {
    fontFamily: fonts.serif,
    fontSize: 22,
    color: colors.ink,
  },
  visitLabelOn: {
    color: colors.white,
  },
  visitDate: {
    fontFamily: fonts.sans,
    color: 'rgba(255,255,255,0.85)',
    marginTop: 4,
  },
  meta: {
    fontFamily: fonts.sans,
    color: colors.copper,
    fontWeight: '700',
    letterSpacing: 0.4,
    textTransform: 'uppercase',
    fontSize: 12,
  },
  address: {
    fontFamily: fonts.sans,
    fontSize: 16,
    color: colors.ink,
    marginTop: 6,
  },
  section: {
    fontFamily: fonts.sans,
    fontSize: 12,
    letterSpacing: 1.3,
    textTransform: 'uppercase',
    color: colors.muted,
    fontWeight: '700',
    marginTop: 28,
    marginBottom: 10,
  },
  photo: {
    width: '100%',
    height: 220,
    borderRadius: 18,
    backgroundColor: colors.paperDeep,
  },
  photoEmpty: {
    height: 140,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.line,
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.card,
  },
  photoHint: {
    color: colors.muted,
    fontFamily: fonts.sans,
  },
  secondary: {
    marginTop: 10,
    alignSelf: 'flex-start',
    paddingVertical: 8,
  },
  secondaryLabel: {
    color: colors.forest,
    fontWeight: '700',
    fontFamily: fonts.sans,
  },
  note: {
    minHeight: 120,
    backgroundColor: colors.card,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.line,
    padding: 14,
    fontFamily: fonts.sans,
    fontSize: 16,
    color: colors.ink,
    textAlignVertical: 'top',
  },
  save: {
    marginTop: 12,
    backgroundColor: colors.ink,
    borderRadius: 14,
    alignItems: 'center',
    paddingVertical: 12,
  },
  saveLabel: {
    color: colors.white,
    fontWeight: '700',
    fontFamily: fonts.sans,
  },
  missing: {
    padding: 24,
    color: colors.muted,
  },
  delete: {
    color: colors.copper,
    fontWeight: '700',
  },
});
