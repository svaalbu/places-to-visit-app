import { Image } from 'expo-image';
import MapView, { Marker, type Region } from 'react-native-maps';
import { StyleSheet, Text, View } from 'react-native';

import { useGooglePhotoMap } from '@/src/lib/googleMapsPhotos';
import { coverPhoto } from '@/src/lib/placeMedia';
import { colors } from '@/src/theme';
import { OSLO_REGION, type Place } from '@/src/types';

type Props = {
  places: Place[];
  accentFor: (place: Place) => string;
  selectedId?: string;
  onSelect: (placeId: string) => void;
};

export function PlaceMap({ places, accentFor, selectedId, onSelect }: Props) {
  const region: Region = OSLO_REGION;
  const googleById = useGooglePhotoMap((state) => state.byId);

  return (
    <MapView
      style={styles.map}
      initialRegion={region}
      mapType="hybrid"
      userInterfaceStyle="light">
      {places.map((place) => {
        const accent = accentFor(place);
        const photo = coverPhoto(place, googleById[place.id]);
        const selected = place.id === selectedId;
        const size = selected ? 52 : 44;
        return (
          <Marker
            key={`${place.id}-${place.visited ? 'in' : 'out'}`}
            coordinate={{ latitude: place.latitude, longitude: place.longitude }}
            onPress={() => onSelect(place.id)}
            tracksViewChanges
            title={place.name}
            description={place.visited ? 'Visited' : 'Still to try'}>
            <View style={styles.wrap}>
              <View
                style={[
                  styles.pin,
                  {
                    width: size,
                    height: size,
                    borderColor: place.visited ? colors.visited : accent,
                    borderWidth: place.visited ? 3 : 2,
                  },
                ]}>
                {photo ? (
                  <Image source={{ uri: photo }} style={styles.thumb} contentFit="cover" />
                ) : (
                  <View style={[styles.fallback, { backgroundColor: accent }]} />
                )}
                {!place.visited ? <View style={styles.dim} /> : null}
              </View>
              {place.visited ? (
                <View style={styles.badge}>
                  <Text style={styles.badgeMark}>✓</Text>
                </View>
              ) : null}
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
  wrap: {
    width: 58,
    height: 58,
    alignItems: 'center',
    justifyContent: 'center',
  },
  pin: {
    borderRadius: 14,
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
  dim: {
    ...StyleSheet.absoluteFill,
    backgroundColor: 'rgba(20,16,12,0.45)',
  },
  badge: {
    position: 'absolute',
    right: 0,
    bottom: 0,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.visited,
    borderWidth: 2,
    borderColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeMark: {
    color: colors.white,
    fontSize: 13,
    fontWeight: '800',
    marginTop: -1,
  },
});
