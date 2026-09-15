import { ThemeProvider, DefaultTheme, Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Platform, StyleSheet, View } from 'react-native';
import 'react-native-reanimated';

import { colors } from '@/src/theme';

export { ErrorBoundary } from 'expo-router';

export const unstable_settings = {
  initialRouteName: '(tabs)',
};

const journalTheme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    background: colors.paper,
    card: colors.paper,
    text: colors.ink,
    border: colors.line,
    primary: colors.forest,
  },
};

export default function RootLayout() {
  const frame = Platform.OS === 'web';

  return (
    <ThemeProvider value={journalTheme}>
      <View style={frame ? styles.webPage : styles.fill}>
        <View style={frame ? styles.phone : styles.fill}>
          <Stack
            screenOptions={{
              headerShadowVisible: false,
              headerTintColor: colors.ink,
              headerStyle: { backgroundColor: colors.paper },
              headerTitleStyle: { fontWeight: '600' },
              contentStyle: { backgroundColor: colors.paper },
            }}>
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="list/[id]" options={{ title: 'List' }} />
            <Stack.Screen name="place/[id]" options={{ title: 'Place' }} />
            <Stack.Screen name="new-place" options={{ title: 'Add place', presentation: 'modal' }} />
            <Stack.Screen name="new-list" options={{ title: 'New list', presentation: 'modal' }} />
          </Stack>
          <StatusBar style="dark" />
        </View>
      </View>
    </ThemeProvider>
  );
}

const styles = StyleSheet.create({
  fill: {
    flex: 1,
    backgroundColor: colors.paper,
  },
  webPage: {
    flex: 1,
    backgroundColor: '#1C1814',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 24,
  },
  phone: {
    width: '100%',
    maxWidth: 430,
    flex: 1,
    maxHeight: 900,
    backgroundColor: colors.paper,
    overflow: 'hidden',
    borderRadius: 28,
    borderWidth: 1,
    borderColor: '#3A322C',
  },
});
