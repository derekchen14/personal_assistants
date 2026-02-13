import { v4 as uuidv4 } from 'uuid';

// Log levels
export const logLevels = {
  DEBUG: 'DEBUG',
  INFO: 'INFO',
  WARNING: 'WARNING',
  ERROR: 'ERROR',
  FATAL: 'FATAL'
};

/**
 * Send a log entry to the backend for forwarding to Loki
 * @param {string} level - Log level (DEBUG, INFO, WARNING, ERROR, FATAL)
 * @param {string} eventName - Name of the event being logged
 * @param {string} component - UI component where the log originated
 * @param {object} options - Additional logging options
 */
export async function sendLog(level, eventName, component, options = {}) {
  try {
    const requestID = options.requestID || `req-${uuidv4().substring(0, 8)}`;
    const sessionID = options.sessionID || localStorage.getItem('sessionID') || `guest session`;
    const userID = options.userID || localStorage.getItem('userID') || null;
    const conversationID = options.conversationID || localStorage.getItem('conversationID') || null;
    
    // Construct the log data object with your structure
    const logData = {
      requestID,
      userID,
      sessionID,
      conversationID,
      timestamp: new Date().toISOString(),
      level,
      source: 'dana-frontend',
      event_name: eventName,
      component,
      details: options.details || {},
      error: level === 'ERROR' || level === 'FATAL' ? {
        error_type: options.error?.error_type || 'unknown',
        error_code: options.error?.error_code || 'UNKNOWN_ERROR',
        error_message: options.error?.error_message || options.message || '',
        stack_trace: options.error?.stack_trace || '',
        browser: {
          name: navigator.userAgent.includes('Chrome') ? 'Chrome' : 
                navigator.userAgent.includes('Firefox') ? 'Firefox' : 
                navigator.userAgent.includes('Safari') && !navigator.userAgent.includes('Chrome') ? 'Safari' : 
                navigator.userAgent.includes('Edge') ? 'Edge' : 'Other',
          version: (() => {
            const match = navigator.userAgent.match(/(Chrome|Firefox|Safari|Edge)\/(\d+\.\d+)/);
            return match ? match[2] : 'unknown';
          })()
        }
      } : null
    };

    // Send to backend
    const response = await fetch('/api/v1/telemetry', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(logData),
    });

    if (!response.ok) {
      // For logging failures, log to console as fallback
      console.error('Failed to send log:', await response.text());
    }
    return true;
  } catch (error) {
    console.error('Error sending log:', error);
    return false;
  }
}

// Convenience methods
export const logger = {
  debug: (eventName, component, options = {}) => 
    sendLog(logLevels.DEBUG, eventName, component, options),

  info: (eventName, component, options = {}) => 
    sendLog(logLevels.INFO, eventName, component, options),
  
  warning: (eventName, component, options = {}) => 
    sendLog(logLevels.WARNING, eventName, component, options),
  
  error: (eventName, component, options = {}) => 
    sendLog(logLevels.ERROR, eventName, component, options),
  
  fatal: (eventName, component, options = {}) => 
    sendLog(logLevels.FATAL, eventName, component, options),
  
  setUserID: (userID) => {
    localStorage.setItem('userID', userID);
  },
  resetUserID: () => {
    localStorage.removeItem('userID');
  },

  setSessionID: (sessionID) => {
    localStorage.setItem('sessionID', sessionID);
  },
  resetSessionID: () => {
    localStorage.removeItem('sessionID');
  },

  setConversationID: (conversationID) => {
    localStorage.setItem('conversationID', conversationID);
  },
  resetConversationID: () => {
    localStorage.removeItem('conversationID');
  }
};
