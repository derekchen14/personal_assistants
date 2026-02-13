<script>
  import Avatar from '../../shared/avatar.svelte';
  import CodeIcon from '@assets/icons/Code.svelte';
  import ThumbsUp from '@assets/icons/ThumbsUp.svelte';
  import ThumbsUpFilled from '@assets/icons/ThumbsUpFilled.svelte';
  import Logo from '@assets/branding/logo-black.svelte';
  import Pencil from '@assets/icons/Pencil.svelte';
  import SuggestedReplies from './suggestedReplies.svelte';

  import { formatDistance, differenceInSeconds } from 'date-fns';
  import { onMount, tick } from 'svelte';
  import { chatActive, sendMessage, messageStore, userActions, agentStatus, serverUrl, resetTrigger, utteranceHistory } from '@store';
  import { securedFetch } from '$lib/apiUtils';
  import { logger } from '$lib/logger'; 
  import { slide } from 'svelte/transition';

  let messages = [];
  let isSpinning = false;
  let hasInitialized = false;
  let now = new Date();
  let hoveredMessageId = null;
  const phrases = [
    "Dana is typing…",
    "Dana is analyzing…",
    "Dana is thinking…",
    "Dana is processing data…",
    "Dana is calculating…"
  ];
  let spinningPhrase = "";

  let messageRefs = [];
  let editingMessageId = null;
  let editedContent = '';
  let textareaActive;

  let lastConversation = null;
  $: {
    if ($chatActive) {
      let firstMessage = {
          message: { type: 'text', content: 'Hello, how can I help you today?' },
          userId: 'agent', time: new Date(),
        };
      // Only update messages if the utteranceHistory changes to a new conversation
      if ($utteranceHistory && $utteranceHistory !== lastConversation && $utteranceHistory.length > 0) {
        messages = [ ...$utteranceHistory.map(utt => ({
          message: { type: utt.type, content: utt.content },
          userId: utt.role === 'agent' ? 'agent' : 'customer',
          time: utt.timestamp ? new Date(utt.timestamp) : new Date(),
        })).reverse(), firstMessage];
        lastConversation = $utteranceHistory;
        hasInitialized = true;
      } else if ($chatActive && !hasInitialized) {
        messages = [firstMessage];
        hasInitialized = true;
      }
    } else {
      messages = [];
      hasInitialized = false;
    }
  }

  $: if ($messageStore) {
    appendMessages($messageStore);
  }

  function appendMessages(currentMessage){
    if ($chatActive) {
      if (currentMessage.message.content === 'spin') {
        isSpinning = true;
      } else {
        isSpinning = false;
        messages = [currentMessage, ...messages];
        now = new Date(); // Trigger a re-render of the time passed
      }
    }
  }

  // pick random phrase to display representing Dana's thinking
  $: if (isSpinning && $agentStatus) {
    const randomIndex = Math.floor(Math.random() * phrases.length);
    spinningPhrase = phrases[randomIndex];
  }

  async function startRevision(index) {
    editingMessageId = index;
    editedContent = messages[index].message.content;
    await tick();
    if (textareaActive) {
      textareaActive.focus();
    }
  }

  function cancelRevision() {
    editingMessageId = null;
    editedContent = '';
    textareaActive.blur();
  }

  function sendRevision() {
    if (editingMessageId !== null && editedContent && editedContent.length > 1) {
      // remove the revised message and all messages afterwards
      messages = messages.slice(editingMessageId + 1);
      // prepare the turn index as a user action to be sent to the server
      const revision = { type: 'REVISE', payload: editingMessageId };
      userActions.set(revision);
      sendMessage(editedContent);

      // clear all revision-related state
      editingMessageId = null;
      editedContent = '';
      userActions.set(null);
    }
  }

  function receiveData(data, userTimestamp) {
    messages[editingMessageId].message.content = data.userUtterance;
    messages[editingMessageId].time = userTimestamp;

    // Update the message store appropriately
    messageStore.set({
      message: { type: 'text', content: data.agentUtterance },
      userId: 'agent', time: new Date()
    });

    // remove all messages that occurred after the edited message, remember that messages are stored in reverse order
    messages = messages.slice(editingMessageId);
    editingMessageId = null;
    editedContent = '';
  }

  function hasHTML(str) {
    // Only allowed HTML for now is bold, italic, code, unordered list and list item
    for (const tag of ['strong', 'em', 'code', 'ul', 'li']) {
      if (str.includes(`/${tag}>`)) return true;
    }
    return false;
  }

  function formatTime(now, msgTime) {
    const secondsDiff = differenceInSeconds(now, msgTime);
    if (secondsDiff <= 60) {
      return "Just now";
    // } else if (secondsDiff < 30) { // Removing this because this level of granularity is not needed
    //   return "a few seconds ago" // Plus, this string is long
    } else {
      return formatDistance(msgTime, now, { addSuffix: true });
    }
  }

  // Makes text box taller as more text is in it
  function adjustHeight(element) {
    if (element) {
      element.style.height = 'auto'; // Reset height
      element.style.height = `${element.scrollHeight}px`; // Set to scroll height
    }
  }

  $: editedContent, adjustHeight(textareaActive);

  // Reset spinning state when resetTrigger changes
  $: if ($resetTrigger) {
    isSpinning = false;
  }

</script>

<div class="flex flex-col-reverse grow basis-0 overflow-y-scroll flex-nowrap p-3 pr-0 relative
  {$chatActive ? 'mr-3' : 'bg-slate-100'}"
  style="scrollbar-width: thin; scrollbar-color: rgba(0, 0, 0, 0.5) transparent;">

  <Logo class="w-full opacity-5 md:scale-125 absolute top-1/2 left-0 transform -translate-x-1/3 -translate-y-1/4
    {$chatActive ? 'hidden' : ''}"/>

  <SuggestedReplies />

  {#if isSpinning && $agentStatus}
    <div class="agentThinking self-start flex flex-row gap-1 pl-2 mt-3 text-slate-400 first:animate-fadeUp">
      <p>{spinningPhrase}</p>
    </div>
  {/if}

  {#each messages as item, index (index + '-' + item.time)}
    {@const isVisible = false}
    {#if item.userId === 'agent'}

      <div class="agentChat relative self-start flex flex-row gap-2 my-2 group first:animate-fadeUp max-w-full">
        <!-- <Avatar showStatus={false} userId={item.userId} /> -->

        <div class="relative self-start flex-1 flex flex-col max-w-full">
          <!-- Code snippet, if available -->
          {#if item.message.code?.snippet && item.showCode}
          <div transition:slide class="left-0 p-4 bg-gray-900 mx-2 rounded-t-lg overflow-hidden">
            <div class="code-snippet font-code text-sm">
              <div class="italic text-xs font-bold text-emerald-400 break-all pb-2">{item.message.code.source}:</div>
              <div class="whitespace-pre overflow-x-auto text-emerald-300">{item.message.code.snippet}</div>
            </div>
          </div>
          {/if}

          <!-- Agent Message Content -->
          <div bind:this={messageRefs[index]} class="text-slate-50 px-3 py-2 rounded-lg bg-cyan-500">
            <div class="absolute left-3 -bottom-1 w-2 h-3 bg-cyan-500"
              style="transform: translateX(-50%) rotate(45deg) skewY(32deg);"></div>
            {#if hasHTML(item.message.content)}
                {@html item.message.content}
            {:else}
                {item.message.content}
            {/if}
          </div>

          <!-- Interact with Agent message -->
          <div class="options absolute -bottom-4 right-2 rounded min-h-6 min-w-12 flex flex-row p-1 gap-0 items-center 
              whitespace-nowrap opacity-0 group-hover:opacity-100 scale-75 group-hover:scale-100 duration-100 bg-cyan-400">
            <span class="text-slate-100 pl-1 text-xs font-bold">
              {formatTime(now, item.time)} •
            </span>
            <button class="codeIcon h-5 px-1 rounded hover:bg-yellow-400 hover:opacity-100 flex justify-center items-center"
              class:hidden={!item.message.code?.snippet} on:click={() => item.showCode = !item.showCode}>
              <CodeIcon fill='white' class="w-4" />&nbsp;
              <span class="text-white text-xs text-nowrap">See Code</span>
            </button>
            <button
              class="upvote w-5 h-5 rounded hover:bg-yellow-400 hover:opacity-100 flex justify-center items-center"
              on:click={ () => { item.upvote = !item.upvote; item.downvote = false; } }>
              {#if item.upvote}
                <ThumbsUpFilled fill='white' class="w-4" />
              {:else}
                <ThumbsUp fill='white' class="w-4" />
              {/if}
            </button>
            <button
              class="downvote w-5 h-5 rounded hover:bg-yellow-400 hover:opacity-100 flex justify-center items-center"
              on:click={() => { item.downvote = !item.downvote; item.upvote = false; }}>
              {#if item.downvote}
                <ThumbsUpFilled fill='white' class="w-4 rotate-180" />
              {:else}
                <ThumbsUp fill='white' class="w-4 rotate-180" />
              {/if}
            </button>
          </div>

        </div>

      </div>

    {:else if item.userId === 'customer'}

      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="customerChat relative self-end flex flex-row gap-1 mt-3 mb-2 ml-10 group first:animate-fadeUp"
        on:mouseenter={() => hoveredMessageId = index}
        on:mouseleave={() => hoveredMessageId = null}>

        <!-- User Message Content -->
        <div bind:this={messageRefs[index]} class="self-start flex-1 text-slate-50 px-3 py-2 rounded-lg bg-blue-600">
          <div class="absolute right-3 -bottom-1 w-2 h-3 bg-blue-600"
                style="transform: translateY(-10%) rotate(45deg) skewX(32deg);"></div>
          
          {#if editingMessageId === index}
            <textarea class="bg-blue-100 text-zinc-700 focus:outline-none resize-none w-full shadow-inner rounded"
              bind:value={editedContent} bind:this={textareaActive}></textarea>
            <div class="my-2 flex justify-center space-x-2">
              <button class="h-8 px-4 border border-zinc-700 text-sm text-zinc-700 bg-zinc-200 rounded-md cursor-pointer"
              on:click={cancelRevision}>Cancel</button>
              <button class="h-8 px-4 border border-green-700 text-sm text-slate-50 bg-green-500 rounded-md cursor-pointer"
              on:click={sendRevision}>Save</button>
            </div>
          {:else}
            {item.message.content}
          {/if}
        </div>

        <!-- Interact with User message -->
        <div class="options absolute -bottom-4 left-2 rounded min-h-6 min-w-12 flex flex-row p-1 gap-0 items-center 
            whitespace-nowrap opacity-0 group-hover:opacity-100 scale-75 group-hover:scale-100 duration-100 bg-blue-500">
          <span class="text-slate-100 pl-1 text-xs font-bold">
            {formatTime(now, item.time)} •
          </span>

          <button
            class="codeIcon h-5 px-1 rounded hover:bg-yellow-400 hover:opacity-100 flex justify-center items-center"
            on:click={() => startRevision(index)}>
            <Pencil fill='#ffffff' class="w-4" />
            &nbsp;
            <span class="text-white text-xs text-nowrap">Edit</span>
          </button>

        </div>
      </div>

    {/if}

  {/each}

</div>