# Kirana Software Mobile

Expo/EAS Android wrapper for the Kirana Software owner billing app.

## Included

- Owner billing app opens inside a persistent WebView.
- Login session and cookies remain saved between launches.
- Android back button works with in-app navigation.
- WhatsApp, UPI, phone and external links open in their native apps.
- Offline/server error screen with retry.
- EAS preview APK and production AAB profiles.
- Production OTA updates through `expo-updates`.

## Link the existing Expo project

This code is intended for the existing Expo project named **Kirana Software Mobile**.
Do not create a second Expo project.

From the `mobile` directory:

```bash
npm install
npx eas-cli@latest login
npx eas-cli@latest init
```

When EAS asks, select the existing **Kirana Software Mobile** project. Copy its UUID into `.env`:

```env
EXPO_PROJECT_ID=YOUR_EXISTING_PROJECT_UUID
EXPO_PUBLIC_APP_URL=https://web-production-02514.up.railway.app
EXPO_ANDROID_PACKAGE=com.kiranasoftware.mobile
```

Then verify the generated config:

```bash
npx expo config --type public
npx expo-doctor@latest
```

## Build APK

```bash
npx eas-cli@latest build --platform android --profile preview
```

The preview profile creates an installable APK and listens to the `production` update channel.

## Build Play Store AAB

```bash
npx eas-cli@latest build --platform android --profile production
```

## Push an OTA update

JavaScript/UI-only changes can be sent without rebuilding the APK/AAB:

```bash
npx eas-cli@latest update --channel production --message "Kirana mobile update"
```

Increment the app version and make a fresh EAS build whenever native dependencies, Android package settings, permissions or other native configuration changes.
