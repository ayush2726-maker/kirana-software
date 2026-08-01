import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  BackHandler,
  Linking,
  Platform,
  SafeAreaView,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View
} from "react-native";
import { WebView } from "react-native-webview";
import * as Updates from "expo-updates";

const APP_ORIGIN = (process.env.EXPO_PUBLIC_APP_URL || "https://web-production-02514.up.railway.app").replace(/\/$/, "");
const OWNER_URL = `${APP_ORIGIN}/?mobile=1`;

function withTimeout(promise, milliseconds) {
  return Promise.race([
    promise,
    new Promise(resolve => setTimeout(() => resolve(null), milliseconds))
  ]);
}

function isAppPage(url) {
  return url === "about:blank" || url.startsWith(APP_ORIGIN);
}

function LoadingOverlay({ message = "Kirana Software load ho raha hai…" }) {
  return (
    <View style={styles.loadingOverlay} pointerEvents="none">
      <View style={styles.logoBox}>
        <Text style={styles.logoText}>K</Text>
      </View>
      <Text style={styles.loadingTitle}>Kirana Software Mobile</Text>
      <ActivityIndicator size="large" color="#0b82c2" style={styles.spinner} />
      <Text style={styles.loadingText}>{message}</Text>
    </View>
  );
}

function ConnectionError({ message, onRetry }) {
  return (
    <View style={styles.errorScreen}>
      <View style={styles.logoBox}>
        <Text style={styles.logoText}>K</Text>
      </View>
      <Text style={styles.errorTitle}>App connect nahi ho rahi</Text>
      <Text style={styles.errorText}>{message || "Internet check karke dobara try karein."}</Text>
      <TouchableOpacity style={styles.retryButton} onPress={onRetry} activeOpacity={0.8}>
        <Text style={styles.retryText}>Dobara Kholein</Text>
      </TouchableOpacity>
    </View>
  );
}

export default function App() {
  const webRef = useRef(null);
  const [canGoBack, setCanGoBack] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [updateMessage, setUpdateMessage] = useState("");

  const reloadWebApp = useCallback(() => {
    setLoadError("");
    setPageLoading(true);
    setReloadKey(value => value + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function checkForOtaUpdate() {
      if (__DEV__ || !Updates.isEnabled) return;
      try {
        const result = await withTimeout(Updates.checkForUpdateAsync(), 5000);
        if (cancelled || !result || !result.isAvailable) return;
        setUpdateMessage("Naya update download ho raha hai…");
        await Updates.fetchUpdateAsync();
        if (cancelled) return;
        setUpdateMessage("Update apply ho raha hai…");
        await Updates.reloadAsync();
      } catch (error) {
        if (!cancelled) setUpdateMessage("");
      }
    }

    checkForOtaUpdate();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const subscription = BackHandler.addEventListener("hardwareBackPress", () => {
      if (canGoBack && webRef.current) {
        webRef.current.goBack();
        return true;
      }
      return false;
    });
    return () => subscription.remove();
  }, [canGoBack]);

  const handleNavigationRequest = useCallback(request => {
    const url = request?.url || "";
    if (!url || isAppPage(url)) return true;

    if (/^(https?:|mailto:|tel:|sms:|whatsapp:|intent:|upi:)/i.test(url)) {
      Linking.openURL(url).catch(() => {});
      return false;
    }
    return true;
  }, []);

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar backgroundColor="#087fbf" barStyle="light-content" />

      {updateMessage ? (
        <View style={styles.updateBanner}>
          <ActivityIndicator size="small" color="#ffffff" />
          <Text style={styles.updateText}>{updateMessage}</Text>
        </View>
      ) : null}

      <View style={styles.container}>
        {loadError ? (
          <ConnectionError message={loadError} onRetry={reloadWebApp} />
        ) : (
          <>
            <WebView
              key={reloadKey}
              ref={webRef}
              source={{ uri: OWNER_URL }}
              style={styles.webView}
              originWhitelist={["*"]}
              javaScriptEnabled
              domStorageEnabled
              sharedCookiesEnabled
              thirdPartyCookiesEnabled
              cacheEnabled
              incognito={false}
              mixedContentMode="compatibility"
              allowsBackForwardNavigationGestures
              pullToRefreshEnabled
              setSupportMultipleWindows={false}
              javaScriptCanOpenWindowsAutomatically
              allowFileAccess
              allowContentAccess
              userAgent="KiranaSoftwareMobile/1.0 Android"
              onShouldStartLoadWithRequest={handleNavigationRequest}
              onNavigationStateChange={navState => setCanGoBack(Boolean(navState.canGoBack))}
              onLoadStart={() => {
                setLoadError("");
                setPageLoading(true);
              }}
              onLoadEnd={() => setPageLoading(false)}
              onError={event => {
                const description = event?.nativeEvent?.description || "Server se connection nahi ho paya.";
                setPageLoading(false);
                setLoadError(description);
              }}
              onHttpError={event => {
                const status = event?.nativeEvent?.statusCode;
                if (Number(status) >= 500) {
                  setPageLoading(false);
                  setLoadError(`Server error ${status}. Dobara try karein.`);
                }
              }}
              onContentProcessDidTerminate={() => webRef.current?.reload()}
              onRenderProcessGone={() => {
                webRef.current?.reload();
                return true;
              }}
            />
            {pageLoading ? <LoadingOverlay /> : null}
          </>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#087fbf"
  },
  container: {
    flex: 1,
    backgroundColor: "#eef7fd"
  },
  webView: {
    flex: 1,
    backgroundColor: "#eef7fd"
  },
  updateBanner: {
    minHeight: 38,
    paddingHorizontal: 14,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 9,
    backgroundColor: "#075f91"
  },
  updateText: {
    color: "#ffffff",
    fontSize: 13,
    fontWeight: "700"
  },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "center",
    padding: 28,
    backgroundColor: "#eef7fd"
  },
  logoBox: {
    width: 86,
    height: 86,
    borderRadius: 26,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#0b82c2",
    shadowColor: "#075f91",
    shadowOpacity: Platform.OS === "ios" ? 0.22 : 0,
    shadowRadius: 14,
    elevation: 7
  },
  logoText: {
    color: "#ffffff",
    fontSize: 52,
    lineHeight: 58,
    fontWeight: "900"
  },
  loadingTitle: {
    marginTop: 20,
    color: "#253241",
    fontSize: 24,
    fontWeight: "900",
    textAlign: "center"
  },
  spinner: {
    marginTop: 24
  },
  loadingText: {
    marginTop: 14,
    color: "#687785",
    fontSize: 14,
    textAlign: "center"
  },
  errorScreen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 28,
    backgroundColor: "#eef7fd"
  },
  errorTitle: {
    marginTop: 22,
    color: "#253241",
    fontSize: 25,
    fontWeight: "900",
    textAlign: "center"
  },
  errorText: {
    maxWidth: 360,
    marginTop: 12,
    color: "#687785",
    fontSize: 15,
    lineHeight: 22,
    textAlign: "center"
  },
  retryButton: {
    minWidth: 210,
    marginTop: 24,
    paddingHorizontal: 24,
    paddingVertical: 15,
    alignItems: "center",
    borderRadius: 14,
    backgroundColor: "#0b82c2"
  },
  retryText: {
    color: "#ffffff",
    fontSize: 17,
    fontWeight: "900"
  }
});
