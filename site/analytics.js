/**
 * RizzaFit Google Analytics 4 (GA4) Integration Module
 * Measurement ID: G-XSBKDCY4CS
 *
 * Privacy & Security Guarantees:
 * 1. ZERO Personal Identifiable Information (PII) is sent: no emails, passwords, usernames, phone numbers, or tokens.
 * 2. Auth events (login, sign_up) are only fired after server-side confirmation.
 * 3. URLs and paths are strictly sanitized: all query parameters and sensitive fragments are stripped.
 * 4. Deduplication is decoupled: virtual page views are deduped by path transition, user events are not blocked.
 * 5. Graceful degradation: all functions safely no-op if gtag is not available (ad-blockers, offline, etc.).
 */
(function(window) {
  'use strict';

  var GA_MEASUREMENT_ID = 'G-XSBKDCY4CS';

  // Strict list of normalized forbidden parameter keys (all lowercase, no punctuation)
  var FORBIDDEN_NORM_KEYS = [
    'email', 'password', 'token', 'usertoken', 'authcode', 'phone',
    'state', 'sessiontoken', 'initdata', 'secret', 'code', 'ref',
    'authorization', 'hash', 'tgwebappdata', 'bottoken', 'accesstoken',
    'refreshtoken', 'apikey', 'username', 'user'
  ];

  // Regex patterns for detecting and scrubbing PII in string values
  var EMAIL_REGEX = /[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/g;
  var JWT_REGEX = /ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}(?:\.[A-Za-z0-9_-]+)?/g;
  var BEARER_REGEX = /bearer\s+[a-zA-Z0-9._-]+/gi;
  var LONG_HEX_TOKEN_REGEX = /\b[0-9a-fA-F]{24,}\b/g;
  var PHONE_REGEX = /(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/g;

  var lastPagePath = null;
  var lastActionTime = 0;
  var lastActionKey = '';

  function isGtagReady() {
    return typeof window.gtag === 'function';
  }

  function normalizeKey(k) {
    if (!k || typeof k !== 'string') return '';
    return k.toLowerCase().replace(/[-_]/g, '');
  }

  function sanitizeString(str) {
    if (!str || typeof str !== 'string') return '';
    return str
      .replace(EMAIL_REGEX, '[REDACTED_EMAIL]')
      .replace(BEARER_REGEX, 'Bearer [REDACTED_TOKEN]')
      .replace(JWT_REGEX, '[REDACTED_TOKEN]')
      .replace(LONG_HEX_TOKEN_REGEX, '[REDACTED_TOKEN]')
      .replace(PHONE_REGEX, '[REDACTED_PHONE]');
  }

  function sanitizeValue(val) {
    if (val === null || val === undefined) return val;
    if (typeof val === 'string') {
      return sanitizeString(val);
    }
    if (typeof val === 'number' || typeof val === 'boolean') {
      return val;
    }
    if (Array.isArray(val)) {
      var cleanArr = [];
      for (var i = 0; i < val.length; i++) {
        cleanArr.push(sanitizeValue(val[i]));
      }
      return cleanArr;
    }
    if (typeof val === 'object') {
      return sanitizeParams(val);
    }
    return sanitizeString(String(val));
  }

  function sanitizeParams(params) {
    if (!params || typeof params !== 'object') return {};
    var clean = {};
    for (var k in params) {
      if (Object.prototype.hasOwnProperty.call(params, k)) {
        var norm = normalizeKey(k);
        if (FORBIDDEN_NORM_KEYS.indexOf(norm) !== -1) {
          continue; // Strip forbidden sensitive key
        }
        clean[k] = sanitizeValue(params[k]);
      }
    }
    return clean;
  }

  function getSafeLocation(rawUrl) {
    var str = rawUrl || (window.location ? window.location.href : '');
    try {
      var URLCtor = window.URL || (typeof URL !== 'undefined' ? URL : null);
      if (URLCtor) {
        var base = (window.location && window.location.origin) ? window.location.origin : 'https://rizzafit.ru';
        var urlObj = new URLCtor(str, base);
        var safeHash = '';
        if (urlObj.hash) {
          var match = urlObj.hash.match(/^#\/[a-zA-Z0-9_-]+(?:\/[a-zA-Z0-9_-]+)*/);
          if (match) {
            safeHash = match[0];
          } else if (urlObj.hash === '#/' || urlObj.hash === '#') {
            safeHash = '#/';
          }
        }
        return urlObj.origin + urlObj.pathname + safeHash;
      }
    } catch (e) {}
    // Fallback if URL constructor throws or is absent
    var origin = (window.location && window.location.origin) ? window.location.origin : 'https://rizzafit.ru';
    var safeP = getSafePath(str);
    return origin + (safeP.startsWith('/') ? safeP : '/' + safeP);
  }

  function getSafePath(rawPath) {
    if (!rawPath || typeof rawPath !== 'string') {
      var p = (window.location && window.location.pathname) ? window.location.pathname : '/';
      var h = (window.location && window.location.hash) ? window.location.hash : '';
      rawPath = p + h;
    }
    // If rawPath is a full URL, extract path and hash
    if (/^[a-zA-Z]+:\/\//.test(rawPath)) {
      try {
        var u = new URL(rawPath);
        rawPath = u.pathname + (u.hash || '');
      } catch (e) {}
    }
    var hashIdx = rawPath.indexOf('#');
    var basePath = hashIdx !== -1 ? rawPath.slice(0, hashIdx) : rawPath;
    var hashPart = hashIdx !== -1 ? rawPath.slice(hashIdx) : '';
    basePath = basePath.split('?')[0] || '/';
    var safeHash = '';
    if (hashPart) {
      var match = hashPart.match(/^#\/[a-zA-Z0-9_-]+(?:\/[a-zA-Z0-9_-]+)*/);
      if (match) {
        safeHash = match[0];
      } else if (hashPart === '#/' || hashPart === '#') {
        safeHash = '#/';
      }
    }
    return basePath + safeHash;
  }

  var SERVER_TELEMETRY_ALLOWLIST = [
    'coach_open', 'coach_message_sent', 'coach_ref_click',
    'program_select', 'program_day_complete',
    'workout_start', 'workout_complete',
    'profile_completed', 'reminder_toggle', 'seo_landing_cta'
  ];

  function sendServerTelemetry(eventKey) {
    if (SERVER_TELEMETRY_ALLOWLIST.indexOf(eventKey) === -1) return false;
    if (typeof fetch !== 'function') return false;
    try {
      fetch('/api/telemetry/event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event: eventKey }),
        keepalive: true
      }).catch(function () {});
      return true;
    } catch (e) {
      return false;
    }
  }

  function sendEvent(eventName, params) {
    if (!isGtagReady()) return;
    try {
      var clean = sanitizeParams(params);
      window.gtag('event', eventName, clean);
    } catch (e) {
      // Fail silently without breaking application execution
    }
  }

  var RizzaAnalytics = {
    MEASUREMENT_ID: GA_MEASUREMENT_ID,

    // Expose helpers for direct verification and testing
    sanitizeString: sanitizeString,
    sanitizeParams: sanitizeParams,
    getSafeLocation: getSafeLocation,
    getSafePath: getSafePath,

    /**
     * Reset router tracking state (useful for test isolation)
     */
    resetTrackingState: function() {
      lastPagePath = null;
      lastActionTime = 0;
      lastActionKey = '';
    },

    /**
     * Track SPA virtual page views
     * Decoupled deduplication: consecutive transitions to the same screen are debounced,
     * but returning to a previously visited screen (A -> B -> A) is properly tracked.
     */
    trackPageView: function(pagePath, pageTitle) {
      var safePath = getSafePath(pagePath);
      if (safePath === lastPagePath) {
        return false;
      }
      lastPagePath = safePath;

      var safeLoc = getSafeLocation(window.location ? window.location.href : '');
      var title = sanitizeString(pageTitle || (typeof document !== 'undefined' ? document.title : '') || 'RizzaFit');

      sendEvent('page_view', {
        page_title: title,
        page_location: safeLoc,
        page_path: safePath
      });
      return true;
    },

    /**
     * Track user sign up (only after confirmed by backend)
     */
    trackSignUp: function(method) {
      sendEvent('sign_up', {
        method: sanitizeString(String(method || 'credentials'))
      });
    },

    /**
     * Track user login (only after confirmed by backend)
     */
    trackLogin: function(method) {
      sendEvent('login', {
        method: sanitizeString(String(method || 'credentials'))
      });
    },

    /**
     * Track workout start
     */
    trackWorkoutStart: function(workoutId, workoutName) {
      sendEvent('workout_start', {
        workout_id: sanitizeString(String(workoutId || '')),
        workout_name: sanitizeString(String(workoutName || ''))
      });
      sendServerTelemetry('workout_start');
    },

    /**
     * Track workout completion
     */
    trackWorkoutComplete: function(workoutId, durationSec) {
      sendEvent('workout_complete', {
        workout_id: sanitizeString(String(workoutId || '')),
        duration_seconds: Math.round(Number(durationSec) || 0)
      });
      sendServerTelemetry('workout_complete');
    },

    trackCoachOpen: function() {
      sendEvent('coach_open', {});
      return sendServerTelemetry('coach_open');
    },

    trackCoachMessage: function() {
      sendEvent('coach_message_sent', {});
      return sendServerTelemetry('coach_message_sent');
    },

    trackCoachRefClick: function(refType) {
      sendEvent('coach_ref_click', { ref_type: sanitizeString(String(refType || 'item')) });
      return sendServerTelemetry('coach_ref_click');
    },

    trackProgramSelect: function(programId) {
      sendEvent('program_select', { program_id: sanitizeString(String(programId || '')) });
      return sendServerTelemetry('program_select');
    },

    trackProgramDayComplete: function(programId) {
      sendEvent('program_day_complete', { program_id: sanitizeString(String(programId || '')) });
      return sendServerTelemetry('program_day_complete');
    },

    trackProfileCompleted: function() {
      sendEvent('profile_completed', {});
      return sendServerTelemetry('profile_completed');
    },

    trackReminderToggle: function(enabled) {
      sendEvent('reminder_toggle', { enabled: Boolean(enabled) });
      return sendServerTelemetry('reminder_toggle');
    },

    /**
     * Track major CTA clicks
     * Does not block legitimate repeated user actions, only rapid double-click bounce (<200ms)
     */
    trackCta: function(ctaName, ctaCategory) {
      var now = Date.now();
      var key = ctaName + ':' + (ctaCategory || '');
      if (lastActionKey === key && (now - lastActionTime < 200)) {
        return false;
      }
      lastActionTime = now;
      lastActionKey = key;

      sendEvent('cta_click', {
        cta_name: sanitizeString(String(ctaName || '')),
        cta_category: sanitizeString(String(ctaCategory || 'general'))
      });
      return true;
    }
  };

  window.RizzaAnalytics = RizzaAnalytics;
})(typeof window !== 'undefined' ? window : this);
