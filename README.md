<div align="center">

  <img src="docs/screenshots/logo.jpg" alt="Jayaprabhu Creations Logo" width="120" style="border-radius: 50%; box-shadow: 0 0 25px rgba(245, 158, 11, 0.5);" />

  # JPMediaSaver
  ### Jayaprabhu Universal Social Media Downloader

  <p align="center">
    A fast, modern, and privacy-first web application for extracting and downloading media from YouTube, Instagram Reels, TikTok, Facebook, Twitter/X, Pinterest, and more.
  </p>

  <p align="center">
    <a href="https://jpmediasaver.web.app" target="_blank">
      <img src="https://img.shields.io/badge/Live_Demo-jpmediasaver.web.app-brightgreen?style=for-the-badge&logo=firebase" alt="Live Demo" />
    </a>
    <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" alt="Python 3.10+" />
    <img src="https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=for-the-badge&logo=fastapi" alt="FastAPI" />
    <img src="https://img.shields.io/badge/Firebase-Hosting_%26_Functions-orange?style=for-the-badge&logo=firebase" alt="Firebase" />
    <img src="https://img.shields.io/badge/Tailwind_CSS-3.4-38B2AC?style=for-the-badge&logo=tailwind-css" alt="Tailwind CSS" />
    <img src="https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge" alt="MIT License" />
  </p>

  <p align="center">
    <b>🌐 Official Live Website:</b> <a href="https://jpmediasaver.web.app">https://jpmediasaver.web.app</a>
  </p>

</div>

---

## 📸 Visual Showcase

### 1. Cinematic Brand Entrance (5-Second Logo Reveal)
When opening the site, visitors are welcomed with an elegant, glowing 5-second brand reveal for **Jayaprabhu Creations** with a synchronized animated progress indicator and quick-skip option.

<div align="center">
  <img src="docs/screenshots/splash_screen.png" alt="Jayaprabhu Creations Entrance" width="850" style="border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);" />
</div>

---

### 2. Universal Media Extraction Interface
Sleek dark-mode interface built with Tailwind CSS, supporting automatic link paste, instant platform detection, stream selection, and video/audio downloads.

<div align="center">
  <img src="docs/screenshots/app_preview.png" alt="JPMediaSaver Main App Interface" width="850" style="border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);" />
</div>

---

### 3. Integrated Creator Support & Donations

<div align="center">

| 🇮🇳 UPI / PhonePe (India) | 🌍 PayPal (International) |
| :---: | :---: |
| <img src="docs/screenshots/phonepe_qr.jpg" alt="PhonePe QR Code - Vikas Prabhu Gudarad" width="220" style="border-radius: 12px; border: 2px solid #a855f7;" /><br><br><b>UPI ID:</b> <code>vickyunion99@ibl</code><br><b>Payee Name:</b> VIKAS PRABHU GUDARAD<br><i>Scan with PhonePe, Google Pay, Paytm, BHIM</i> | <br><br><a href="https://www.paypal.com/donate?business=gudaradvikas09@gmail.com&no_recurring=0&currency_code=USD" target="_blank"><img src="https://img.shields.io/badge/Donate-PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white" alt="Donate with PayPal" /></a><br><br><b>PayPal Account:</b><br><code>gudaradvikas09@gmail.com</code><br><br><i>Supports Credit Cards, Debit Cards & PayPal Balance</i> |

</div>

---

## 🚀 Key Features

* **Multi-Platform Support**: Downloads video and audio from YouTube (Shorts & long videos), Instagram Reels/Stories, TikTok (without watermark), Facebook, Twitter/X, Pinterest, Reddit, and more.
* **100% Serverless on Google Cloud**:
  * Frontend hosted on **Firebase Hosting** with global CDN caching.
  * Backend runs on **Firebase Cloud Functions (2nd Gen Python)** with auto-scaling and zero server maintenance.
* **Unified Domain Architecture**: Both frontend and backend serve from `jpmediasaver.web.app`, eliminating CORS problems.
* **Custom Support / Donation Options**:
  * Indian supporters can pay any custom INR amount directly to PhonePe/GPay UPI (`vickyunion99@ibl`).
  * International supporters can donate any custom USD amount via official PayPal checkout.
* **Strict 100% Non-Adult & Clean Ad Integration**:
  * Monitored Adsterra 728x90 banner and native recommendations with adult/gambling filters active.
* **Zero Data Retention Policy**: We do not store downloaded files or search history; media streams directly from CDNs.
* **Download History Tracking**: Optional local storage and Firebase Firestore user history synchronization.

---

## 🛠️ Architecture & Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | Vanilla JavaScript (ES6+), Tailwind CSS (CDN), FontAwesome 6, Plus Jakarta Sans |
| **Backend** | Python 3.10, FastAPI, `yt-dlp`, `pytubefix`, `a2wsgi`, Firebase Admin SDK |
| **Cloud & Deployment** | Google Firebase Hosting, Firebase Cloud Functions (2nd Gen / Cloud Run) |
| **Payment Integrations** | UPI Deep-Linking (`upi://pay`), PayPal Donate |
| **Monetization** | Adsterra (Filtered clean 728x90 Banner, Native Recommendations) |

---

## 📂 Project Structure

```
social-media-downloader/
├── frontend/                     # Static Web App (Firebase Hosting root)
│   ├── index.html                # Main UI with Tailwind & Modals
│   ├── app.js                    # Core client logic & API handlers
│   ├── style.css                 # Glassmorphic styles & CSS keyframes
│   ├── firebase-config.js        # Firebase Client SDK initialization
│   ├── payment-config.js         # UPI and PayPal donation configuration
│   ├── logo.jpg                  # Jayaprabhu Creations emblem
│   └── images/                   # Book covers, QR banners & assets
├── functions/                    # 2nd Gen Firebase Cloud Functions (Python)
│   ├── main.py                   # Serverless ASGI function entrypoint
│   ├── requirements.txt          # Python dependencies for Cloud Functions
│   └── app/                      # Application backend logic
│       ├── main.py               # FastAPI application definition
│       ├── extractors/           # Platform-specific extractors (yt-dlp)
│       └── models.py             # Pydantic data schemas
├── backend/                      # Standalone / Local development backend
├── docs/screenshots/            # High-resolution README preview images
├── firebase.json                 # Firebase Hosting & Function rewrites
├── .firebaserc                   # Firebase project bindings (jpmediasaver)
└── .gitignore                    # Environment & credential exclusions
```

---

## ⚡ Quickstart (Local Development)

### 1. Clone the repository
```bash
git clone https://github.com/vikasgudarad09-hue/social-media-downloader.git
cd social-media-downloader
```

### 2. Run the Backend locally
```bash
cd backend
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. Open the Frontend
Open `frontend/index.html` in your browser (or use VS Code Live Server). The frontend will automatically route requests to `http://localhost:8000` when running locally!

---

## ☁️ Deployment to Firebase

To deploy both the frontend and backend directly to Google Cloud:

```bash
# 1. Login to Firebase CLI
firebase login

# 2. Deploy to live project
firebase deploy
```

---

## ☕ Support the Creator

If you find **JPMediaSaver** helpful, feel free to support ongoing server and development costs:

* **UPI (India 🇮🇳)**: `vickyunion99@ibl` (*VIKAS PRABHU GUDARAD*)
* **PayPal (Global 🌍)**: [gudaradvikas09@gmail.com](https://www.paypal.com/donate?business=gudaradvikas09@gmail.com&no_recurring=0&currency_code=USD)
* **Created by**: **Jayaprabhu Creations**

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
