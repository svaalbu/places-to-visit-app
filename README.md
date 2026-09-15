# Bordbok

An iPhone notebook for restaurants and cafés you are collecting — starting in Oslo.

Keep separate lists (cafés, high end, regular, or any list you add), check off places you have visited, pin them on a map, and attach a short note plus a photo from each table.

## On your iPhone

1. Install [Expo Go](https://apps.apple.com/app/expo-go/id982107779).
2. On a Mac: `npm install` then `npx expo start`, and scan the QR code with the Camera app.
3. Or build a device binary later with [EAS Build](https://docs.expo.dev/build/setup/) (`npx eas build --platform ios`).

This repo is an Expo / React Native app (Expo SDK 57). It is meant to be opened in Expo Go or compiled in Xcode via EAS — it is not a Swift project.

## Features

- **Lists** — starter collections for Oslo cafés, high-end rooms, and regular tables. Add your own lists.
- **Visited** — check a place off in the list, on the place screen, or from the map.
- **Notes & photos** — a short note and one photo per place, stored on the phone.
- **Oslo map** — filled pins are visited; hollow pins are still to try. Filter by list.
- **Add a place** — type it in, or search Oslo via OpenStreetMap Nominatim.

Starter pins are a personal shortlist, not a complete city guide. Coordinates are approximate.

## Run locally

```bash
npm install
npx expo start
```

- `npx expo start --ios` — Simulator (macOS)
- `npx expo start --web` — browser preview (phone-sized frame, map included)
- `npm run typecheck` — TypeScript
- `npm run validate-seed` — Oslo coordinate sanity check
