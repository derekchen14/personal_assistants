import { displayAlert } from '@alert';
import { sheetData } from '@store';
import { writable, get } from 'svelte/store';
import { manageDecisionData, manageDerivedData, manageDirectData, manageDynamicData, selectedSpreadsheet, resetChat} from './dataStore';
import { saveEdits, selectedTable, currentFlow, currentStage } from './dataStore';
import { browser } from '$app/environment';
import { logger } from '$lib/logger'; 
import { v4 as uuidv4 } from 'uuid';

export * from './dataStore';

/** @type {WebSocket|null} */
let socket = null;
let waitTimer;

// Constants
const TIMEOUT_DURATION = 3000;
const LONG_MESSAGE_DELAY_MS = 5678; // Wait for around 5 seconds before sending the message
const isServer = typeof window === 'undefined';
const host = import.meta.env.VITE_SERVER_HOST
export const serverUrl = `${isServer ? 'http://' + host : window.location.origin}/api/v1`;
export const socketUrl = serverUrl.replace(/^http/, 'ws');

// User Input
export const lastAction = writable(null);
export const messageStore = writable(null); // Message from Dana
export const searchQuery = writable('');
export const userActions = writable(null);

// Interactive View
export const interactionView = writable(null);
export const resetInteractions = writable(true);
export const pickedColumns = writable({});
export const carouselIndex = writable(0);
export const activatedItem = writable('');
export const panelVariables = writable({});  // values are arrays of clauses or constraints

// Suggested Reply Pills
export const hasSuggestion = writable(false);
export const replyPillData = writable([]);
export const flowDax = writable('');

// System Settings
export const displayLayout = writable('split');  // top, split, bottom
export const oauthSuccess = writable(false);
export const agentStatus = writable(false); // agent is on when websockets is connected
export const disconnectionMessage = writable("Your connection has been lost. Please upload files to start a new session."); // Whether the chat is active for interaction
export const connectionStatus = writable('not_initialized'); // 'connected', 'disconnected', 'not_initialized'
export const shouldConnect = writable(false);

// Conversation Management
export const conversationId = writable(null);

// Determines which integration/connector to show
export const activeConnector = writable('upload'); // 'upload', 'drive', 'ga4', 'hubspot', etc.

export const utteranceHistory = writable([]); // Store for conversation utterances

if (browser) {
  // Avoid using window.store directly as it causes linter errors
  const storeObject = { messageStore, activeConnector, interactionView, displayLayout, searchQuery,
                    replyPillData, userActions, oauthSuccess, agentStatus, lastAction, selectedTable,
                    conversationId };
  // @ts-ignore - Assign to window for debugging purposes
  window.store = storeObject;
  
  // Check if we're on a page that should trigger a WebSocket connection
  const shouldInitializeSocket = () => {
    const path = window.location.pathname;
    // Only connect on application page after authentication, not on login, register, etc.
    // Also make sure we only connect when actually viewing data
    return (path.includes('/application') ||  path.includes('/dashboard'))
  };

  // Only initialize the socket if we're on a page that needs it
  if (shouldInitializeSocket()) {
    shouldConnect.set(true);
    if (socket) {
      socket.close();   // Clear any existing socket
    }
    initializeSocket();
  } else {
    shouldConnect.set(false);
  }
}

export const receiveData = (data) => {
  // data is already parsed as JSON
  if (data.message != null) {
    messageStore.set({
      message: { type: 'text', content: data.message, code: data.code_snippet },
      userId: 'agent', time: new Date()
    });
  }
  if (data.connection_status != null) {
    connectionStatus.set(data.connection_status);
    if (data.connection_status === 'disconnected') {
      handleConnectionLoss(data.message);
    } else if (data.connection_status === 'connected') {
      agentStatus.set(true);
    }
  }
  if (data.actions != null) {
    lastAction.set(data.actions); // list of actions
    if (data.actions[0] == 'ERROR') {
      agentStatus.set(false);
    }
  }
  if (data.frame != null) {
    try {
      if (data.tabType === 'direct') {
        manageDirectData(data.frame);
      } else if (data.tabType === 'decision') {
        manageDecisionData(data.frame);
      } else if (data.tabType === 'dynamic') {
        manageDynamicData(data.frame);
      } else if (data.tabType === 'derived') {
        manageDerivedData(data.frame);
      }
      
      // Store properties for each table if available
      if (data.properties && data.frame.tabs) {
        const tables = data.frame.tabs;
        const safeProps = typeof data.properties === 'object' ? data.properties : {};

        sheetData.update(storeData => {
          const updatedData = { ...(storeData || {}) };

          tables.forEach(tableName => {
            const tableProperties = safeProps[tableName] || {};
            if (!updatedData[tableName]) {
              updatedData[tableName] = {};
            }

            updatedData[tableName] = {
              ...(updatedData[tableName] || {}),
              properties: tableProperties
            };
          });

          return updatedData;
        });
      }
      
    } catch (error_msg) {
      console.error(error_msg);
      agentStatus.set(false);
    }
  }
  if (data.suggestions != null) {
    hasSuggestion.set(true);
    replyPillData.set(data.suggestions);
  }
  if (data.interaction != null) {
    if (data.interaction['format'] === 'signal') {
      if (data.interaction['content'] === 'next') {
        carouselIndex.update(n => n + 1);
      } else if (data.interaction['content'] === 'previous') {
        carouselIndex.update(n => n - 1);
      } else if (data.interaction['content'] === 'end') {
        interactionView.set(null);
        carouselIndex.set(0);
        displayLayout.set('bottom');
      }
    } else {
      if (data.interaction['flowType'] && data.interaction['flowType'] !== 'none') {
        currentFlow.set(data.interaction['flowType']);
      }
      if (data.interaction['stage']) {
        currentStage.set(data.interaction['stage']);
      }
      if (data.interaction['show']) {
        displayLayout.set('split');
      }
      resetInteractions.set(true);
      interactionView.set(data.interaction);
    }
  }

  // Handle conversation ID
  if (data.conversation_id) {
    const currentId = get(conversationId);
    if (currentId !== data.conversation_id) {
      conversationId.set(data.conversation_id);
      // Update URL without refresh using History API
      const path = window.location.pathname;
      const newPath = path.includes('/conversation/') 
        ? path.replace(/\/conversation\/[^/]+/, `/conversation/${data.conversation_id}`)
        : `${path}/conversation/${data.conversation_id}`;
      window.history.pushState({}, '', newPath);
    }
  }
}

// Handle connection loss
function handleConnectionLoss(reason = 'Connection lost. Please upload files to start a new session.') {
  connectionStatus.set('disconnected');
  agentStatus.set(false);
  disconnectionMessage.set(reason);
  resetChat(false /* enableNotification */);
}

export async function initializeSocket() {
  if (socket && socket.readyState === WebSocket.OPEN) {
    console.log('Using existing socket connection...');
    return socket;
  } else {
    console.log('Initializing new socket connection...');
  }

  try {
    // Connect without the token query parameter - the cookie will be sent automatically
    socket = new WebSocket(`${socketUrl}/ws`);
    
    // Connection opened and closed
    socket.addEventListener('open', function (_event) {
      console.log('socket connection started');
      agentStatus.set(true);
      connectionStatus.set('connected');
      // Generate new conversation ID when socket connects
      // TODO: Get conversation ID from the backend.
      const conversationID = `${uuidv4().substring(0, 8)}`;
      logger.setConversationID(conversationID);
      console.log("frontend web socket opened")
    });
    
    socket.addEventListener('close', function (event) {
      console.log('socket connection has ended', event);
      
      // Check if closure was due to authentication issues (code 1008)
      if (event.code === 1008) {
        handleConnectionLoss('Authentication failed. Please log in again.');
      } else if (event.code === 1000) {
        agentStatus.set(false);
        connectionStatus.set('disconnected');
      } else {
        // Unexpected closure - network issues, server crash, etc.
        handleConnectionLoss('Connection lost. Please refresh the page to start a new session.');
      }
      logger.resetConversationID();
      console.log("frontend web socket closed")
    });

    // Listen for incoming messages
    socket.addEventListener('message', function (event) {
      const data = JSON.parse(event.data);   
      clearTimeout(waitTimer);
      receiveData(data);
    });

    // Handle errors
    socket.addEventListener('error', function (error) {
      console.error('WebSocket error:', error);
      handleConnectionLoss('Failed to establish connection. Please refresh the page.');
    });

    return socket;
  } catch (error) {
    console.error(error);
    handleConnectionLoss('Failed to establish connection. Please refresh the page.');
    return null;
  }
}

export const sendMessage = (message) => {
  const unsafe = guardRailMessage(message);
  if (unsafe) { return; }

  // Check if socket is connected before sending
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    handleConnectionLoss('Connection lost. Please refresh the page to start a new session.');
    return;
  }

  saveEdits(); // Save any unsaved edits before sending a new message
  messageStore.set({
    message: { type: 'text', content: message },
    userId: 'customer', time: new Date()
  });
  const obj = {
    currentMessage: message,
    dialogueAct: get(flowDax),
    lastAction: get(userActions),
    conversation_id: get(conversationId) // Include conversation ID in message
  };

  const blob = new Blob([JSON.stringify(obj, null, 2)], {
    type: 'application/json',
  });

  socket.send(blob);

  waitTimer = setTimeout(() => {
    let spinner = { message: { type: 'image', content: 'spin' }, userId: 'agent' };
    messageStore.set(spinner);
  }, TIMEOUT_DURATION);

  flowDax.set('');        // clear out the flowDax after sending the message
  userActions.set(null);  // clear out the user actions after sending the message
  hasSuggestion.set(false);
};

function guardRailMessage(message) {
  let isSafe = true
  if (message.toLowerCase().includes("ignore previous instruct")) {
    isSafe = false;
    messageStore.set({
      message: { type: 'text', content: message },
      userId: 'customer', time: new Date()
    });
    messageStore.set({
      message: { type: 'text', content: "You can't manipulate me so easily, please stop trying." },
      userId: 'agent', time: new Date()
    });

    agentStatus.set(false);
    displayAlert("error", "Malicious activity detected, system has been shutdown.");
    throw new Error("User attempted to hack the system with prompt engineering!");
  }
  if (message.length > 1024) {
    isSafe = false;
    const truncatedMessage = message.slice(0, 1000) + ' ... [truncated]'
    messageStore.set({
      message: { type: 'text', content: truncatedMessage },
      userId: 'customer', time: new Date()
    });
    // agent response to long messages
    setTimeout(() => {
      const shortenMessage = "Sorry, I zoned out for a second. That is too long, can you please shorten it?"
      messageStore.set({
        message: {type: 'text', content: shortenMessage},
        userId: 'agent', time: new Date()
      });
      displayAlert('warning', "Messages must be 1000 characters or less");
    }, LONG_MESSAGE_DELAY_MS);
  }
  return !isSafe;
}