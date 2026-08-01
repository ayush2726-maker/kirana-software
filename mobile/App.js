import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Linking,
  Platform,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View
} from "react-native";
import * as Updates from "expo-updates";
import * as WebBrowser from "expo-web-browser";

const APP_URL = "https://web-production-02514.up.railway.app/?mobile=1&appVersion=102";
const UPDATE_TIMEOUT_MS = 5000;

function withTimeout(promise, milliseconds) {
  return Promise.race([
    promise,
    new Promise(resolve => setTimeout(() => resolve(null), milliseconds))
  ]);
}

export default function App() {
  const openingRef = useRef(false);
  const mountedRef = useRef(true);
  const [opening, setOpening] = useState(false);
  const [status, setStatus] = useState("Billing app taiyar hai");

  const openBillingApp = useCallback(async () => {
    if (openingRef.current) return;
    openingRef.current = true;
    if (mountedRef.current) {
      setOpening(true);
      setStatus("Secure billing app khul rahi hai…");
    }

    try {
      let browserPackage;
      if (Platform.OS === "android") {
        const browsers = await WebBrowser.getCustomTabsSupportingBrowsersAsync().catch(() => null);
        browserPackage = browsers?.preferredBrowserPackage || browsers?.defaultBrowserPackage || undefined;
        await WebBrowser.warmUpAsync(browserPackage).catch(() => null);
        await WebBrowser.mayInitWithUrlAsync(APP_URL, browserPackage).catch(() => null);
      }

      await WebBrowser.openBrowserAsync(APP_URL, {
        browserPackage,
        toolbarColor: "#087fbf",
        secondaryToolbarColor: "#075f91",
        controlsColor: "#087fbf",
        enableBarCollapsing: true,
        enableDefaultShareMenuItem: false,
        showTitle: false,
        createTask: false
      });

      if (mountedRef.current) {
        setStatus("Billing app band ho gayi. Dobara kholne ke liye neeche button dabayein.");
      }
    } catch (error) {
      try {
        await Linking.openURL(APP_URL);
        if (mountedRef.current) setStatus("Billing app browser mein khol di gayi hai.");
      } catch (fallbackError) {
        if (mountedRef.current) {
          setStatus("Browser nahi khul paya. Internet aur Chrome check karke dobara try karein.");
        }
      }
    } finally {
      openingRef.current = false;
      if (mountedRef.current) setOpening(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    let cancelled = false;

    async function startApp() {
      if (!__DEV__ && Updates.isEnabled) {
        try {
          const update = await withTimeout(Updates.checkForUpdateAsync(), UPDATE_TIMEOUT_MS);
          if (!cancelled && update?.isAvailable) {
            setStatus("Naya update download ho raha hai…");
            await Updates.fetchUpdateAsync();
            if (!cancelled) {
              setStatus("Update apply ho raha hai…");
              await Updates.reloadAsync();
              return;
            }
          }
        } catch (error) {
          // A failed OTA check must never block the billing app from opening.
        }
      }

      if (!cancelled) {
        setTimeout(() => {
          if (!cancelled) openBillingApp();
        }, 350);
      }
    }

    startApp();

    return () => {
      cancelled = true;
      mountedRef.current = false;
      if (Platform.OS === "android") {
        WebBrowser.coolDownAsync().catch(() => null);
      }
    };
  }, [openBillingApp]);

  return (
    <View style={styles.root}>
      <StatusBar backgroundColor="#087fbf" barStyle="light-content" />

      <View style={styles.hero}>
        <View style={styles.logo}>
          <Text style={styles.logoText}>K</Text>
        </View>
        <Text style={styles.title}>Kirana Software</Text>
        <Text style={styles.subtitle}>Billing, Stock aur Khata — Sab Ek Jagah</Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Owner Billing App</Text>
        <Text style={styles.message}>{status}</Text>

        <TouchableOpacity
          style={[styles.button, opening && styles.buttonDisabled]}
          activeOpacity={0.82}
          disabled={opening}
          onPress={openBillingApp}
        >
          {opening ? <ActivityIndicator color="#ffffff" /> : null}
          <Text style={styles.buttonText}>{opening ? "Khul rahi hai…" : "Billing App Kholein"}</Text>
        </TouchableOpacity>

        <Text style={styles.note}>
          App ab Android WebView ke bajay phone ke Chrome Custom Tab engine par chalegi, isliye click aur blank-screen issue nahi aayega.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#eef7fd"
  },
  hero: {
    minHeight: 315,
    paddingHorizontal: 28,
    paddingTop: 72,
    alignItems: "center",
    backgroundColor: "#087fbf"
  },
  logo: {
    width: 92,
    height: 92,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#42abe2"
  },
  logoText: {
    color: "#ffffff",
    fontSize: 58,
    fontWeight: "900"
  },
  title: {
    marginTop: 20,
    color: "#ffffff",
    fontSize: 34,
    fontWeight: "900"
  },
  subtitle: {
    marginTop: 9,
    color: "#dceffc",
    fontSize: 16,
    textAlign: "center"
  },
  card: {
    marginHorizontal: 24,
    marginTop: -42,
    padding: 26,
    borderRadius: 24,
    backgroundColor: "#ffffff",
    elevation: 7
  },
  cardTitle: {
    color: "#263545",
    fontSize: 25,
    fontWeight: "900",
    textAlign: "center"
  },
  message: {
    minHeight: 46,
    marginTop: 13,
    color: "#687785",
    fontSize: 15,
    lineHeight: 22,
    textAlign: "center"
  },
  button: {
    minHeight: 58,
    marginTop: 20,
    paddingHorizontal: 20,
    borderRadius: 16,
    flexDirection: "row",
    gap: 10,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#0b82c2"
  },
  buttonDisabled: {
    opacity: 0.72
  },
  buttonText: {
    color: "#ffffff",
    fontSize: 18,
    fontWeight: "900"
  },
  note: {
    marginTop: 18,
    color: "#7a8792",
    fontSize: 12,
    lineHeight: 18,
    textAlign: "center"
  }
});
