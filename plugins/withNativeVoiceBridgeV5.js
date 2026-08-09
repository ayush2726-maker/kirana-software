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
      `import android.annotation.SuppressLint\nimport android.Manifest\nimport android.content.ContentValues\nimport android.content.pm.PackageManager\nimport android.provider.MediaStore\nimport android.speech.RecognizerIntent\nimport android.webkit.JavascriptInterface\nimport android.webkit.PermissionRequest\nimport org.json.JSONObject`
    );

    src = src.replace(
      'private val uploadRequestCode = 7301',
      `private val uploadRequestCode = 7301\n    private var capturedPhotoUri: Uri? = null\n    private val voiceRequestCode = 7302\n    private val micPermissionRequestCode = 7303\n    private var pendingVoiceStart = false\n    private var pendingWebPermission: PermissionRequest? = null\n    // KiranaVoiceBridgeV5`
    );

    src = src.replace(
      'target.webChromeClient = object : WebChromeClient() {',
      `target.addJavascriptInterface(VoiceBridge(), "KiranaVoice")\n\n        target.webChromeClient = object : WebChromeClient() {\n            override fun onPermissionRequest(request: PermissionRequest) {\n                if (request.resources.contains(PermissionRequest.RESOURCE_AUDIO_CAPTURE)) {\n                    runOnUiThread {\n                        if (android.os.Build.VERSION.SDK_INT < 23 || checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {\n                            request.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE))\n                        } else {\n                            pendingWebPermission = request\n                            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), micPermissionRequestCode)\n                        }\n                    }\n                } else {\n                    request.deny()\n                }\n            }`
    );

    const chooserOld = `            override fun onShowFileChooser(\n                webView: WebView,\n                filePathCallback: ValueCallback<Array<Uri>>,\n                fileChooserParams: FileChooserParams\n            ): Boolean {\n                uploadCallback?.onReceiveValue(null)\n                uploadCallback = filePathCallback\n                return try {\n                    startActivityForResult(fileChooserParams.createIntent(), uploadRequestCode)\n                    true\n                } catch (error: Exception) {\n                    uploadCallback = null\n                    Toast.makeText(this@MainActivity, "The file picker could not be opened", Toast.LENGTH_SHORT).show()\n                    false\n                }\n            }`;
    const chooserNew = `            override fun onShowFileChooser(\n                webView: WebView,\n                filePathCallback: ValueCallback<Array<Uri>>,\n                fileChooserParams: FileChooserParams\n            ): Boolean {\n                uploadCallback?.onReceiveValue(null)\n                uploadCallback = filePathCallback\n                val acceptsImage = fileChooserParams.acceptTypes.isEmpty() || fileChooserParams.acceptTypes.any { it.isBlank() || it.startsWith("image/") }\n                if (fileChooserParams.isCaptureEnabled && acceptsImage && launchBillCamera()) {\n                    return true\n                }\n                return try {\n                    capturedPhotoUri = null\n                    startActivityForResult(fileChooserParams.createIntent(), uploadRequestCode)\n                    true\n                } catch (error: Exception) {\n                    uploadCallback = null\n                    Toast.makeText(this@MainActivity, "The file picker could not be opened", Toast.LENGTH_SHORT).show()\n                    false\n                }\n            }`;
    if (!src.includes(chooserOld)) throw new Error('Native camera file chooser anchor not found');
    src = src.replace(chooserOld, chooserNew);

    const activityResultAnchor = `    @Deprecated("Deprecated in Android")\n    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {\n        super.onActivityResult(requestCode, resultCode, data)\n        if (requestCode == uploadRequestCode) {`;
    const activityResultReplacement = `    private inner class VoiceBridge {\n        @JavascriptInterface\n        fun start(prompt: String = "") {\n            runOnUiThread { startVoiceRecognition(prompt) }\n        }\n    }\n\n    private fun launchBillCamera(): Boolean {\n        return try {\n            val values = ContentValues().apply {\n                put(MediaStore.Images.Media.DISPLAY_NAME, "kirana_bill_" + System.currentTimeMillis() + ".jpg")\n                put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg")\n                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.Q) {\n                    put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/Kirana")\n                }\n            }\n            val uri = contentResolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values) ?: return false\n            capturedPhotoUri = uri\n            val cameraIntent = Intent(MediaStore.ACTION_IMAGE_CAPTURE).apply {\n                putExtra(MediaStore.EXTRA_OUTPUT, uri)\n                addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION or Intent.FLAG_GRANT_READ_URI_PERMISSION)\n            }\n            startActivityForResult(cameraIntent, uploadRequestCode)\n            true\n        } catch (error: Exception) {\n            capturedPhotoUri = null\n            false\n        }\n    }\n\n    private fun startVoiceRecognition(prompt: String = "") {\n        if (android.os.Build.VERSION.SDK_INT >= 23 && checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {\n            pendingVoiceStart = true\n            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), micPermissionRequestCode)\n            return\n        }\n        try {\n            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {\n                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)\n                putExtra(RecognizerIntent.EXTRA_LANGUAGE, "hi-IN")\n                putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, "hi-IN")\n                putExtra(RecognizerIntent.EXTRA_PROMPT, if (prompt.isBlank()) "Boliye" else prompt)\n                putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)\n            }\n            startActivityForResult(intent, voiceRequestCode)\n        } catch (error: Exception) {\n            webView.evaluateJavascript("window.KiranaVoiceError && window.KiranaVoiceError('voice-unavailable')", null)\n        }\n    }\n\n    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {\n        super.onRequestPermissionsResult(requestCode, permissions, grantResults)\n        if (requestCode != micPermissionRequestCode) return\n        val granted = grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED\n        pendingWebPermission?.let { req ->\n            if (granted) req.grant(arrayOf(PermissionRequest.RESOURCE_AUDIO_CAPTURE)) else req.deny()\n        }\n        pendingWebPermission = null\n        if (pendingVoiceStart) {\n            pendingVoiceStart = false\n            if (granted) startVoiceRecognition() else webView.evaluateJavascript("window.KiranaVoiceError && window.KiranaVoiceError('permission-denied')", null)\n        }\n    }\n\n    @Deprecated("Deprecated in Android")\n    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {\n        super.onActivityResult(requestCode, resultCode, data)\n        if (requestCode == voiceRequestCode) {\n            if (resultCode == RESULT_OK) {\n                val results = data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)\n                val heard = results?.firstOrNull().orEmpty()\n                if (heard.isNotBlank()) {\n                    val quoted = JSONObject.quote(heard)\n                    webView.evaluateJavascript("window.KiranaVoiceResult && window.KiranaVoiceResult(" + quoted + ")", null)\n                }\n            }\n            return\n        }\n        if (requestCode == uploadRequestCode) {`;
    if (!src.includes(activityResultAnchor)) {
      throw new Error('Native voice patch anchor not found in MainActivity');
    }
    src = src.replace(activityResultAnchor, activityResultReplacement);

    const uploadResultOld = `        if (requestCode == uploadRequestCode) {\n            uploadCallback?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data))\n            uploadCallback = null\n        }`;
    const uploadResultNew = `        if (requestCode == uploadRequestCode) {\n            val result = if (resultCode == RESULT_OK && data == null && capturedPhotoUri != null) {\n                arrayOf(capturedPhotoUri!!)\n            } else {\n                WebChromeClient.FileChooserParams.parseResult(resultCode, data)\n            }\n            uploadCallback?.onReceiveValue(result)\n            uploadCallback = null\n            if (resultCode != RESULT_OK && capturedPhotoUri != null) {\n                try { contentResolver.delete(capturedPhotoUri!!, null, null) } catch (_: Exception) {}\n            }\n            capturedPhotoUri = null\n        }`;
    if (!src.includes(uploadResultOld)) throw new Error('Native camera result anchor not found');
    src = src.replace(uploadResultOld, uploadResultNew);

    src = src.replace(/appVersion=105/g, 'appVersion=107');
    src = src.replace(/KiranaSoftwareNative\/1\.0\.5/g, 'KiranaSoftwareNative/1.0.7');

    config.modResults.contents = src;
    return config;
  });
}

module.exports = function withNativeVoiceBridgeV5(config) {
  config = withRecordAudioManifest(config);
  config = withNativeVoiceBridge(config);
  return config;
};
