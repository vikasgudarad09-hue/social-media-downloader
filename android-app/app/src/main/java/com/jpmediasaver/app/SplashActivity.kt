package com.jpmediasaver.app

import android.annotation.SuppressLint
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.appcompat.app.AppCompatActivity

@SuppressLint("CustomSplashScreen")
class SplashActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_splash)

        // Check if opened via share intent
        val sharedUrl = extractSharedUrl(intent)

        Handler(Looper.getMainLooper()).postDelayed({
            val mainIntent = Intent(this, MainActivity::class.java).apply {
                if (sharedUrl != null) {
                    putExtra("SHARED_URL", sharedUrl)
                }
            }
            startActivity(mainIntent)
            finish()
            overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out)
        }, 1500)
    }

    private fun extractSharedUrl(intent: Intent?): String? {
        if (intent?.action == Intent.ACTION_SEND && intent.type == "text/plain") {
            val text = intent.getStringExtra(Intent.EXTRA_TEXT) ?: return null
            // Extract URL from shared text
            val urlPattern = Regex("https?://[\\w\\-._~:/?#\\[\\]@!$&'()*+,;=%]+")
            return urlPattern.find(text)?.value
        }
        return null
    }
}
