import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  BackHandler,
  Linking,
  StatusBar,
  StyleSheet,
  Text,
  TouchableOpacity,
  View
} from "react-native";
import { WebView } from "react-native-webview";
import * as Updates from "expo-updates";

const APP_ORIGIN = (process.env.EXPO_PUBLIC_APP_URL || "https://web-production-02514.up.railway.app").replace(/\/$/, "");
const OWNER_URL = `${APP_ORIGIN}/?mobile=1&appVersion=101`;

const TOUCH_READY_SCRIPT = `
(function () {
  try {
    document.documentElement.style.pointerEvents = 'auto';
    document.documentElement.style.touchAction = 'auto';
    if (document.body) {
      document.body.style.pointerEvents = 'auto';
      document.body.style.touchAction = 'auto';
    }
    document.querySelectorAll('input, button, select, textarea, a, [role="button"]').forEach(function (el) {
      el.style.pointerEvents = 'auto';
      el.style.touchAction = 'manipulation';
    });
    window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'KIRANA_PAGE_READY' }));
  } catch (error) {}
})();
true;
`;

function isAppPage(url) {
  return url === "about:blank" || url.startsWith(APP_ORIGIN);
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
        const result = await Updates.checkForUpdateAsync();
        if (cancelled || !result?.isAvailable) return;
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
    <View style={styles.root} pointerEvents="box-none">
      <StatusBar backgroundColor="#087fbf" barStyle="light-content" />

      {updateMessage ? (
        <View style={styles.statusBanner} pointerEvents="none">
          <ActivityIndicator size="small" color="#ffffff" />
          <Text style={styles.statusText}>{updateMessage}</Text>
        </View>
      ) : pageLoading ? (
        <View style={styles.statusBanner} pointerEvents="none">
          <ActivityIndicator size="small" color="#ffffff" />
          <Text style={styles.statusText}>Kirana Software load ho raha hai…</Text>
        </View>
      ) : null}

      <View style={styles.webContainer} pointerEvents="box-none">
        {loadError ? (
          <ConnectionError message={loadError} onRetry={reloadWebApp} />
        ) : (
          <WebView
            key={reloadKey}
            ref={webRef}
            source={{ uri: OWNER_URL }}
            style={styles.webView}
            containerStyle={styles.webViewContainer}
            pointerEvents="auto"
            originWhitelist={["*"]}
            javaScriptEnabled
            domStorageEnabled
            sharedCookiesEnabled
            thirdPartyCookiesEnabled
            cacheEnabled={false}
            incognito={false}
            mixedContentMode="compatibility"
            allowsBackForwardNavigationGestures
            pullToRefreshEnabled
            nestedScrollEnabled
            scrollEnabled
            setSupportMultipleWindows={false}
            javaScriptCanOpenWindowsAutomatically
            allowFileAccess
            allowContentAccess
            focusable
            androidLayerType="hardware"
            applicationNameForUserAgent="KiranaSoftwareMobile/1.0.1"
            injectedJavaScript={TOUCH_READY_SCRIPT}
            injectedJavaScriptBeforeContentLoaded={TOUCH_READY_SCRIPT}
            onShouldStartLoadWithRequest={handleNavigationRequest}
            onNavigationStateChange={navState => {
              setCanGoBack(Boolean(navState.canGoBack));
              if (navState?.url && navState.url !== "about:blank") setPageLoading(false);
            }}
            onMessage={() => setPageLoading(false)}
            onLoadStart={() => {
              setLoadError("");
              setPageLoading(true);
            }}
            onLoadProgress={event => {
              if (Number(event?.nativeEvent?.progress || 0) >= 0.45) setPageLoading(false);
            }}
            onLoadEnd={() => setPageLoading(false)}
            onError={event => {
              const description = event?.nativeEvent?.description || "Server se connection nahi ho paya.";
              setPageLoading(false);
              setLoadError(description);
            }}
            onHttpError={event => {
              const status = Number(event?.nativeEvent?.statusCode || 0);
              if (status >= 500) {
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
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#087fbf"
  },
  webContainer: {
    flex: 1,
    backgroundColor: "#eef7fd"
  },
  webViewContainer: {
    flex: 1,
    backgroundColor: "#eef7fd"
  },
  webView: {
    flex: 1,
    backgroundColor: "#eef7fd"
  },
  statusBanner: {
    minHeight: 34,
    paddingHorizontal: 12,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    backgroundColor: "#075f91"
  },
  statusText: {
    color: "#ffffff",
    fontSize: 12,
    fontWeight: "700"
  },
  logoBox: {
    width: 86,
    height: 86,
    borderRadius: 26,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#0b82c2",
    elevation: 7
  },
  logoText: {
    color: "#ffffff",
    fontSize: 52,
    lineHeight: 58,
    fontWeight: "900"
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
