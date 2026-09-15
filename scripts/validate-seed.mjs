import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const source = readFileSync(join(root, 'src/data/seed.ts'), 'utf8');
const pairs = [...source.matchAll(/latitude: ([0-9.]+),\s*\n\s*longitude: ([0-9.]+)/g)];
const visited = [...source.matchAll(/visited: true/g)];
const lists = [...source.matchAll(/id: '(cafes|high-end|regular)'/g)];

if (pairs.length < 20) {
  throw new Error(`Expected at least 20 seed coordinates, found ${pairs.length}`);
}
if (lists.length < 3) {
  throw new Error('Starter lists for cafés, high end, and regular are required');
}
if (visited.length < 3) {
  throw new Error('Starter data should include a few visited places');
}

for (const [, latRaw, lonRaw] of pairs) {
  const lat = Number(latRaw);
  const lon = Number(lonRaw);
  if (lat < 59.85 || lat > 60.05 || lon < 10.6 || lon > 10.95) {
    throw new Error(`Coordinate outside greater Oslo: ${lat}, ${lon}`);
  }
}

console.log(
  `Validated ${pairs.length} Oslo coordinates, ${visited.length} visited starter places.`,
);
