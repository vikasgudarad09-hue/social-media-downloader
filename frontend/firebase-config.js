/**
 * Firebase Client Configuration & Helper Service for JPMediaSaver
 * 
 * SETUP INSTRUCTIONS:
 * 1. Go to https://console.firebase.google.com/ and create or select a project.
 * 2. In Project Settings, add a Web App ('</>') and copy the firebaseConfig values below.
 * 3. In the Firebase Console, enable:
 *    - Authentication -> Sign-in method -> Google & Anonymous
 *    - Firestore Database -> Create database (Production or Test mode)
 * 4. Paste your credentials into the `firebaseConfig` object below!
 */

const firebaseConfig = {
    apiKey: "AIzaSyD6T6r1Cha6RIIVRXSV6chK5wNzFcAbjM4",
    authDomain: "jpmediasaver.firebaseapp.com",
    projectId: "jpmediasaver",
    storageBucket: "jpmediasaver.firebasestorage.app",
    messagingSenderId: "393072926822",
    appId: "1:393072926822:web:82a673ab940893606d8da7",
    measurementId: "G-2NNQRJSCSX"
};

// Check if actual configuration has been supplied
const isFirebaseConfigured = Boolean(
    firebaseConfig.apiKey && 
    firebaseConfig.apiKey !== "YOUR_API_KEY" && 
    firebaseConfig.projectId !== "YOUR_PROJECT_ID"
);

let firebaseAuth = null;
let firestoreDb = null;
let firebaseAnalytics = null;

if (typeof firebase !== "undefined") {
    if (isFirebaseConfigured) {
        try {
            firebase.initializeApp(firebaseConfig);
            firebaseAuth = firebase.auth();
            firestoreDb = firebase.firestore();
            if (firebase.analytics && firebaseConfig.measurementId) {
                firebaseAnalytics = firebase.analytics();
            }
            console.log("🔥 Firebase initialized successfully in live mode.");
        } catch (err) {
            console.warn("⚠️ Firebase live initialization notice:", err);
        }
    } else {
        console.info("ℹ️ Firebase running in Demo/Standby mode. Add your config in frontend/firebase-config.js to activate live cloud sync.");
    }
}

// Local Storage Fallback Key for Standby Mode
const LOCAL_HISTORY_STORAGE_KEY = "jp_media_download_history_fallback";

/**
 * Sign in user with Google Popup
 */
async function authSignInWithGoogle() {
    if (!isFirebaseConfigured || !firebaseAuth) {
        // Fallback demo mode login
        const demoUser = {
            uid: "guest_" + Math.random().toString(36).substring(2, 9),
            displayName: "Guest User",
            email: "guest@example.com",
            photoURL: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80",
            isAnonymous: true
        };
        localStorage.setItem("jp_demo_user", JSON.stringify(demoUser));
        window.dispatchEvent(new CustomEvent("firebase-auth-state-changed", { detail: demoUser }));
        return demoUser;
    }

    try {
        const provider = new firebase.auth.GoogleAuthProvider();
        provider.setCustomParameters({ prompt: 'select_account' });
        const result = await firebaseAuth.signInWithPopup(provider);
        return result.user;
    } catch (error) {
        console.error("Google Sign-In failed:", error);
        throw error;
    }
}

/**
 * Sign in anonymously (Guest session)
 */
async function authSignInAnonymously() {
    if (!isFirebaseConfigured || !firebaseAuth) {
        const demoUser = {
            uid: "guest_" + Math.random().toString(36).substring(2, 9),
            displayName: "Guest User",
            email: null,
            photoURL: null,
            isAnonymous: true
        };
        localStorage.setItem("jp_demo_user", JSON.stringify(demoUser));
        window.dispatchEvent(new CustomEvent("firebase-auth-state-changed", { detail: demoUser }));
        return demoUser;
    }

    try {
        const result = await firebaseAuth.signInAnonymously();
        return result.user;
    } catch (error) {
        console.error("Anonymous Sign-In failed:", error);
        throw error;
    }
}

/**
 * Sign out current user
 */
async function authSignOut() {
    if (!isFirebaseConfigured || !firebaseAuth) {
        localStorage.removeItem("jp_demo_user");
        window.dispatchEvent(new CustomEvent("firebase-auth-state-changed", { detail: null }));
        return;
    }

    try {
        await firebaseAuth.signOut();
    } catch (error) {
        console.error("Sign-out failed:", error);
        throw error;
    }
}

/**
 * Listen for Auth state changes
 */
function onFirebaseAuthStateChanged(callback) {
    if (isFirebaseConfigured && firebaseAuth) {
        return firebaseAuth.onAuthStateChanged(callback);
    } else {
        // Standby mode check
        const savedDemo = localStorage.getItem("jp_demo_user");
        if (savedDemo) {
            try {
                callback(JSON.parse(savedDemo));
            } catch (e) {
                callback(null);
            }
        } else {
            callback(null);
        }

        const customListener = (e) => callback(e.detail);
        window.addEventListener("firebase-auth-state-changed", customListener);
        return () => window.removeEventListener("firebase-auth-state-changed", customListener);
    }
}

/**
 * Get current ID token to send in backend Authorization header
 */
async function getFirebaseIdToken() {
    if (isFirebaseConfigured && firebaseAuth && firebaseAuth.currentUser) {
        try {
            return await firebaseAuth.currentUser.getIdToken();
        } catch (e) {
            console.warn("Could not retrieve Firebase ID token:", e);
            return null;
        }
    }
    return null;
}

/**
 * Save extracted/downloaded video to user's history
 */
async function saveDownloadToFirestore(record) {
    const downloadItem = {
        title: record.title || "Media Download",
        url: record.url || "",
        platform: record.platform || "Unknown",
        thumbnail: record.thumbnail || "",
        duration: record.duration || 0,
        duration_formatted: record.duration_formatted || "00:00",
        download_url: record.video_url || record.url || "",
        audio_url: record.audio_url || "",
        timestamp: new Date().toISOString()
    };

    const currentUser = (firebaseAuth && firebaseAuth.currentUser) || 
        (localStorage.getItem("jp_demo_user") ? JSON.parse(localStorage.getItem("jp_demo_user")) : null);

    const uid = currentUser ? currentUser.uid : "anonymous_session";

    if (isFirebaseConfigured && firestoreDb && currentUser && !currentUser.isAnonymous) {
        try {
            await firestoreDb.collection("users").document(uid).collection("downloads").add({
                ...downloadItem,
                created_at: firebase.firestore.FieldValue.serverTimestamp()
            });
            console.log("Recorded download in Cloud Firestore.");
            return true;
        } catch (err) {
            console.warn("Firestore save failed, falling back to local cache:", err);
        }
    }

    // Fallback: save to LocalStorage
    try {
        let history = JSON.parse(localStorage.getItem(LOCAL_HISTORY_STORAGE_KEY) || "[]");
        // Keep unique by url
        history = history.filter(item => item.url !== downloadItem.url);
        history.unshift(downloadItem);
        // Keep top 30 items
        if (history.length > 30) history = history.slice(0, 30);
        localStorage.setItem(LOCAL_HISTORY_STORAGE_KEY, JSON.stringify(history));
        return true;
    } catch (e) {
        console.error("Local history cache error:", e);
        return false;
    }
}

/**
 * Load user's past downloads
 */
async function loadUserDownloads() {
    const currentUser = (firebaseAuth && firebaseAuth.currentUser) || 
        (localStorage.getItem("jp_demo_user") ? JSON.parse(localStorage.getItem("jp_demo_user")) : null);

    const uid = currentUser ? currentUser.uid : null;

    if (isFirebaseConfigured && firestoreDb && uid && currentUser && !currentUser.isAnonymous) {
        try {
            const snapshot = await firestoreDb
                .collection("users")
                .document(uid)
                .collection("downloads")
                .orderBy("created_at", "desc")
                .limit(25)
                .get();

            const items = [];
            snapshot.forEach(doc => {
                items.push({ id: doc.id, ...doc.data() });
            });
            return items;
        } catch (err) {
            console.warn("Could not query Firestore history, reading local:", err);
        }
    }

    // Local fallback
    try {
        return JSON.parse(localStorage.getItem(LOCAL_HISTORY_STORAGE_KEY) || "[]");
    } catch (e) {
        return [];
    }
}

/**
 * Clear user's download history
 */
async function clearUserDownloads() {
    localStorage.removeItem(LOCAL_HISTORY_STORAGE_KEY);
    const currentUser = (firebaseAuth && firebaseAuth.currentUser);
    if (isFirebaseConfigured && firestoreDb && currentUser && !currentUser.isAnonymous) {
        try {
            const snapshot = await firestoreDb.collection("users").document(currentUser.uid).collection("downloads").get();
            const batch = firestoreDb.batch();
            snapshot.docs.forEach(doc => batch.delete(doc.ref));
            await batch.commit();
        } catch (err) {
            console.warn("Failed clearing Firestore history:", err);
        }
    }
}

// Export for app.js usage
window.JPFirebase = {
    isConfigured: isFirebaseConfigured,
    signInWithGoogle: authSignInWithGoogle,
    signInAnonymously: authSignInAnonymously,
    signOut: authSignOut,
    onAuthStateChanged: onFirebaseAuthStateChanged,
    getIdToken: getFirebaseIdToken,
    saveDownload: saveDownloadToFirestore,
    loadDownloads: loadUserDownloads,
    clearDownloads: clearUserDownloads
};
