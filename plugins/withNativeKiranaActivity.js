const { withAndroidManifest, withMainActivity } = require("@expo/config-plugins");

const APP_URL = "https://web-production-02514.up.railway.app/?mobile=1&appVersion=103";

function kotlinSource(packageName) {
  return `package ${packageName}

import android.annotation.SuppressLint
import android.app.Activity
import android.app.DownloadManager
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.DownloadListener
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.ProgressBar
import android.widget.Toast

class MainActivity : Activity() {
    private lateinit var webView: WebView
    private lateinit var progressBar: ProgressBar
    private var fileChooserCallback: ValueCallback<Array<Uri>>? = null
    private val fileChooserRequestCode = 7301
    private val appUrl = "${APP_URL}"
    private val appHost = Uri.parse(appUrl).host.orEmpty()

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        window.statusBarColor = Color.rgb(8, 127, 191)
        window.navigationBarColor = Color.rgb(238, 247, 253)

        val root = FrameLayout(this).apply {
            setBackgroundColor(Color.rgb(238, 247, 253))
        }

        webView = WebView(this).apply {
            setBackgroundColor(Color.rgb(238, 247, 253))
            isFocusable = true
            isFocusableInTouchMode = true
            requestFocus(View.FOCUS_DOWN)
            overScrollMode = View.OVER_SCROLL_NEVER
            settings.apply {
                javaScriptEnabled = true
                domStorageEnabled = true
                databaseEnabled = true
                allowFileAccess = true
                allowContentAccess = true
                loadsImagesAutomatically = true
                loadWithOverviewMode = false
                useWideViewPort = true
                builtInZoomControls = false
                displayZoomControls = false
                setSupportMultipleWindows(false)
                javaScriptCanOpenWindowsAutomatically = true
                mediaPlaybackRequiresUserGesture = false
                cacheMode = WebSettings.LOAD_NO_CACHE
                mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
                userAgentString = userAgentString + " KiranaSoftwareNative/1.0.3"
            }

            CookieManager.getInstance().apply {
                setAcceptCookie(true)
                setAcceptThirdPartyCookies(this@apply, true)
            }

            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                    return handleUri(request.url)
                }

                @Deprecated("Deprecated in Android")
                override fun shouldOverrideUrlLoading(view: WebView, url: String): Boolean {
                    return handleUri(Uri.parse(url))
                }

                override fun onPageFinished(view: WebView, url: String) {
                    super.onPageFinished(view, url)
                    progressBar.visibility = View.GONE
                    view.requestFocus(View.FOCUS_DOWN)
                }

                override fun onReceivedError(
                    view: WebView,
                    request: WebResourceRequest,
                    error: WebResourceError
                ) {
                    super.onReceivedError(view, request, error)
                    if (request.isForMainFrame) {
                        progressBar.visibility = View.GONE
                        showErrorPage("Server se connection nahi ho paya")
                    }
                }
            }

            webChromeClient = object : WebChromeClient() {
                override fun onProgressChanged(view: WebView, newProgress: Int) {
                    progressBar.progress = newProgress
                    progressBar.visibility = if (newProgress >= 100) View.GONE else View.VISIBLE
                }

                override fun onShowFileChooser(
                    webView: WebView,
                    filePathCallback: ValueCallback<Array<Uri>>,
                    fileChooserParams: FileChooserParams
                ): Boolean {
                    fileChooserCallback?.onReceiveValue(null)
                    fileChooserCallback = filePathCallback
                    return try {
                        startActivityForResult(fileChooserParams.createIntent(), fileChooserRequestCode)
                        true
                    } catch (error: Exception) {
                        fileChooserCallback = null
                        Toast.makeText(this@MainActivity, "File picker nahi khul paya", Toast.LENGTH_SHORT).show()
                        false
                    }
                }
            }

            setDownloadListener(DownloadListener { url, userAgent, contentDisposition, mimeType, _ ->
                try {
                    val request = DownloadManager.Request(Uri.parse(url)).apply {
                        setMimeType(mimeType)
                        addRequestHeader("User-Agent", userAgent)
                        CookieManager.getInstance().getCookie(url)?.let { addRequestHeader("Cookie", it) }
                        setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                        setDestinationInExternalPublicDir(
                            Environment.DIRECTORY_DOWNLOADS,
                            android.webkit.URLUtil.guessFileName(url, contentDisposition, mimeType)
                        )
                    }
                    (getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager).enqueue(request)
                    Toast.makeText(this@MainActivity, "Download shuru ho gaya", Toast.LENGTH_SHORT).show()
                } catch (error: Exception) {
                    openExternal(Uri.parse(url))
                }
            })
        }

        progressBar = ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
            max = 100
            progress = 5
            isIndeterminate = false
        }

        root.addView(
            webView,
            FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        )
        root.addView(
            progressBar,
            FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(4)
            ).apply { gravity = Gravity.TOP }
        )

        setContentView(root)
        webView.loadUrl(appUrl)
    }

    private fun handleUri(uri: Uri): Boolean {
        val scheme = uri.scheme.orEmpty().lowercase()
        if (scheme == "kirana" && uri.host == "retry") {
            webView.loadUrl(appUrl)
            return true
        }

        if (scheme == "http" || scheme == "https") {
            return if (uri.host.equals(appHost, ignoreCase = true)) {
                false
            } else {
                openExternal(uri)
                true
            }
        }

        if (scheme == "intent") {
            return try {
                val intent = Intent.parseUri(uri.toString(), Intent.URI_INTENT_SCHEME)
                startActivity(intent)
                true
            } catch (error: Exception) {
                true
            }
        }

        if (scheme in setOf("tel", "mailto", "sms", "smsto", "whatsapp", "upi", "paytmmp")) {
            openExternal(uri)
            return true
        }

        return false
    }

    private fun openExternal(uri: Uri) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, uri))
        } catch (error: Exception) {
            Toast.makeText(this, "Is link ke liye app nahi mili", Toast.LENGTH_SHORT).show()
        }
    }

    private fun showErrorPage(message: String) {
        val escaped = message.replace("'", "\\'")
        val html = """
            <!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>
            <style>body{font-family:Arial,sans-serif;background:#eef7fd;color:#263545;margin:0;display:grid;place-items:center;min-height:100vh;padding:24px;box-sizing:border-box}.card{background:white;max-width:420px;padding:28px;border-radius:22px;box-shadow:0 12px 35px #075f9130;text-align:center}.logo{width:78px;height:78px;border-radius:23px;background:#0b82c2;color:white;display:grid;place-items:center;font-size:48px;font-weight:900;margin:auto}h2{margin:20px 0 8px}p{color:#687785;line-height:1.5}a{display:block;margin-top:22px;background:#0b82c2;color:white;text-decoration:none;padding:15px;border-radius:14px;font-weight:800}</style>
            </head><body><div class='card'><div class='logo'>K</div><h2>$escaped</h2><p>Internet check karke dobara try karein.</p><a href='kirana://retry'>Dobara Kholein</a></div></body></html>
        """.trimIndent()
        webView.loadDataWithBaseURL(appUrl, html, "text/html", "UTF-8", null)
    }

    @Deprecated("Deprecated in Android")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == fileChooserRequestCode) {
            val result = WebChromeClient.FileChooserParams.parseResult(resultCode, data)
            fileChooserCallback?.onReceiveValue(result)
            fileChooserCallback = null
        }
    }

    @Deprecated("Deprecated in Android")
    override fun onBackPressed() {
        if (::webView.isInitialized && webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    override fun onResume() {
        super.onResume()
        if (::webView.isInitialized) webView.onResume()
    }

    override fun onPause() {
        if (::webView.isInitialized) webView.onPause()
        super.onPause()
    }

    override fun onDestroy() {
        if (::webView.isInitialized) {
            webView.stopLoading()
            webView.webChromeClient = null
            webView.webViewClient = WebViewClient()
            webView.destroy()
        }
        super.onDestroy()
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()
}
`;
}

module.exports = function withNativeKiranaActivity(config) {
  config = withMainActivity(config, current => {
    const packageName = current.android?.package || "com.kiranasoftware.mobile";
    current.modResults.language = "kt";
    current.modResults.contents = kotlinSource(packageName);
    return current;
  });

  config = withAndroidManifest(config, current => {
    const application = current.modResults.manifest.application?.[0];
    if (application?.$) {
      application.$["android:hardwareAccelerated"] = "true";
      application.$["android:usesCleartextTraffic"] = "false";
      application.$["android:largeHeap"] = "true";
    }
    return current;
  });

  return config;
};
