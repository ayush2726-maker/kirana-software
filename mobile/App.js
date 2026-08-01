import React from "react";
import { StatusBar, StyleSheet, View } from "react-native";
import { WebView } from "react-native-webview";

const APP_URL = "https://web-production-02514.up.railway.app/?mobile=1&appVersion=102";

export default function App() {
  return (
    <View style={styles.root}>
      <StatusBar backgroundColor="#087fbf" barStyle="light-content" />
      <WebView
        source={{ uri: APP_URL }}
        style={styles.webView}
        originWhitelist={["*"]}
        javaScriptEnabled
        domStorageEnabled
        sharedCookiesEnabled
        thirdPartyCookiesEnabled
        cacheEnabled={false}
        setSupportMultipleWindows={false}
        allowsBackForwardNavigationGestures
        pullToRefreshEnabled
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#eef7fd"
  },
  webView: {
    flex: 1,
    backgroundColor: "#eef7fd"
  }
});
