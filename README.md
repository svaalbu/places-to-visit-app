# Bordbok

An iPhone notebook for restaurants and cafés you are collecting — starting in Oslo.

Keep separate lists (cafés, high end, regular, or any list you add), check off places you have visited, pin them on a map, and attach a short note plus a photo from each table.

## On your iPhone

**Expo Go is not a regular app.** It is a playground: you open Expo Go, scan a QR code from a computer running `npx expo start`, and Bordbok runs *inside* Expo Go. It does not get its own home-screen icon, it needs that development session (or a matching published update), and Expo does not treat it as the way to ship something you use every day.

For everyday use, install **Bordbok itself** with [EAS Build](https://docs.expo.dev/build/setup/) and **TestFlight**. Then it behaves like any other iPhone app: own icon, works offline, no Expo Go, no laptop.

You need:

1. An [Apple Developer Program](https://developer.apple.com/programs/) membership (paid, required for TestFlight).
2. A free [Expo](https://expo.dev) account.
3. These commands from the project folder (once):

```bash
npm install
npx eas-cli@latest login
npx eas-cli@latest init
npx eas-cli@latest build --platform ios --profile production
npx eas-cli@latest submit --platform ios
```

EAS walks you through Apple login, certificates, and App Store Connect. After the build is submitted, install **TestFlight** from the App Store, accept Bordbok, and add it to your home screen.

A `preview` profile in `eas.json` can also install a production-like build on your registered iPhone without the public App Store (`--profile preview`). TestFlight is usually simpler for one personal phone.

This repo is Expo / React Native (SDK 57), not a Swift Xcode project.

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
