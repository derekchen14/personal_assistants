<script>
  import { sendMessage, chatActive, hasSuggestion, flowDax, replyPillData, userActions, resetTrigger } from '@store';
  import { onMount } from 'svelte';
  import { displayLayout, oauthSuccess, activeConnector, showResetModal } from '@store';
  import PaperAirplane from '@assets/icons/PaperAirplane.svelte';

  let dropdownOpen = false;

  const uploadFile = () => {
    dropdownOpen = false;
    $activeConnector = 'upload';
    $displayLayout = 'split';
  };

  const addConnector = (data_source) => {
    dropdownOpen = false;
    localStorage.setItem('vendor', data_source);
    window.location.href = `${serverUrl}/oauth/integration?data_source=${data_source}`;
  };

  const triggerReset = () => {
    dropdownOpen = false;
    showResetModal.set(true);
  };

  onMount(() => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('oauth_success') === 'true') {
      $oauthSuccess = true;
      $displayLayout = 'bottom';
    }
  });

  let message;
  let inputBox;
  let lastSentTime = 0;

  function localSendMessage(event) {
    // unpack Suggested Reply from pill data if available
    if ($hasSuggestion && ['1', '2', '3', '4'].includes(message)) {
      let replyIndex = parseInt(message) - 1;
      let chosenReply = $replyPillData[replyIndex];

      if (chosenReply['action']) {
        let action = { type: 'REPLY', payload: chosenReply['action'] };
        userActions.set(action);
      }
      flowDax.set(chosenReply['dax']);
      message = chosenReply['text'];
    }

    // handle regular message
    if (message && message.length > 1) {
      if (Date.now() - lastSentTime > 4321) {
        sendMessage(message); // prevent messages for 4 seconds
        message = ''; // Just reset the message variable, don't reset the form
        lastSentTime = Date.now();
        setTimeout(() => { // Delay to account for DOM render issues
          adjustHeight();
          toggleSendButton();
        }, 0);
      }
    }
    // Remove the event.target.reset() call
  }

  // focus on input box after chat is active, with tiny delay to account for DOM render issues
  $: if ($chatActive && inputBox) {
    setTimeout(() => inputBox.focus(), 1);
  }

  // Makes text box taller as more text is in it
  function adjustHeight() {
    const element = document.getElementById('chat-input');
    if (element) {
      element.style.height = 'auto'; // Reset height
      element.style.height = `${element.scrollHeight}px`; // Set to scroll height
    }
  }

  // Toggle send button based on if there's text in textarea
  function toggleSendButton() {
    const sendButton = document.getElementById('send-button');
    const chatInput = document.getElementById('chat-input');
    if (chatInput.value.trim()) {
      sendButton.style.transition = 'height 0.3s ease, width 0.3s ease';
      sendButton.style.height = '40px';
      sendButton.style.width = '40px';
    } else {
      sendButton.style.transition = 'height 0s ease, width 0s ease';
      sendButton.style.height = '0';
      sendButton.style.width = '0';
    }
  }

  // Make return key functional in text area
  function handleEnterKey(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      document.querySelector('form').requestSubmit();
    }
  }

  // Reset message when resetTrigger changes
  $: if ($resetTrigger) {
    if (!$chatActive) { // Only reset if chat is active
      message = '';
      if (inputBox) {
        adjustHeight();
        toggleSendButton();
      }
    }
  }
</script>

<div class="flex flex-row rounded-b-md items-center justify-stretch w-full bg-slate-50
  border-t border-solid border-gray-300 p-4 w-full">
  <!-- Removing icons for now as they are nonfunctional -->
  <!-- <div class="hidden lg:flex justify-between text-gray-500 mr-1">
    <Paperclip />
    <Smiley />
  </div> -->

  <form on:submit|preventDefault={localSendMessage} class="flex w-full p-1 rounded-lg items-start h-full 
    border border-slate-400 {$chatActive ? 'bg-white' : 'bg-slate-100'}">
    <!-- Input Box -->
    <textarea name="message" id="chat-input"
      class="h-10 w-full px-1.5 text-zinc-700 shadow-inner border-0 shadow-none text-base placeholder-slate-300
        focus:outline-none focus:ring-0 focus:ring-transparent focus:border-0 resize-none
        {$chatActive ? 'bg-white' : 'bg-slate-100 cursor-not-allowed'}"
      placeholder={$chatActive ? 'Talk to Dana ...' : ''}
      disabled={!$chatActive} bind:value={message} bind:this={inputBox} 
      rows="1" on:input={adjustHeight} on:paste={adjustHeight} on:input={toggleSendButton} on:keydown={handleEnterKey}></textarea>
  
    <div class="flex justify-center items-center">
      <!-- Send Button with Paper Airplane -->
      <button type="submit" value="chat" id="send-button"
        class="h-0 w-0 transition-all duration-300 flex rounded-md justify-center items-center cursor-pointer
        {$chatActive ? 'cursor-pointer bg-teal-500' : 'hidden'}">
        <PaperAirplane class="w-2/3 aspect-square hover:w-3/4 transition-all duration-200 ease-in-out" />
      </button>

    </div>
  </form>

</div>