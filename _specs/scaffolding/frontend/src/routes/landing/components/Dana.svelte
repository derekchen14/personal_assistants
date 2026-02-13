<script lang="ts">
  import ArrowRight from '../../application/lib/icons/ArrowRight.svelte';
  import { Book_Call_URL } from '$lib/constants';
  import { onMount, onDestroy } from 'svelte';
  
  // Image paths for the carousel
  const imagePaths = [
    "/images/landing/dana-screenshot1.jpg",
    "/images/landing/dana-screenshot2.jpg",
    "/images/landing/dana-screenshot3.jpg",
    "/images/landing/dana-screenshot4.jpg"
  ];
  
  // Each card has an image index and a visual position
  let cards = [
    { id: 0, imageIndex: 0, position: 0 },
    { id: 1, imageIndex: 1, position: 1 },
    { id: 2, imageIndex: 2, position: 2 },
    { id: 3, imageIndex: 3, position: 3 }
  ];
  
  let isTransitioning = false;
  let interval;
  
  onMount(() => {
    // Start the rotation timer
    interval = setInterval(rotateImage, 4000);
  });
  
  onDestroy(() => {
    // Clean up the interval when component is destroyed
    clearInterval(interval);
  });
  
  function rotateImage() {
    if (isTransitioning) return;
    
    isTransitioning = true;
    
    // Update positions - the front card (position 0) moves to "exiting" position
    // and all others move forward one position
    cards = cards.map(card => {
      if (card.position === 0) {
        return { ...card, position: 'exiting' };
      } else if (card.position === 3) {
        return { ...card, position: 2 };
      } else if (card.position === 2) {
        return { ...card, position: 1 };
      } else if (card.position === 1) {
        return { ...card, position: 0 };
      }
      return card;
    });
    
    // After exiting transition completes, place card at back with opacity 0
    setTimeout(() => {
      cards = cards.map(card => {
        if (card.position === 'exiting') {
          const oldImageIndex = card.imageIndex;
          return { 
            ...card, 
            position: 'hidden-back',
            imageIndex: (oldImageIndex + 4) % imagePaths.length
          };
        }
        return card;
      });
      
      // Short delay then start the fade in process
      setTimeout(() => {
        cards = cards.map(card => {
          if (card.position === 'hidden-back') {
            return { ...card, position: 'fading-in' };
          }
          return card;
        });
        
        // Wait for fade-in to complete before allowing next rotation
        setTimeout(() => {
          cards = cards.map(card => {
            if (card.position === 'fading-in') {
              return { ...card, position: 3 };
            }
            return card;
          });
          isTransitioning = false;
        }, 600); // Match this to the opacity transition duration
      }, 50);
    }, 1000);
  }
</script>

<style>
  .card {
    transition: all 2s cubic-bezier(0.25, 1, 0.5, 1);
    will-change: transform, opacity, filter;
    transform-origin: center center;
    backface-visibility: hidden;
  }
  
  /* Card Positions */
  .position-0 {
    z-index: 40;
    transform: translateY(0) scale(1);
    opacity: 1;
  }
  
  .position-1 {
    z-index: 30;
    transform: translateY(-20px) scale(0.97);
  }
  
  .position-2 {
    z-index: 20;
    transform: translateY(-35px) scale(0.94);
  }
  
  .position-3 {
    z-index: 10;
    transform: translateY(-45px) scale(0.92);
  }
  
  /* Exiting position (front card moving forward and fading out) */
  .position-exiting {
    z-index: 50;
    transform: translateY(30px) translateZ(40px) scale(1.03);
    opacity: 0;
    transition: all 1s;
  }
  
  /* Hidden back position - no transition to instantly jump to position */
  .position-hidden-back {
    z-index: 5;
    transform: translateY(-45px) scale(0.92);
    opacity: 0;
    transition: none;
  }
  
  /* Fading in at the back position - only animate opacity */
  .position-fading-in {
    z-index: 5;
    transform: translateY(-45px) scale(0.92);
    opacity: 0;
    transition: none; /* First frame - stay invisible */
  }

  /* Add a special rule that gets applied after the initial render */
  .position-fading-in:not(:first-child) {
    opacity: 1;
    transition: opacity 600ms ease-in;
    transition-delay: 100ms; /* Small delay before starting fade-in */
  }
</style>

<!-- Dana Introduction Section with padding-top to accommodate the overlap -->
<section class="relative pb-20 pt-10 md:pt-20 bg-[url('/images/landing/dana-background.webp')] bg-center bg-no-repeat text-ink border-t-1 border-ink"
  style="background-size: 100% 100%;">
  <div class="px-8 md:px-16">
    <div class="max-w-[1280px] mx-auto">
      <div class="flex flex-col [@media(min-width:1024px)]:flex-row gap-12 items-center">
        <!-- Left Column with mobile title/robot layout -->
        <div class="w-full [@media(min-width:1024px)]:w-1/2 space-y-8 [@media(min-width:1024px)]:pr-8">
          <div class="flex items-center gap-4">
            <h2 class="text-4xl md:text-5xl font-[600] font-rem space-y-2">
              <span class="block leading-[1.2]">100% Accuracy</span>
              <span class="block leading-[1.2]">without Hallucination.</span>
            </h2>
          </div>
          
          <!-- Rest of content -->
          <p class="text-lg text-gray-800 md:text-xl">
            <strong>Meet Dana, a purpose-built AI agent for RevOps teams.</strong> Whether it's a clean-up job for reporting or a deep dive into your monthly performance, Dana's got you every cell of the way. It's like having a data scientist by your side … <strong>only faster.</strong>
          </p>
          
          <div class="pt-4">
            <a href={Book_Call_URL} target="_blank" rel="noopener noreferrer" class="inline-block">
              <button class="bg-custom_green hover:bg-custom_green_hover text-ivory_light font-medium w-[300px] h-[64px] text-[24px] rounded-full transition duration-300 relative flex items-center group">
                <div class="flex-grow text-center pr-8">Chat with Dana</div>
                <div class="absolute right-8 flex items-center transition-transform duration-300 group-hover:translate-x-1">
                  <ArrowRight />
                </div>
              </button>
            </a>
          </div>
        </div>

        <!-- Right Column - Screenshot with Animation -->
        <div class="w-full [@media(min-width:1024px)]:w-1/2">
          <div class="image-container relative w-full h-[60vw] md:h-[500px] flex items-center justify-center">
            <!-- Fixed stack of cards that never get created/destroyed -->
            {#each cards as card (card.id)}
              <div class="card absolute w-full position-{card.position}">
                <img 
                  src={imagePaths[card.imageIndex]} 
                  alt="Dana Screenshot" 
                  class="w-full h-auto rounded-xl shadow-[0px_64px_128px_0px_rgba(0,40,140,0.15)]"
                />
              </div>
            {/each}
          </div>
        </div>
        
      </div>
      
      <!-- Four Column Feature Section -->
      <div class="grid grid-cols-1 sm:grid-cols-2 [@media(min-width:1024px)]:grid-cols-4 gap-8 mt-16">
        <!-- Feature 1 -->
        <div class="pt-6 border-t border-ink flex flex-col gap-2 ">
          <img src="/images/landing/dana-icon-star.png" alt="" class="w-6 h-6 mr-3" aria-hidden="true" />
          <h3 class="text-md font-bold text-ink mt-4">Total Data Mastery</h3>
          <p class="text-ink">Say goodbye to how-to tutorials and tedious data prep. Dana scrubs it clean and shares pro tips, unlocking powerful marketing moves fast.</p>
        </div>
        
        <!-- Feature 2 -->
        <div class="pt-6 border-t border-ink flex flex-col gap-2 ">
          <img src="/images/landing/dana-icon-lightbulb.png" alt="" class="w-6 h-6 mr-3" aria-hidden="true" />
          <h3 class="text-md font-bold text-ink mt-4">Cross-Channel Clarity</h3>
          <p class="text-ink">Dana unifies your email, paid, social, and analytics data, revealing how customers vibe with your brand. Smarter decisions, no guesswork—just results.</p>
        </div>
        
        <!-- Feature 3 -->
        <div class="pt-6 border-t border-ink flex flex-col gap-2 ">
          <img src="/images/landing/dana-icon-bolt.png" alt="" class="w-6 h-6 mr-3" aria-hidden="true" />
          <h3 class="text-md font-bold text-ink mt-4">Lightning-Quick Wins</h3>
          <p class="text-ink">No more waiting on sluggish data fixes. Hook up your sources, and Dana's on it, dishing out insights like your round-the-clock analyst.</p>
        </div>
        
        <!-- Feature 4 -->
        <div class="pt-6 border-t border-ink flex flex-col gap-2 ">
          <img src="/images/landing/dana-icon-heart.png" alt="" class="w-6 h-6 mr-3" aria-hidden="true" />
          <h3 class="text-md font-bold text-ink mt-4">Your AI Analyst BFF</h3>
          <p class="text-ink">Dana's not just tech—it's your partner, helping you with repetitive tasks so you can amp up your campaigns.</p>
        </div>
      </div>
    </div>
  </div>
</section>
