import * as ImagePicker from 'expo-image-picker';

export async function pickPlacePhoto(): Promise<string | undefined> {
  const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
  if (!permission.granted) {
    return undefined;
  }

  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ['images'],
    quality: 0.55,
    allowsEditing: true,
    aspect: [4, 3],
    base64: true,
  });

  if (result.canceled) {
    return undefined;
  }

  const asset = result.assets[0];
  if (asset.base64) {
    const mime = asset.mimeType ?? 'image/jpeg';
    return `data:${mime};base64,${asset.base64}`;
  }
  return asset.uri;
}
