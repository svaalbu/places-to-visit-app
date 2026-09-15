import { Platform, StyleSheet } from 'react-native';

export const colors = {
  paper: '#F3EDE3',
  paperDeep: '#E7DDD0',
  card: '#FFFBF5',
  ink: '#1F1A16',
  muted: '#7A7068',
  line: '#E2D6C8',
  forest: '#2C4A3E',
  copper: '#C4622D',
  visited: '#0B8A4B',
  white: '#FFFFFF',
  overlay: 'rgba(31, 26, 22, 0.45)',
};

export const fonts = {
  serif: Platform.select({
    ios: 'Georgia',
    android: 'serif',
    default: 'Georgia, "Times New Roman", serif',
  }) as string,
  sans: Platform.select({
    ios: 'System',
    android: 'sans-serif',
    default: 'ui-sans-serif, system-ui, -apple-system, sans-serif',
  }) as string,
};

export const layout = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.paper,
  },
  padded: {
    paddingHorizontal: 20,
  },
  card: {
    backgroundColor: colors.card,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: colors.line,
    padding: 18,
  },
  title: {
    fontFamily: fonts.serif,
    fontSize: 34,
    lineHeight: 40,
    color: colors.ink,
    letterSpacing: -0.6,
  },
  subtitle: {
    fontFamily: fonts.sans,
    fontSize: 15,
    lineHeight: 22,
    color: colors.muted,
  },
  sectionLabel: {
    fontFamily: fonts.sans,
    fontSize: 12,
    letterSpacing: 1.4,
    textTransform: 'uppercase',
    color: colors.muted,
    fontWeight: '600',
  },
});
