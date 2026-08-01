const APP_URL = process.env.EXPO_PUBLIC_APP_URL || "https://web-production-02514.up.railway.app";
const PROJECT_ID = "97bba2a7-cef9-4902-aa87-e6651d4b5156";
const ANDROID_PACKAGE = process.env.EXPO_ANDROID_PACKAGE || "com.kiranasoftware.mobile";

const expo = {
  name: "Kirana Software Mobile",
  slug: "kirana-software-mobile",
  owner: "ayush2726",
  version: "1.0.1",
  orientation: "portrait",
  userInterfaceStyle: "light",
  backgroundColor: "#eef7fd",
  scheme: "kiranasoftware",
  icon: "./assets/icon.png",
  splash: {
    image: "./assets/splash.png",
    resizeMode: "contain",
    backgroundColor: "#eef7fd"
  },
  newArchEnabled: false,
  runtimeVersion: {
    policy: "appVersion"
  },
  android: {
    package: ANDROID_PACKAGE,
    versionCode: 3,
    edgeToEdgeEnabled: true,
    softwareKeyboardLayoutMode: "resize",
    permissions: ["INTERNET"],
    adaptiveIcon: {
      foregroundImage: "./assets/adaptive-icon.png",
      backgroundColor: "#eef7fd"
    }
  },
  ios: {
    bundleIdentifier: ANDROID_PACKAGE,
    buildNumber: "3",
    supportsTablet: true
  },
  extra: {
    appUrl: APP_URL,
    eas: {
      projectId: PROJECT_ID
    }
  },
  updates: {
    url: `https://u.expo.dev/${PROJECT_ID}`,
    enabled: true,
    checkAutomatically: "ON_LOAD",
    fallbackToCacheTimeout: 0
  }
};

module.exports = { expo };
