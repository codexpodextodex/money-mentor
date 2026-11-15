# Money Mentor on a real phone

The phone app from the demo page, as an installable Android app. It is a small Expo app that opens the app page (`/app` on the demo server) full screen, so it works exactly like the phone in the demo: same screens, same walkthrough, same answers from Nemotron. It needs an internet connection.

**Download:** the APK is attached to the latest [release](https://github.com/codexpodextodex/money-mentor/releases). Allow installs from unknown sources, or install over USB:

```bash
adb install MoneyMentor.apk
```

## What the wrapper adds

- A launcher icon and a green launch screen, like S-mobiili's.
- Drawn edge to edge: the status bar and navigation bar heights are handed to the web app through its `--sat` and `--sab` CSS variables.
- The Android back button goes back inside the app.
- A "No connection" screen with a retry button.
- Camera permission, so a bill or a price tag can be photographed.

## Build it yourself

Needs Node, JDK 17 and the Android SDK with the NDK licence accepted.

```bash
npm install
npx expo prebuild --platform android
cd android && ./gradlew assembleRelease -PreactNativeArchitectures=arm64-v8a
```

The APK lands in `android/app/build/outputs/apk/release/`. On Windows, build from a short path (for example `C:\mm`): React Native's C++ build fails on paths longer than 260 characters.

To point the app at another server, change `APP_URL` in `App.tsx`.
