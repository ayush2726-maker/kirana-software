const APP_URL = process.env.EXPO_PUBLIC_APP_URL || "https://web-production-02514.up.railway.app";
const PROJECT_ID = (process.env.EXPO_PROJECT_ID || "").trim();
const ANDROID_PACKAGE = process.env.EXPO_ANDROID_PACKAGE || "com.kiranasoftware.mobile";

const expo = {
  name: "Kirana Software Mobile",
  slug: "kirana-software-mobile",
  version: "1.0.0",
  orientation: "portrait",
  userInterfaceStyle: "light",
  backgroundColor: "#eef7fd",
  scheme: "kiranasoftware",
  newArchEnabled: true,
  runtimeVersion: {
    policy: "appVersion"
  },
  android: {
    package: ANDROID_PACKAGE,
    versionCode: 1,
    edgeToEdgeEnabled: true,
    permissions: ["INTERNET"],
    adaptiveIcon: {
      backgroundColor: "#0b82c2"
    }
  },
  ios: {
    bundleIdentifier: ANDROID_PACKAGE,
    buildNumber: "1",
    supportsTablet: true
  },
  extra: {
    appUrl: APP_URL,
    eas: PROJECT_ID ? { projectId: PROJECT_ID } : undefined
  },
  updates: PROJECT_ID
    ? {
        url: `https://u.expo.dev/${PROJECT_ID}`,
        enabled: true,
        checkAutomatically: "ON_LOAD",
        fallbackToCacheTimeout: 0
      }
    : {
        enabled: false
      }
};

module.exports = { expo };
