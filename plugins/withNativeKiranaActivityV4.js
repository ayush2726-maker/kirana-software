const { withAndroidManifest, withMainActivity } = require("@expo/config-plugins");

const APP_URL = "https://web-production-02514.up.railway.app/native-owner?mobile=1&appVersion=105";
const LOGIN_URL = "https://web-production-02514.up.railway.app/owner-login?native=1";

function makeMainActivity(packageName) {
  return `package ${packageName}

import android.annotation.SuppressLint
import android.app.Activity
import android.app.DownloadManager
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.net.http.SslError
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.webkit.CookieManager
import android.webkit.RenderProcessGoneDetail
import android.webkit.SslErrorHandler
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast

class MainActivity : Activity() {
    private lateinit var webView: WebView
    private lateinit var progressBar: ProgressBar
    private lateinit var loadingOverlay: LinearLayout
    private lateinit var loadingTitle: TextView
    private lateinit var loadingMessage: TextView
    private lateinit var retryButton: Button
    private lateinit var loginButton: Button

    private var uploadCallback: ValueCallback<Array<Uri>>? = null
    private val uploadRequestCode = 7301
    private val startUrl = "${APP_URL}"
    private val loginUrl = "${LOGIN_URL}"
    private val startHost = Uri.parse(startUrl).host.orEmpty()
    private val timeoutHandler = Handler(Looper.getMainLooper())
    private var timeoutRunnable: Runnable? = null
    private var pageCommitted = false
    private var rendererGone = false
    private var lastExitBackAt = 0L
    private var backCallbackPending = false

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        window.statusBarColor = Color.rgb(8, 127, 191)
        window.navigationBarColor = Color.rgb(238, 247, 253)

        val root = FrameLayout(this).apply {
            setBackgroundColor(Color.rgb(238, 247, 253))
        }

        webView = WebView(this)
        configureWebView(webView)
        webView.visibility = View.INVISIBLE

        progressBar = ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
            max = 100
            progress = 5
            isIndeterminate = false
        }

        loadingOverlay = buildLoadingOverlay()

        root.addView(
            webView,
            FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )
        )
        root.addView(
            loadingOverlay,
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

        // Clear only cached page files. Owner login cookies are preserved.
        webView.clearCache(true)
        CookieManager.getInstance().flush()
        loadOwner(startUrl)
    }

    private fun buildLoadingOverlay(): LinearLayout {
        val overlay = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setPadding(dp(30), dp(30), dp(30), dp(30))
            setBackgroundColor(Color.rgb(238, 247, 253))
        }

        val logo = TextView(this).apply {
            text = "K"
            textSize = 54f
            gravity = Gravity.CENTER
            setTextColor(Color.WHITE)
            setBackgroundColor(Color.rgb(29, 151, 211))
        }
        overlay.addView(logo, LinearLayout.LayoutParams(dp(108), dp(108)))

        loadingTitle = TextView(this).apply {
            text = "Kirana Software"
            textSize = 28f
            gravity = Gravity.CENTER
            setTextColor(Color.rgb(38, 53, 69))
            setPadding(0, dp(22), 0, 0)
        }
        overlay.addView(
            loadingTitle,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            )
        )

        loadingMessage = TextView(this).apply {
            text = "Loading your business..."
            textSize = 17f
            gravity = Gravity.CENTER
            setTextColor(Color.rgb(105, 122, 136))
            setPadding(0, dp(12), 0, dp(16))
        }
        overlay.addView(
            loadingMessage,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            )
        )

        retryButton = Button(this).apply {
            text = "Retry App"
            visibility = View.GONE
            setOnClickListener {
                if (rendererGone) recreate() else loadOwner(cacheBusted(startUrl))
            }
        }
        overlay.addView(
            retryButton,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(58)
            ).apply {
                topMargin = dp(10)
                marginStart = dp(24)
                marginEnd = dp(24)
            }
        )

        loginButton = Button(this).apply {
            text = "Login Again"
            visibility = View.GONE
            setOnClickListener {
                if (rendererGone) recreate() else loadOwner(cacheBusted(loginUrl))
            }
        }
        overlay.addView(
            loginButton,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                dp(58)
            ).apply {
                topMargin = dp(10)
                marginStart = dp(24)
                marginEnd = dp(24)
            }
        )

        return overlay
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView(target: WebView) {
        target.apply {
            setBackgroundColor(Color.rgb(238, 247, 253))
            isFocusable = true
            isFocusableInTouchMode = true
            overScrollMode = View.OVER_SCROLL_NEVER
            requestFocus(View.FOCUS_DOWN)
        }

        target.settings.apply {
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
            cacheMode = WebSettings.LOAD_DEFAULT
            mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
            userAgentString = userAgentString + " KiranaSoftwareNative/1.0.5"
        }

        CookieManager.getInstance().apply {
            setAcceptCookie(true)
            setAcceptThirdPartyCookies(target, true)
        }

        target.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                return handleUri(request.url)
            }

            @Deprecated("Deprecated in Android")
            override fun shouldOverrideUrlLoading(view: WebView, url: String): Boolean {
                return handleUri(Uri.parse(url))
            }

            override fun onPageStarted(view: WebView, url: String, favicon: android.graphics.Bitmap?) {
                super.onPageStarted(view, url, favicon)
                pageCommitted = false
                showLoading("Loading your business...")
                scheduleTimeout()
            }

            override fun onPageCommitVisible(view: WebView, url: String) {
                super.onPageCommitVisible(view, url)
                revealPage()
            }

            override fun onPageFinished(view: WebView, url: String) {
                super.onPageFinished(view, url)
                if (!pageCommitted) revealPage()
                view.requestFocus(View.FOCUS_DOWN)
            }

            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest,
                error: WebResourceError
            ) {
                super.onReceivedError(view, request, error)
                if (request.isForMainFrame) {
                    showFailure("The server page could not load. Check internet and retry.")
                }
            }

            override fun onReceivedHttpError(
                view: WebView,
                request: WebResourceRequest,
                errorResponse: WebResourceResponse
            ) {
                super.onReceivedHttpError(view, request, errorResponse)
                if (request.isForMainFrame && errorResponse.statusCode >= 400) {
                    showFailure("Server error ${'$'}{errorResponse.statusCode}. Please retry.")
                }
            }

            override fun onReceivedSslError(view: WebView, handler: SslErrorHandler, error: SslError) {
                handler.cancel()
                showFailure("Secure connection failed. Check phone date, time and internet.")
            }

            override fun onRenderProcessGone(view: WebView, detail: RenderProcessGoneDetail): Boolean {
                rendererGone = true
                showFailure("Android WebView stopped. Tap Retry App to restart it.")
                return true
            }
        }

        target.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView, newProgress: Int) {
                if (!pageCommitted) {
                    progressBar.progress = newProgress
                    progressBar.visibility = if (newProgress >= 100) View.GONE else View.VISIBLE
                }
            }

            override fun onShowFileChooser(
                webView: WebView,
                filePathCallback: ValueCallback<Array<Uri>>,
                fileChooserParams: FileChooserParams
            ): Boolean {
                uploadCallback?.onReceiveValue(null)
                uploadCallback = filePathCallback
                return try {
                    startActivityForResult(fileChooserParams.createIntent(), uploadRequestCode)
                    true
                } catch (error: Exception) {
                    uploadCallback = null
                    Toast.makeText(this@MainActivity, "The file picker could not be opened", Toast.LENGTH_SHORT).show()
                    false
                }
            }
        }

        target.setDownloadListener { url, userAgent, contentDisposition, mimeType, _ ->
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
                Toast.makeText(this, "Download started", Toast.LENGTH_SHORT).show()
            } catch (error: Exception) {
                openExternal(Uri.parse(url))
            }
        }
    }

    private fun cacheBusted(url: String): String {
        val uri = Uri.parse(url)
        return uri.buildUpon()
            .appendQueryParameter("reload", System.currentTimeMillis().toString())
            .build()
            .toString()
    }

    private fun scheduleTimeout() {
        timeoutRunnable?.let { timeoutHandler.removeCallbacks(it) }
        timeoutRunnable = Runnable {
            if (!pageCommitted) {
                webView.stopLoading()
                showFailure("The app took too long to load. Tap Retry App.")
            }
        }
        timeoutHandler.postDelayed(timeoutRunnable!!, 15000L)
    }

    private fun cancelTimeout() {
        timeoutRunnable?.let { timeoutHandler.removeCallbacks(it) }
        timeoutRunnable = null
    }

    private fun showLoading(message: String) {
        retryButton.visibility = View.GONE
        loginButton.visibility = View.GONE
        loadingTitle.text = "Kirana Software"
        loadingMessage.text = message
        loadingOverlay.visibility = View.VISIBLE
        webView.visibility = View.INVISIBLE
        progressBar.visibility = View.VISIBLE
    }

    private fun showFailure(message: String) {
        cancelTimeout()
        progressBar.visibility = View.GONE
        webView.visibility = View.INVISIBLE
        loadingOverlay.visibility = View.VISIBLE
        loadingTitle.text = "App could not open"
        loadingMessage.text = message
        retryButton.visibility = View.VISIBLE
        loginButton.visibility = View.VISIBLE
    }

    private fun revealPage() {
        pageCommitted = true
        rendererGone = false
        cancelTimeout()
        progressBar.visibility = View.GONE
        loadingOverlay.visibility = View.GONE
        webView.visibility = View.VISIBLE
    }

    private fun loadOwner(url: String) {
        pageCommitted = false
        showLoading("Loading your business...")
        webView.stopLoading()
        webView.loadUrl(
            url,
            mapOf(
                "Cache-Control" to "no-cache",
                "Pragma" to "no-cache"
            )
        )
        scheduleTimeout()
    }

    private fun nativeUrlFromRoot(uri: Uri): String {
        val builder = Uri.parse(startUrl).buildUpon()
        uri.getQueryParameter("handoff")?.let { builder.appendQueryParameter("handoff", it) }
        uri.getQueryParameter("session")?.let { builder.appendQueryParameter("session", it) }
        builder.appendQueryParameter("reload", System.currentTimeMillis().toString())
        return builder.build().toString()
    }

    private fun handleUri(uri: Uri): Boolean {
        val scheme = uri.scheme.orEmpty().lowercase()

        if (scheme == "kirana" && uri.host == "retry") {
            loadOwner(cacheBusted(startUrl))
            return true
        }

        if (scheme == "http" || scheme == "https") {
            if (!uri.host.equals(startHost, ignoreCase = true)) {
                openExternal(uri)
                return true
            }

            // Owner login redirects to the website root. Keep the owner APK on
            // its lightweight native route and preserve the one-time handoff.
            if (uri.path.orEmpty() == "/") {
                loadOwner(nativeUrlFromRoot(uri))
                return true
            }
            return false
        }

        if (scheme == "intent") {
            return try {
                startActivity(Intent.parseUri(uri.toString(), Intent.URI_INTENT_SCHEME))
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
            Toast.makeText(this, "No app is available for this link", Toast.LENGTH_SHORT).show()
        }
    }

    @Deprecated("Deprecated in Android")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == uploadRequestCode) {
            uploadCallback?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data))
            uploadCallback = null
        }
    }

    private fun handleExitBack() {
        val now = SystemClock.elapsedRealtime()
        if (now - lastExitBackAt <= 2000L) {
            finish()
            return
        }
        lastExitBackAt = now
        Toast.makeText(this, "Press back again to exit", Toast.LENGTH_SHORT).show()
    }

    private fun fallbackBack() {
        val currentPath = try { Uri.parse(webView.url.orEmpty()).path.orEmpty() } catch (_: Exception) { "" }
        if (webView.canGoBack() && currentPath !in setOf("", "/", "/native-owner", "/owner-login")) {
            webView.goBack()
        } else {
            handleExitBack()
        }
    }

    @Deprecated("Deprecated in Android")
    override fun onBackPressed() {
        if (!::webView.isInitialized) {
            handleExitBack()
            return
        }
        if (backCallbackPending) return
        backCallbackPending = true
        val script = """
            (function () {
              try {
                return (window.KiranaBack && window.KiranaBack.handle)
                  ? window.KiranaBack.handle()
                  : 'native';
              } catch (error) {
                return 'native';
              }
            })();
        """.trimIndent()
        webView.evaluateJavascript(script) { rawValue ->
            backCallbackPending = false
            val result = rawValue.orEmpty().trim().trim('"').lowercase()
            when (result) {
                "handled" -> Unit
                "home" -> handleExitBack()
                else -> fallbackBack()
            }
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
        cancelTimeout()
        if (::webView.isInitialized) {
            webView.stopLoading()
            webView.destroy()
        }
        super.onDestroy()
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()
}
`;
}

module.exports = function withNativeKiranaActivityV4(config) {
  config = withMainActivity(config, current => {
    const packageName = current.android?.package || "com.kiranasoftware.mobile";
    current.modResults.language = "kt";
    current.modResults.contents = makeMainActivity(packageName);
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
