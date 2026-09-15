import { Link, router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ListCard } from '@/src/components/ListCard';
import { confirmAction } from '@/src/lib/confirm';
import { useBordbok, visitedCount } from '@/src/store';
import { colors, fonts, layout } from '@/src/theme';

export default function ListsScreen() {
  const lists = useBordbok((state) => state.lists);
  const places = useBordbok((state) => state.places);
  const restoreOsloStarter = useBordbok((state) => state.restoreOsloStarter);
  const totals = visitedCount(places);

  return (
    <SafeAreaView style={layout.screen} edges={['top']}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.kicker}>Oslo</Text>
        <Text style={layout.title}>Bordbok</Text>
        <Text style={[layout.subtitle, styles.lede]}>
          A notebook of restaurants and cafés. Check off the ones you have been to, leave a short
          note, and keep a photo from the table.
        </Text>

        <View style={styles.stats}>
          <View style={styles.stat}>
            <Text style={styles.statValue}>{totals.visited}</Text>
            <Text style={styles.statLabel}>visited</Text>
          </View>
          <View style={styles.stat}>
            <Text style={styles.statValue}>{Math.max(totals.total - totals.visited, 0)}</Text>
            <Text style={styles.statLabel}>to try</Text>
          </View>
          <View style={styles.stat}>
            <Text style={styles.statValue}>{lists.length}</Text>
            <Text style={styles.statLabel}>lists</Text>
          </View>
        </View>

        <View style={styles.headerRow}>
          <Text style={layout.sectionLabel}>Your lists</Text>
          <Link href="/new-list" asChild>
            <Pressable>
              <Text style={styles.link}>New list</Text>
            </Pressable>
          </Link>
        </View>

        <View style={styles.cards}>
          {lists.map((list) => {
            const counts = visitedCount(places, list.id);
            return (
              <ListCard
                key={list.id}
                list={list}
                visited={counts.visited}
                total={counts.total}
                onPress={() => router.push(`/list/${list.id}`)}
              />
            );
          })}
        </View>
        <Pressable
          onPress={() =>
            confirmAction(
              'Restore Oslo starter?',
              'This replaces your lists and places with the included Oslo collection.',
              restoreOsloStarter,
            )
          }>
          <Text style={styles.restore}>Restore Oslo starter collection</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingHorizontal: 20,
    paddingBottom: 40,
    paddingTop: 12,
  },
  kicker: {
    fontFamily: fonts.sans,
    fontSize: 12,
    letterSpacing: 2,
    textTransform: 'uppercase',
    color: colors.copper,
    fontWeight: '700',
    marginBottom: 6,
  },
  lede: {
    marginTop: 10,
    maxWidth: 360,
  },
  stats: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 22,
    marginBottom: 28,
  },
  stat: {
    flex: 1,
    backgroundColor: colors.card,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.line,
    paddingVertical: 14,
    alignItems: 'center',
  },
  statValue: {
    fontFamily: fonts.serif,
    fontSize: 26,
    color: colors.ink,
  },
  statLabel: {
    fontFamily: fonts.sans,
    fontSize: 12,
    color: colors.muted,
    marginTop: 2,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  link: {
    fontFamily: fonts.sans,
    color: colors.forest,
    fontWeight: '700',
    fontSize: 14,
  },
  cards: {
    gap: 14,
  },
  restore: {
    marginTop: 28,
    textAlign: 'center',
    color: colors.muted,
    fontFamily: fonts.sans,
    fontSize: 13,
    textDecorationLine: 'underline',
  },
});
