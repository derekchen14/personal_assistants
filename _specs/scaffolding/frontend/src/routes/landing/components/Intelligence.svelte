<script lang="ts">
  import ArrowRight from '../../application/lib/icons/ArrowRight.svelte';
  import { onMount } from 'svelte';
  import { Book_Call_URL } from '$lib/constants';
  
  // Card data array
  const cards = [
    {
      image: "/images/landing/intelligence-reasoning.svg",
      alt: "Transparent reasoning",
      title: "Transparent reasoning",
      expandedInfo: `<em>You shouldn't have to guess what your tools are thinking.</em>

Marketers need to trust the numbers they act on—but with most AI tools, transparency is an afterthought. Soleda's AI agent, Dana, makes every decision traceable and every calculation explainable. No black-box magic, no vague outputs—just real, contextual reasoning that you can follow step-by-step. When a metric is calculated or a data issue is fixed, Dana shows you how and why.

Instead of trying to decode what went wrong in a spreadsheet, you'll see the logic unfold as if working alongside a highly competent teammate. Whether it's handling broken imports, null values, or detecting anomalies, Dana surfaces suggestions with clarity and checks in before taking action—keeping you fully in control.`
    },
    {
      image: "/images/landing/intelligence-accuracy.svg",
      alt: "Built for accuracy",
      title: "Built for accuracy",
      expandedInfo: `<em>You can't afford decisions based on assumptions.</em>

Accuracy isn't just a nice-to-have—it's the difference between wasted spend and high-impact campaigns. Soleda's agents are built from the ground up to understand the messy reality of marketing data. With a robust natural language understanding layer, Dana takes time to truly grasp your unique data environment before executing anything, eliminating the ambiguity that derails so many insights.

From unifying inconsistent customer data across tools, to parsing mismatched naming conventions and broken joins, Dana doesn't cut corners. Rather than force-fitting a model, it analyzes, cross-checks, and confirms—resulting in insights that are not just plausible, but dependable. That means fewer gut-checks and second-guessing, and more time driving growth.`
    },
    {
      image: "/images/landing/intelligence-adaptive.svg",
      alt: "Adaptive self-learning",
      title: "Adaptive self-learning",
      expandedInfo: `<em>Because your business isn't a template.</em>

Every marketing org defines success differently—whether it's a paid subscriber, a newsletter sign-up, or funnel progression. Soleda's AI learns what your team values most, adjusting its behavior to match your KPIs, naming conventions, and workflows. There's no need for rigid playbooks or re-training: Dana adapts in real time through natural interaction.

Unlike brittle automations or pre-built dashboards that break at the slightest change, Dana evolves with your business. It remembers what matters to you, learns from feedback, and starts to anticipate your needs—automating repeatable tasks while staying responsive to new challenges. So as your strategy shifts, your data agent grows with you.`
    }
  ];

  // State management
  let activeCardIndex = -1;
  let isModalOpen = false;
  let opacities = cards.map(() => 1);
  let cardsVisible = false;

  // Handle card click
  function handleCardClick(index) {
    if (!isModalOpen) {
      activeCardIndex = index;
      opacities[index] = 0;
      isModalOpen = true;
      document.body.style.overflow = 'hidden';
    }
  }

  // Close modal
  function closeModal() {
    isModalOpen = false;
    if (activeCardIndex >= 0) {
      opacities[activeCardIndex] = 1;
      activeCardIndex = -1;
    }
    document.body.style.overflow = 'auto';
  }

  onMount(() => {
    // Set up IntersectionObserver to detect when cards section is 50% visible
    const cardsSection = document.querySelector('.cards-section');
    
    if (cardsSection) {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            cardsVisible = true;
            observer.unobserve(entry.target);
          }
        });
      }, {
        threshold: 0.25 // Trigger when 50% of element is visible
      });
      
      observer.observe(cardsSection);
    }
    
    return () => {
      document.body.style.overflow = 'auto';
    };
  });
</script>

<!-- Intelligence Section -->
<section class="relative py-24 bg-[url('/images/landing/intelligence-background.webp')] bg-center bg-no-repeat" style="background-size: 100% 100%;">
  <div class="px-8 md:px-16">
    <div class="max-w-[1280px] mx-auto">
      <!-- Header Area -->
      <div class="flex flex-col md:flex-row gap-8 md:gap-12 items-end mb-16 pr-0 md:pr-24 md:pr-6">
        <h2 class="text-4xl md:text-5xl font-[600] text-ivory font-rem w-full md:w-1/2 lg:w-1/3 space-y-2 mb-0">
          <span class="block leading-[1.2]">Actual</span>
          <span class="block leading-[1.2]">Intelligence.</span>
        </h2>
        <p class="text-md md:text-md text-ivory w-full md:w-1/2 mb-0">
          Our agents are your ultimate allies, born from cutting-edge AI research. Armed with powerful tools and a natural ability to seek clarity, they boost your productivity so you can deliver exceptional results.
        </p>
      </div>

      <!-- Cards Grid -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-16 cards-section">
        {#each cards as card, index}
          <div 
            class="bg-white rounded-3xl p-6 flex flex-col w-full relative cursor-pointer transition-all duration-300 group card-animate {cardsVisible ? 'card-visible' : ''}"
            style="opacity: {opacities[index] * (cardsVisible ? 1 : 0)}; transition-delay: {index * 150}ms;"
            on:click={() => handleCardClick(index)}
            role="button"
            tabindex="0"
            on:keydown={(e) => e.key === 'Enter' && handleCardClick(index)}
          >
            <div class="absolute bottom-6 right-6 w-8 h-8 flex items-center justify-center">
              <div class="absolute w-full h-full rounded-full border border-black/25 group-hover:bg-black transition-colors"></div>
              <div class="w-4 h-[2px] bg-black group-hover:bg-white absolute transition-colors"></div>
              <div class="h-4 w-[2px] bg-black group-hover:bg-white absolute transition-colors"></div>
            </div>
            <img 
              src={card.image}
              alt={card.alt}
              class="w-full h-auto mb-6"
            />
            <h3 class="text-xl md:text-sm font-bold text-left text-gray-900 mr-8">
              {card.title}
            </h3>
          </div>
        {/each}
      </div>

      <!-- CTA Button -->
      <div class="flex justify-center">
        <a href={Book_Call_URL} target="_blank" rel="noopener noreferrer" class="inline-block">
          <button class="bg-stone-50 hover:bg-white text-slate-950 font-medium w-[300px] h-[64px] text-[24px] rounded-full transition duration-300 shadow-lg relative flex items-center group text-ink">
            <div class="flex-grow text-center pr-8">Learn more</div>
            <div class="absolute right-8 flex items-center transition-transform duration-300 group-hover:translate-x-1">
              <ArrowRight />
            </div>
          </button>
        </a>
      </div>
    </div>
  </div>
</section>

<!-- Modal Overlay -->
{#if isModalOpen && activeCardIndex >= 0}
  <div 
    class="fixed inset-0 bg-black/80 backdrop-blur-[16px] z-50 transition-opacity duration-300 flex items-start justify-center p-4 pt-16 overflow-y-auto" 
    style="opacity: {isModalOpen ? 1 : 0}"
    on:click={closeModal}
  >
    <div 
      class="bg-ivory rounded-3xl p-8 max-w-2xl w-full relative mb-16 animate-modal"
      on:click|stopPropagation={() => {}}
    >
      <!-- Close button -->
      <button 
        class="absolute top-4 right-4 w-8 h-8 flex items-center justify-center group"
        on:click={closeModal}
      >
        <div class="absolute w-full h-full rounded-full border border-black/25 group-hover:bg-black transition-colors"></div>
        <div class="w-4 h-[2px] bg-black group-hover:bg-white absolute rotate-45 transition-colors"></div>
        <div class="w-4 h-[2px] bg-black group-hover:bg-white absolute -rotate-45 transition-colors"></div>
      </button>
      
      <div class="flex justify-center">
        <img 
          src={cards[activeCardIndex].image}
          alt={cards[activeCardIndex].alt}
          class="w-1/2 mb-8"
        />
      </div>
      
      <h3 class="text-3xl font-bold text-left text-gray-900 mb-6 text-center">
        {cards[activeCardIndex].title}
      </h3>
      <div class="text-gray-800 text-lg leading-relaxed space-y-6 whitespace-pre-line">
        {@html cards[activeCardIndex].expandedInfo}
      </div>
      <div class="flex justify-center mt-8">
        <button 
          class="bg-black text-white font-medium px-12 py-3 rounded-full transition duration-300 hover:bg-gray-800"
          on:click={closeModal}
        >
          Back
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  @keyframes modalEntrance {
    from {
      opacity: 0;
      transform: translateY(20px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .animate-modal {
    animation: modalEntrance 0.4s ease-out forwards;
  }
  
  .card-animate {
    opacity: 0;
    transform: translateY(100px);
    transition: opacity 1s ease-out, transform 1s ease-out;
    /* Ensure cards are initially invisible */
    visibility: visible;
  }
  
  .card-visible {
    opacity: 1;
    transform: translateY(0);
  }
</style>
