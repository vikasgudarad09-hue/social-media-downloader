# Add project specific ProGuard rules here.
-keepattributes *Annotation*
-keepattributes JavascriptInterface

# Keep WebView JavaScript interface
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# Keep Kotlin metadata
-keep class kotlin.Metadata { *; }
