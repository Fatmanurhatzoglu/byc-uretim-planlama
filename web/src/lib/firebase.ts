import { initializeApp, getApps, type FirebaseApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";
import { getFirestore, type Firestore } from "firebase/firestore";
import { FIREBASE_ROOT, FIREBASE_SCHEMA_VERSION } from "./constants";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

function assertConfig() {
  if (!firebaseConfig.apiKey || !firebaseConfig.projectId) {
    throw new Error(
      "Firebase yapılandırması eksik. web/.env.local dosyasını oluşturun (bkz. .env.example).",
    );
  }
}

let app: FirebaseApp;
let auth: Auth;
let db: Firestore;

export function getFirebaseApp(): FirebaseApp {
  if (!getApps().length) {
    assertConfig();
    app = initializeApp(firebaseConfig);
  } else {
    app = getApps()[0]!;
  }
  return app;
}

export function getFirebaseAuth(): Auth {
  if (!auth) auth = getAuth(getFirebaseApp());
  return auth;
}

export function getDb(): Firestore {
  if (!db) db = getFirestore(getFirebaseApp());
  return db;
}

export function schemaRef() {
  return { root: FIREBASE_ROOT, version: FIREBASE_SCHEMA_VERSION };
}
