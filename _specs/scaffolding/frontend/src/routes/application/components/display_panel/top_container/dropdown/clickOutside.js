/**
 * Detects clicks outside the element it's applied to and sets the provided writable to false.
 * @param {HTMLElement} node - The element to detect outside clicks for.
 * @param {Writable} displaySetting - The writable that stores the display setting for the dropdown menu
 */
export function clickOutside(node, displaySetting) {
  const handleClick = event => {
    // Check if the click is outside the node
    if (!node.contains(event.target)) {
      displaySetting.set(false);
    }
  };

  // Attach the event listener to the document
  document.addEventListener('click', handleClick);

  return {
    destroy() {
      // Cleanup the event listener when the node is destroyed
      document.removeEventListener('click', handleClick);
    }
  };
}