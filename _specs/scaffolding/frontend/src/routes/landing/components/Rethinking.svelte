<script>
  import ArrowRight from '../../application/lib/icons/ArrowRight.svelte';
  import { onMount } from 'svelte';
  import { fly } from 'svelte/transition';
  import { flip } from 'svelte/animate';
  import { Book_Call_URL } from '$lib/constants';

  // Chat conversation data
  const conversation = [
    { speaker: 'User', text: 'Which brands are connected to really high AOV?' },
    { speaker: 'Dana', text: 'I can calculate AOV by averaging the completed purchase amounts for each shopper ID, does that sound right? Also, I noticed that some of the brand names have similar terms, should we take a look?' },
    { speaker: 'User', text: 'So they are misspelled?' },
    { speaker: 'Dana', text: 'Yes, for example I noticed there is Versache and Versace, as well as Dolce and Gabbanna vs. Dolce & Gabbana vs. Dolce & Gabanna. See table for more.' },
    { speaker: 'User', text: 'Oh right! Let\'s merge those into the correct ones.' },
    { speaker: 'Dana', text: 'No problem, I\'ve updated the data for consistency. Looking at the consolidated results, the brands associated with the highest AOV are Jimmy Choo, Stuart Weitzman, and UGG. In general, it seems that luxury brands lead to higher order values, with the exception of UGG.' },
    { speaker: 'User', text: 'Interesting. Can I get a breakdown of all orders containing UGGs?' },
    { speaker: 'Dana', text: 'Absolutely. After looking at the order composition, I noticed that orders with UGG includes shoes for men and women, in addition to clothing purchases to complete the outfit. In contrast the orders within luxury shoes only have one item.' },
    { speaker: 'User', text: 'Wow, that\'s a great insight!' }
  ];

  let visibleMessages = 0;
  let messageTimer;
  let resetTimer;
  let showTypingIndicator = false;
  let typingPerson = null;
  let typingTimer;

  function startAnimation() {
    visibleMessages = 0;
    clearTimeout(messageTimer);
    clearTimeout(resetTimer);
    clearTimeout(typingTimer);
    showTypingIndicator = false;
    showNextMessage();
  }

  function showNextMessage() {
    if (visibleMessages < conversation.length) {
      // Show typing indicator before showing the next message
      const nextMessage = conversation[visibleMessages];
      typingPerson = nextMessage.speaker;
      showTypingIndicator = true;
      
      // Calculate typing indicator duration based on next message length and speaker
      const typingDuration = nextMessage.speaker === 'Dana' 
        ? nextMessage.text.length * 10 // 10ms per character for Dana (reduced from 40ms)
        : nextMessage.text.length * 40; // Keep 40ms for User
      
      // Show the actual message after the typing duration
      typingTimer = setTimeout(() => {
        showTypingIndicator = false;
        visibleMessages++;
        
        // Calculate delay before showing typing for next message
        // based on current message length
        const currentMessage = conversation[visibleMessages - 1].text;
        const readingDelay = currentMessage.length * 30; // 30ms per character for reading
        const totalDelay = 500 + readingDelay; // Base 0.5 second plus reading delay (reduced from 1000ms)
        
        messageTimer = setTimeout(showNextMessage, totalDelay);
      }, typingDuration);
    } else {
      // After all messages are shown, reset after 5 seconds
      resetTimer = setTimeout(() => {
        startAnimation();
      }, 5000);
    }
  }

  onMount(() => {
    startAnimation();
    return () => {
      clearTimeout(messageTimer);
      clearTimeout(resetTimer);
      clearTimeout(typingTimer);
    };
  });
</script>

<!-- Rethinking Section -->
<section class="relative py-32 bg-ivory bg-[url('/images/landing/rethinking-background.webp')] bg-center bg-no-repeat" style="background-size: 100% 100%;">
  <div class="px-8 md:px-16">
    <div class="max-w-[1280px] mx-auto">
      <div class="flex flex-col md:flex-row gap-12 items-center">
        <!-- Left Column -->
        <div class="w-full md:w-1/2 space-y-8 order-1">
          <img 
            src="/images/landing/rethinking-logo.svg"
            alt=""
            class="w-12 h-12"
            aria-hidden="true"
          />
          
          <h2 class="text-4xl lg:text-6xl font-[600] text-ink font-rem space-y-2">
            <span class="block leading-[1.2]">Smarter with</span>
            <span class="block leading-[1.2]">every question.</span>
          </h2>
          
          <p class="text-md text-ink md:text-md">
            At <strong>Soleda</strong>, we're crafting agents with specialized knowledge and tools. They bring domain expertise and ask relevant questions. They are <em>dependable</em>. Just like your favorite colleague.
          </p>
          
          <!-- CTA Button (visible only above 768px) -->
          <div class="pt-4 hidden md:block">
            <a href={Book_Call_URL} target="_blank" rel="noopener noreferrer" class="inline-block">
              <button class="bg-custom_green hover:bg-custom_green_hover text-ivory_light font-medium w-[300px] h-[64px] text-[24px] rounded-full transition duration-300 relative flex items-center group">
                <div class="flex-grow text-center pr-8">Get started</div>
                <div class="absolute right-8 flex items-center transition-transform duration-300 group-hover:translate-x-1">
                  <ArrowRight />
                </div>
              </button>
            </a>
          </div>
        </div>
        
        <!-- Right Column - Chat Interface -->
        <div class="w-full max-w-[512px] md:w-1/2 order-2 self-start md:self-auto">
          <div class="bg-white border-solid border-0 border-[#F6F3E9] rounded-lg w-full h-96 px-6 py-0 overflow-hidden relative">
            <!-- Chat container with flex column that positions content from bottom to top -->
            <div class="h-full flex flex-col justify-end overflow-hidden">
              <!-- Messages area -->
              <div class="flex flex-col space-y-4 w-full">
                {#each conversation.slice(0, visibleMessages) as message, i (i)}
                  <div class="flex {message.speaker === 'Dana' ? 'justify-start' : 'justify-end'}"
                    animate:flip={{ duration: 400 }}>
                    <div class="max-w-[80%] rounded-2xl px-4 py-3 text-ivory_light
                      {message.speaker === 'Dana' ? 'bg-custom_green' : 'bg-[#006BB9]'}"
                      in:fly={{ y: 30, duration: 300 }}>
                      {message.text}
                    </div>
                  </div>
                {/each}
              </div>
              
              <!-- Fixed height area for typing indicators -->
              <div class="w-full min-h-[40px] mt-2">
                {#if showTypingIndicator}
                  <div 
                    class="flex {typingPerson === 'Dana' ? 'justify-start' : 'justify-end'}"
                    in:fly={{ y: 10, duration: 200 }}
                  >
                    {#if typingPerson === 'User'}
                      <div class="flex items-center h-5 px-4 typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                    {:else}
                      <div class="px-4 thinking-text">Dana is thinking...</div>
                    {/if}
                  </div>
                {/if}
              </div>
            </div>
          </div>
        </div>
        
        <!-- CTA Button (visible only below 768px) -->
        <div class="w-full order-3 md:hidden mt-4">
          <a href={Book_Call_URL} target="_blank" rel="noopener noreferrer" class="inline-block">
            <button class="bg-cyan-900 hover:bg-gray-800 text-ivory_light font-medium w-[300px] h-[64px] text-2xl rounded-full transition duration-300 shadow-lg relative flex items-center group">
              <div class="flex-grow text-center pr-8">Get started</div>
              <div class="absolute right-8 flex items-center transition-transform duration-300 group-hover:translate-x-1">
                <ArrowRight />
              </div>
            </button>
          </a>
        </div>
      </div>
    </div>
  </div>
</section>

<style>
  /* Typing indicator animation for User */
  .typing-indicator span {
    height: 8px;
    width: 8px;
    margin: 0 2px;
    background-color: #777777;
    border-radius: 50%;
    display: inline-block;
    animation: bounce 1.5s infinite ease-in-out;
  }
  
  .typing-indicator span:nth-child(1) {
    animation-delay: -0.3s;
  }
  
  .typing-indicator span:nth-child(2) {
    animation-delay: -0.15s;
  }
  
  @keyframes bounce {
    0%, 80%, 100% { 
      transform: scale(0);
    }
    40% { 
      transform: scale(1);
    }
  }
  
  /* Thinking animation for Dana */
  .thinking-text {
    color: #777777; /* Fallback color */
    background: linear-gradient(90deg, #555555, #999999, #555555);
    background-size: 200% auto;
    background-clip: text;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: gradient 2s linear infinite;
  }
  
  @keyframes gradient {
    0% {
      background-position: 0% center;
    }
    100% {
      background-position: 200% center;
    }
  }
</style>
