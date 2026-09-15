import { Link, Stack } from 'expo-router';
import { StyleSheet, Text, View } from 'react-native';

import { colors, fonts, layout } from '@/src/theme';

export default function NotFoundScreen() {
  return (
    <>
      <Stack.Screen options={{ title: 'Missing' }} />
      <View style={[layout.screen, styles.wrap]}>
        <Text style={styles.title}>This page is not in Bordbok.</Text>
        <Link href="/" style={styles.link}>
          <Text style={styles.linkText}>Back to lists</Text>
        </Link>
      </View>
    </>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  title: {
    fontFamily: fonts.serif,
    fontSize: 24,
    color: colors.ink,
    textAlign: 'center',
  },
  link: {
    marginTop: 16,
  },
  linkText: {
    color: colors.forest,
    fontWeight: '700',
  },
});
