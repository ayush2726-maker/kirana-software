const { withAndroidManifest, withMainActivity } = require('@expo/config-plugins');

function withRecordAudioManifest(config) {
  return withAndroidManifest(config, (config) => {
    const manifest = config.modResults.manifest;
    manifest['uses-permission'] = manifest['uses-permission'] || [];
    const name = 'android.permission.RECORD_AUDIO';
    if (!manifest['uses-permission'].some((p) => p.$ && p.$['android:name'] === name)) {
      manifest['uses-permission'].push({ $: { 'android:name': name } });
    }
    return config;
  });
}

function withNativeVoiceBridge(config) {
  return withMainActivity(config, (config) => {
    let src = config.modResults.contents;
    if (src.includes('KiranaVoiceBridgeV5')) return config;

    src = src.replace(
      'import android.annotation.SuppressLint',
      `import android.annotation.SuppressLint\nimport android.Manifest\nimport android.content.pm.PackageManager\nimport android.speech.RecognizerIntent\nimport android.webkit.JavascriptInterface\nimport android.webkit.PermissionRequest\nimport org.json.JSONObject`
    );

    src = src.replace(
      'private val uploadRequestCode = 7301',
      `private val uploadRequestCode = 7301\n    private val voiceRequestCode = 7302\n    private val micPermissionRequestCode = 7303\n    private var pendingVoiceStart = false\n    private var pendingWebPermission: PermissionRequest? = null\n    // KiranaVoiceBridgeV5`
    );

    src = src.replace(
      'target.webChromeClient = object : WebChromeClient() {',
      `target.addJavascriptInterface(VoiceBridge(), "KiranaVoice")\n\n        target.webChromeClient = object : WebChromeClient() {\n            override fun onPermissionRequest(request: PermissionRequest) {\n                if (request.resources.contains(PermissionRequest.RESOURCE_AUDIO_CAPTURE)) {\n                    runOnUiThread {\n                        if (android.os.Build.VERSION.SDK_INT < 23 || checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {\n                            request.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE))\n                        } else {\n                            pendingWebPermission = request\n                            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), micPermissionRequestCode)\n                        }\n                    }\n                } else {\n                    request.deny()\n                }\n            }`
    );

    const activityResultAnchor = `    @Deprecated("Deprecated in Android")\n    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {\n        super.onActivityResult(requestCode, resultCode, data)\n        if (requestCode == uploadRequestCode) {`;
    const activityResultReplacement = `    private inner class VoiceBridge {\n        @JavascriptInterface\n        fun start() {\n            runOnUiThread { startVoiceRecognition() }\n        }\n    }\n\n    private fun startVoiceRecognition() {\n        if (android.os.Build.VERSION.SDK_INT >= 23 && checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {\n            pendingVoiceStart = true\n            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), micPermissionRequestCode)\n            return\n        }\n        try {\n            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {\n                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)\n                putExtra(RecognizerIntent.EXTRA_LANGUAGE, "hi-IN")\n                putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "hi-IN")\n                putExtra(RecognizerIntent.EXTRA_PROMPT, "Item bolo, jaise: 5 kilo moong")\n                putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)\n            }\n            startActivityForResult(intent, voiceRequestCode)\n        } catch (error: Exception) {\n            webView.evaluateJavascript("window.KiranaVoiceError && window.KiranaVoiceError('voice-unavailable')", null)\n        }\n    }\n\n    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {\n        super.onRequestPermissionsResult(requestCode, permissions, grantResults)\n        if (requestCode != micPermissionRequestCode) return\n        val granted = grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED\n        pendingWebPermission?.let { req ->\n            if (granted) req.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE)) else req.deny()\n        }\n        pendingWebPermission = null\n        if (pendingVoiceStart) {\n            pendingVoiceStart = false\n            if (granted) startVoiceRecognition() else webView.evaluateJavascript("window.KiranaVoiceError && window.KiranaVoiceError('permission-denied')", null)\n        }\n    }\n\n    @Deprecated("Deprecated in Android")\n    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {\n        super.onActivityResult(requestCode, resultCode, data)\n        if (requestCode == voiceRequestCode) {\n            if (resultCode == RESULT_OK) {\n                val results = data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)\n                val heard = results?.firstOrNull().orEmpty()\n                if (heard.isNotBlank()) {\n                    val quoted = JSONObject.quote(heard)\n                    webView.evaluateJavascript("window.KiranaVoiceResult && window.KiranaVoiceResult(" + quoted + ")", null)\n                }\n            }\n            return\n        }\n        if (requestCode == uploadRequestCode) {`;
    if (!src.includes(activityResultAnchor)) {
      throw new Error('Native voice patch anchor not found in MainActivity');
    }
    src = src.replace(activityResultAnchor, activityResultReplacement);

    config.modResults.contents = src;
    return config;
  });
}

module.exports = function withNativeVoiceBridgeV5(config) {
  config = withRecordAudioManifest(config);
  config = withNativeVoiceBridge(config);
  return config;
};
