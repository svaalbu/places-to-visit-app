import MapView, { Marker, type Region } from 'react-native-maps';
import { StyleSheet, View } from 'react-native';

import { OSLO_REGION, type Place } from '@/src/types';

type Props = {
  places: Place[];
  accentFor: (place: Place) => string;
  onSelect: (placeId: string) => void;
};

export function PlaceMap({ places, accentFor, onSelect }: Props) {
  const region: Region = OSLO_REGION;

  return (
    <MapView style={styles.map} initialRegion={region} mapType="standard">
      {places.map((place) => {
        const accent = accentFor(place);
        return (
          <Marker
            key={place.id}
            coordinate={{ latitude: place.latitude, longitude: place.longitude }}
            onPress={() => onSelect(place.id)}
            tracksViewChanges={false}
            title={place.name}
            description={place.visited ? 'Visited' : 'Still to try'}>
            <View
              style={[
                styles.pin,
                {
                  borderColor: accent,
                  backgroundColor: place.visited ? accent : '#FFFBF5',
                },
              ]}
            />
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
    width: 16,
    height: 16,
    borderRadius: 8,
    borderWidth: 2.5,
  },
});
