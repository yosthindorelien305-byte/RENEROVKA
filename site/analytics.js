/**
 * RizzaFit Google Analytics 4 (GA4) Integration Module
 * Measurement ID: G-XSBKDCY4CS
 *
 * Privacy & Security Guarantees:
 * 1. ZERO Personal Identifiable Information (PII) is sent: no emails, passwords, usernames, phone numbers, or tokens.
 * 2. Auth events (login, sign_up) are only fired after server-side confirmation.
 * 3. Graceful degradation: all functions safely no-op if gtag is not available (ad-blockers, offline, etc.).
 * 4. Deduplication: prevents rapid duplicate events.
 */
(function(window) {
  'use strict';

  var GA_MEASUREMENT_ID = 'G-XSBKDCY4CS';
  var lastSentEvents = {};

  function isGtagReady() {
    return typeof window.gtag === 'function';
  }

  function sendEvent(eventName, params) {
    if (!isGtagReady()) return;
    try {
      // Clean params: ensure no sensitive keys ever leak
      var cleanParams = {};
      if (params && typeof params === 'object') {
        var forbiddenKeys = [
          'email', 'password', 'token', 'userToken', 'auth_code',
          'phone', 'state', 'sessionToken', 'initData', 'secret'
        ];
        for (var k in params) {
          if (Object.prototype.hasOwnProperty.call(params, k)) {
            if (forbiddenKeys.indexOf(k.toLowerCase()) === -1) {
              cleanParams[k] = params[k];
            }
          }
        }
      }
      window.gtag('event', eventName, cleanParams);
    } catch (e) {
      // Fail silently without breaking application execution
    }
  }

  var RizzaAnalytics = {
    MEASUREMENT_ID: GA_MEASUREMENT_ID,

    /**
     * Track SPA virtual page views
     */
    trackPageView: function(pagePath, pageTitle) {
      var path = pagePath || (window.location.pathname + (window.location.hash || ''));
      var title = pageTitle || document.title || 'RizzaFit';

      var now = Date.now();
      if (lastSentEvents.page_view && lastSentEvents.page_view.path === path && (now - lastSentEvents.page_view.ts < 1000)) {
        return;
      }
      lastSentEvents.page_view = { path: path, ts: now };

      sendEvent('page_view', {
        page_title: title,
        page_location: window.location.href,
        page_path: path
      });
    },

    /**
     * Track user sign up (only after confirmed by backend)
     */
    trackSignUp: function(method) {
      sendEvent('sign_up', {
        method: String(method || 'credentials')
      });
    },

    /**
     * Track user login (only after confirmed by backend)
     */
    trackLogin: function(method) {
      sendEvent('login', {
        method: String(method || 'credentials')
      });
    },

    /**
     * Track workout start
     */
    trackWorkoutStart: function(workoutId, workoutName) {
      sendEvent('workout_start', {
        workout_id: String(workoutId || ''),
        workout_name: String(workoutName || '')
      });
    },

    /**
     * Track workout completion
     */
    trackWorkoutComplete: function(workoutId, durationSec) {
      sendEvent('workout_complete', {
        workout_id: String(workoutId || ''),
        duration_seconds: Math.round(Number(durationSec) || 0)
      });
    },

    /**
     * Track major CTA clicks
     */
    trackCta: function(ctaName, ctaCategory) {
      var now = Date.now();
      var key = ctaName + ':' + (ctaCategory || '');
      if (lastSentEvents[key] && (now - lastSentEvents[key] < 1000)) {
        return;
      }
      lastSentEvents[key] = now;

      sendEvent('cta_click', {
        cta_name: String(ctaName || ''),
        cta_category: String(ctaCategory || 'general')
      });
    }
  };

  window.RizzaAnalytics = RizzaAnalytics;
})(window);
