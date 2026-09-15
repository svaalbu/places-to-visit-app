export function googleMapsApiKey(): string | undefined {
  const key = process.env.EXPO_PUBLIC_GOOGLE_MAPS_API_KEY?.trim();
  return key ? key : undefined;
}

export function hasGoogleMapsKey(): boolean {
  return Boolean(googleMapsApiKey());
}
