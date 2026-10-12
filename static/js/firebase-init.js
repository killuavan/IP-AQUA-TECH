(function () {
  'use strict';

  const config = window.IP_AQUA_FIREBASE_CONFIG || {};
  if (!config || !config.apiKey || !config.projectId) {
    return;
  }

  if (!window.firebase) {
    console.warn('Firebase SDK was not loaded before firebase-init.js');
    return;
  }

  const existingApp = window.firebase.apps && window.firebase.apps.length
    ? window.firebase.apps[0]
    : null;

  const app = existingApp || window.firebase.initializeApp(config);
  const database = window.firebase.database ? window.firebase.database(app) : null;
  const firestore = window.firebase.firestore ? window.firebase.firestore(app) : null;
  const analytics = window.firebase.analytics ? window.firebase.analytics(app) : null;

  window.IP_AQUA_FIREBASE = {
    app,
    config,
    database,
    firestore,
    analytics,
  };

  if (database) {
    console.info('Firebase Realtime Database initialized');
  }
  if (firestore) {
    console.info('Firebase Firestore initialized');
  }
  if (analytics) {
    console.info('Firebase Analytics initialized');
  }
})();
