package com.jpmediasaver.app

import android.annotation.SuppressLint
import android.content.Intent
import android.graphics.Bitmap
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Bundle
import android.view.View
import android.webkit.*
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ProgressBar
import androidx.appcompat.app.AppCompatActivity
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var progressBar: ProgressBar
    private lateinit var swipeRefresh: SwipeRefreshLayout
    private lateinit var offlineView: LinearLayout
    private lateinit var retryButton: Button

    companion object {
        const val WEBSITE_URL = "https://jpmediasaver.netlify.app"
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // Initialize views
        webView = findViewById(R.id.webView)
        progressBar = findViewById(R.id.progressBar)
        swipeRefresh = findViewById(R.id.swipeRefresh)
        offlineView = findViewById(R.id.offlineView)
        retryButton = findViewById(R.id.retryButton)

        // Setup WebView
        setupWebView()

        // Setup swipe-to-refresh
        swipeRefresh.setColorSchemeColors(
            getColor(R.color.purple_500),
            getColor(R.color.purple_700)
        )
        swipeRefresh.setOnRefreshListener {
            webView.reload()
        }

        // Retry button
        retryButton.setOnClickListener {
            if (isNetworkAvailable()) {
                offlineView.visibility = View.GONE
                webView.visibility = View.VISIBLE
                webView.reload()
            }
        }

        // Load the website or shared URL
        val sharedUrl = intent.getStringExtra("SHARED_URL")
        if (sharedUrl != null) {
            // Auto-paste the shared URL into the website
            val urlWithParam = "$WEBSITE_URL?url=${java.net.URLEncoder.encode(sharedUrl, "UTF-8")}"
            webView.loadUrl(urlWithParam)
        } else {
            webView.loadUrl(WEBSITE_URL)
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            allowFileAccess = true
            allowContentAccess = true
            loadWithOverviewMode = true
            useWideViewPort = true
            cacheMode = WebSettings.LOAD_DEFAULT
            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            mediaPlaybackRequiresUserGesture = false
            setSupportZoom(false)
            builtInZoomControls = false
        }

        // Handle page loading progress
        webView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                if (newProgress < 100) {
                    progressBar.visibility = View.VISIBLE
                    progressBar.progress = newProgress
                } else {
                    progressBar.visibility = View.GONE
                    swipeRefresh.isRefreshing = false
                }
            }
        }

        // Handle page navigation
        webView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                super.onPageStarted(view, url, favicon)
                progressBar.visibility = View.VISIBLE
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                progressBar.visibility = View.GONE
                swipeRefresh.isRefreshing = false

                // Inject CSS to hide browser-specific elements and adapt to app
                view?.evaluateJavascript("""
                    (function() {
                        // Add app-mode class to body
                        document.body.classList.add('app-mode');
                        // Hide any "open in browser" links
                        var style = document.createElement('style');
                        style.textContent = 'body { -webkit-tap-highlight-color: transparent; }';
                        document.head.appendChild(style);
                    })();
                """.trimIndent(), null)
            }

            override fun shouldOverrideUrlLoading(
                view: WebView?,
                request: WebResourceRequest?
            ): Boolean {
                val url = request?.url?.toString() ?: return false

                // Keep navigation within our domain inside WebView
                return if (url.contains("jpmediasaver.netlify.app") ||
                    url.contains("social-media-downloader-production")) {
                    false // Load in WebView
                } else {
                    // Open external links (download URLs, ads) in browser
                    val intent = Intent(Intent.ACTION_VIEW, request.url)
                    startActivity(intent)
                    true
                }
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?
            ) {
                if (request?.isForMainFrame == true) {
                    webView.visibility = View.GONE
                    offlineView.visibility = View.VISIBLE
                }
            }
        }
    }

    private fun isNetworkAvailable(): Boolean {
        val cm = getSystemService(CONNECTIVITY_SERVICE) as ConnectivityManager
        val network = cm.activeNetwork ?: return false
        val capabilities = cm.getNetworkCapabilities(network) ?: return false
        return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        // Handle new share intents while app is running
        val sharedUrl = intent?.getStringExtra(Intent.EXTRA_TEXT)
        if (sharedUrl != null) {
            val urlPattern = Regex("https?://[\\w\\-._~:/?#\\[\\]@!$&'()*+,;=%]+")
            val url = urlPattern.find(sharedUrl)?.value
            if (url != null) {
                val urlWithParam = "$WEBSITE_URL?url=${java.net.URLEncoder.encode(url, "UTF-8")}"
                webView.loadUrl(urlWithParam)
            }
        }
    }
}
