import { writable } from 'svelte/store';

const ALERT_DISPLAY_DURATION_MS = 9876; // around 10 seconds

export const alertStore = writable({
  show: false,
  color: '', // to be updated based on the alertType
  prefix: '', // to be updated based on the alertType
  info: '',
});

export function clearAlert() {
  alertStore.update((state) => ({ ...state, show: false }));
}

export function displayAlert(alertType, info, isPersistent = false) {
  let color;
  let prefix;
  let message;
  switch (alertType) {
    case 'success':
      color = 'green';
      prefix = 'Success:';
      message = info ? `${info}` : 'Your request has been successfully processed.';
      break;
    case 'warning':
      color = 'yellow';
      prefix = 'Warning:';
      message = `${info}`;
      break;
    case 'error':
      color = 'red';
      prefix = 'Error:';
      message = info ? `${info}` : 'We encountered an error, please try again later.';
      break;
    default:
      color = 'blue';
      prefix = 'Note:';
      message = info ? `${info}` : 'Please share your thoughts to feedback@soleda.ai';
  }
  alertStore.set({ show: true, color: color, prefix: prefix, message: message });

  if (!isPersistent) {
    setTimeout(() => {
      alertStore.update((state) => ({ ...state, show: false }));
    }, ALERT_DISPLAY_DURATION_MS);
  }
}
