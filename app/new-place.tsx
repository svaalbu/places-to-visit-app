import { router, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
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

import { FilterChips } from '@/src/components/FilterChips';
import { searchOsloPlaces, type GeoHit } from '@/src/lib/nominatim';
import { pickPlacePhoto } from '@/src/lib/photo';
import { useBordbok } from '@/src/store';
import { colors, fonts, layout } from '@/src/theme';
import { OSLO_REGION } from '@/src/types';

export default function NewPlaceScreen() {
  const params = useLocalSearchParams<{ listId?: string }>();
  const lists = useBordbok((state) => state.lists);
  const addPlace = useBordbok((state) => state.addPlace);
  const [listId, setListId] = useState(params.listId || lists[0]?.id || '');
  const [name, setName] = useState('');
  const [neighborhood, setNeighborhood] = useState('');
  const [address, setAddress] = useState('');
  const [note, setNote] = useState('');
  const [photoUri, setPhotoUri] = useState<string | undefined>();
  const [coords, setCoords] = useState({
    latitude: OSLO_REGION.latitude,
    longitude: OSLO_REGION.longitude,
  });
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<GeoHit[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSave = name.trim().length > 1 && listId;

  const listChips = useMemo(
    () => lists.map((list) => ({ key: list.id, label: list.name })),
    [lists],
  );

  const runSearch = async () => {
    setSearching(true);
    setError(null);
    try {
      const results = await searchOsloPlaces(query || name);
      setHits(results);
      if (results.length === 0) {
        setError('No Oslo match. You can still save with a typed address.');
      }
    } catch {
      setError('Search is unavailable. Save with the address you typed.');
    } finally {
      setSearching(false);
    }
  };

  const applyHit = (hit: GeoHit) => {
    setName(hit.name);
    setAddress(hit.address);
    setCoords({ latitude: hit.latitude, longitude: hit.longitude });
    setHits([]);
  };

  const save = () => {
    if (!canSave) return;
    const id = addPlace({
      listId,
      name: name.trim(),
      neighborhood: neighborhood.trim() || 'Oslo',
      address: address.trim() || 'Oslo',
      latitude: coords.latitude,
      longitude: coords.longitude,
      visited: false,
      note: note.trim(),
      photoUri,
      coverPhotoUrl: photoUri,
    });
    router.replace(`/place/${id}`);
  };

  return (
    <KeyboardAvoidingView
      style={layout.screen}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.label}>List</Text>
        <FilterChips chips={listChips} selected={listId} onSelect={setListId} />

        <Text style={styles.label}>Search Oslo</Text>
        <View style={styles.searchRow}>
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Tim Wendelboe, Speilsalen…"
            placeholderTextColor={colors.muted}
            style={[styles.input, styles.searchInput]}
            onSubmitEditing={() => void runSearch()}
          />
          <Pressable onPress={() => void runSearch()} style={styles.searchBtn}>
            <Text style={styles.searchBtnLabel}>{searching ? '…' : 'Find'}</Text>
          </Pressable>
        </View>
        {hits.map((hit) => (
          <Pressable key={`${hit.name}-${hit.latitude}`} onPress={() => applyHit(hit)} style={styles.hit}>
            <Text style={styles.hitName}>{hit.name}</Text>
            <Text style={styles.hitAddr}>{hit.address}</Text>
          </Pressable>
        ))}
        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Text style={styles.label}>Name</Text>
        <TextInput
          value={name}
          onChangeText={setName}
          placeholder="Café or restaurant"
          placeholderTextColor={colors.muted}
          style={styles.input}
        />
        <Text style={styles.label}>Neighborhood</Text>
        <TextInput
          value={neighborhood}
          onChangeText={setNeighborhood}
          placeholder="Grünerløkka, Frogner, Bjørvika…"
          placeholderTextColor={colors.muted}
          style={styles.input}
        />
        <Text style={styles.label}>Address</Text>
        <TextInput
          value={address}
          onChangeText={setAddress}
          placeholder="Street and number"
          placeholderTextColor={colors.muted}
          style={styles.input}
        />
        <Text style={styles.label}>Note (optional)</Text>
        <TextInput
          value={note}
          onChangeText={setNote}
          placeholder="A sentence from the visit, or why it’s on the list"
          placeholderTextColor={colors.muted}
          style={[styles.input, styles.multiline]}
          multiline
        />
        <Pressable
          onPress={async () => {
            const uri = await pickPlacePhoto();
            if (uri) setPhotoUri(uri);
          }}
          style={styles.secondary}>
          <Text style={styles.secondaryLabel}>{photoUri ? 'Photo added · change' : 'Add a photo'}</Text>
        </Pressable>

        <Pressable onPress={save} disabled={!canSave} style={[styles.save, !canSave && styles.disabled]}>
          <Text style={styles.saveLabel}>Save to Bordbok</Text>
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: 20,
    paddingBottom: 48,
    gap: 4,
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
  multiline: {
    minHeight: 90,
    textAlignVertical: 'top',
  },
  searchRow: {
    flexDirection: 'row',
    gap: 8,
  },
  searchInput: {
    flex: 1,
  },
  searchBtn: {
    backgroundColor: colors.forest,
    borderRadius: 14,
    paddingHorizontal: 16,
    justifyContent: 'center',
  },
  searchBtnLabel: {
    color: colors.white,
    fontWeight: '700',
  },
  hit: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 12,
    marginTop: 8,
    borderWidth: 1,
    borderColor: colors.line,
  },
  hitName: {
    fontFamily: fonts.serif,
    fontSize: 16,
    color: colors.ink,
  },
  hitAddr: {
    fontFamily: fonts.sans,
    color: colors.muted,
    marginTop: 2,
  },
  error: {
    color: colors.copper,
    marginTop: 8,
    fontFamily: fonts.sans,
  },
  secondary: {
    marginTop: 12,
  },
  secondaryLabel: {
    color: colors.forest,
    fontWeight: '700',
  },
  save: {
    marginTop: 24,
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
    fontFamily: fonts.sans,
  },
});
