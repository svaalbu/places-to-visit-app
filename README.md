# Bordbok

An iPhone notebook for restaurants and cafés you are collecting — starting in Oslo.

Keep separate lists (cafés, high end, regular, or any list you add), check off places you have visited, pin them on a map, and attach a short note plus a photo from each table.

## Test on your iPhone (no Apple Developer Program)

Use **Expo Go**. It is free. You do not pay Apple. Bordbok runs *inside* Expo Go while your computer is serving the project.

1. On the iPhone, install [Expo Go](https://apps.apple.com/app/expo-go/id982107779) from the App Store.
2. Create a free [Expo](https://expo.dev/signup) account.
3. In Expo Go, tap the avatar and **log in** with that account.
4. On your computer, install **Node.js 22 LTS** first. `npm` and `npx` come with it. Until Node is installed, those commands will fail with `command not found`.

   - Easiest on a Mac: download the **LTS** installer from [nodejs.org](https://nodejs.org/), run it, then **quit Terminal completely and open a new window**.
   - Or with Homebrew: `brew install node@22` then follow the brew caveats so `node` is on your `PATH`.
   - Check that it worked:

```bash
node -v
npm -v
```

   You want Node `v22` (or at least `v20`) and an npm version printed. Then:

```bash
git clone https://github.com/svaalbu/places-to-visit-app.git
cd places-to-visit-app
git checkout cursor/oslo-restaurant-tracker-0e8a
npm install
npx expo login
npx expo start
```

Log in to the **same** Expo account in the terminal (SDK 57 Expo Go requires this).

5. Put the phone and the computer on the **same Wi‑Fi**.
6. On the iPhone, open the **Camera** app, scan the QR code in the terminal, and open it in Expo Go.
7. Leave the terminal running. If you stop it, Bordbok in Expo Go will stop loading.

If the QR code never connects (guest Wi‑Fi, VPN, or phone on cellular), use a tunnel instead:

```bash
npx expo start --tunnel
```

The first tunnel start may ask to install `@expo/ngrok`. Allow that, then scan the new QR code.

**Limits of this path:** the home-screen icon is Expo Go, not Bordbok. The computer must keep running (or you use a tunnel to a machine that stays on). Photos, notes, and check-offs are stored on that phone. This is the right way to try the app before paying Apple.

## Install as a normal app later (Apple Developer Program)

For everyday use with Bordbok’s own icon and no laptop, install it with [EAS Build](https://docs.expo.dev/build/setup/) and **TestFlight**. That needs a paid [Apple Developer Program](https://developer.apple.com/programs/) membership.

```bash
npx eas-cli@latest login
npx eas-cli@latest init
npx eas-cli@latest build --platform ios --profile production
npx eas-cli@latest submit --platform ios
```

Then install **TestFlight** from the App Store and add Bordbok to the home screen.

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
