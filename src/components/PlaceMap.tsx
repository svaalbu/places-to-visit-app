import { Image } from 'expo-image';
import MapView, { Marker, type Region } from 'react-native-maps';
import { StyleSheet, View } from 'react-native';

import { coverPhoto } from '@/src/lib/placeMedia';
import { OSLO_REGION, type Place } from '@/src/types';

type Props = {
  places: Place[];
  accentFor: (place: Place) => string;
  selectedId?: string;
  onSelect: (placeId: string) => void;
};

export function PlaceMap({ places, accentFor, selectedId, onSelect }: Props) {
  const region: Region = OSLO_REGION;

  return (
    <MapView
      style={styles.map}
      initialRegion={region}
      mapType="hybrid"
      userInterfaceStyle="light">
      {places.map((place) => {
        const accent = accentFor(place);
        const photo = coverPhoto(place);
        const selected = place.id === selectedId;
        return (
          <Marker
            key={place.id}
            coordinate={{ latitude: place.latitude, longitude: place.longitude }}
            onPress={() => onSelect(place.id)}
            tracksViewChanges={Boolean(photo)}
            title={place.name}
            description={
              place.googleRating
                ? `Google ${place.googleRating.toFixed(1)} · ${place.visited ? 'Visited' : 'To try'}`
                : place.visited
                  ? 'Visited'
                  : 'To try'
            }>
            <View
              style={[
                styles.pin,
                { borderColor: accent, width: selected ? 52 : 44, height: selected ? 52 : 44 },
                place.visited && { borderWidth: 3 },
              ]}>
              {photo ? (
                <Image source={{ uri: photo }} style={styles.thumb} contentFit="cover" />
              ) : (
                <View style={[styles.fallback, { backgroundColor: accent }]} />
              )}
            </View>
          </Marker>
        );
      })}
    </MapView>
  );
}

const styles = StyleSheet.create({
  map: {
    flex: 1,
  },
  pin: {
    borderRadius: 14,
    borderWidth: 2.5,
    overflow: 'hidden',
    backgroundColor: '#1C1814',
  },
  thumb: {
    width: '100%',
    height: '100%',
  },
  fallback: {
    flex: 1,
  },
});
