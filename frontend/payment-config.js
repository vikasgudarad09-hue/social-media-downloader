/**
 * Payment & Support Configuration for JPMediaSaver
 * 
 * Configured with official details for:
 * - UPI: PhonePe / GPay / Paytm (India)
 * - PayPal: International payments
 */

const PAYMENT_CONFIG = {
    creatorName: "Vikas Prabhu Gudarad",

    // ==========================================
    // 🇮🇳 UPI CONFIGURATION (India)
    // ==========================================
    // Official PhonePe / UPI ID decoded from your QR poster
    upiId: "vickyunion99@ibl",
    
    // Payee Name registered with bank / PhonePe
    upiPayeeName: "VIKAS PRABHU GUDARAD",

    // Path to your authentic PhonePe QR banner
    phonePeQrImage: "images/phonepe_qr.jpg",

    // Default amount in INR
    defaultUpiAmount: 100,

    // Preset suggested amounts in INR
    suggestedAmountsINR: [
        { label: "₹50 (Chai ☕)", amount: 50 },
        { label: "₹100 (Coffee ☕)", amount: 100 },
        { label: "₹200 (Snack 🥪)", amount: 200 },
        { label: "₹500 (Super Fan ⭐)", amount: 500 }
    ],

    // ==========================================
    // 🌍 PAYPAL CONFIGURATION (International)
    // ==========================================
    // Your registered PayPal email ID
    paypalEmail: "gudaradvikas09@gmail.com",

    // Direct PayPal Donation Link
    paypalUrl: "https://www.paypal.com/donate?business=gudaradvikas09@gmail.com&no_recurring=0&currency_code=USD",

    // Preset suggested amounts in USD
    suggestedAmountsUSD: [
        { label: "$3 (Coffee ☕)", amount: 3 },
        { label: "$5 (Snack 🥪)", amount: 5 },
        { label: "$10 (Lunch 🍕)", amount: 10 },
        { label: "$25 (Supporter ⭐)", amount: 25 }
    ]
};

// Export to window for global access
window.JPPaymentConfig = PAYMENT_CONFIG;
