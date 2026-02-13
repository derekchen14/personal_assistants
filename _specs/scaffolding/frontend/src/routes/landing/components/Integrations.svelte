<script>
  import { onMount, tick } from 'svelte';
  import { writable } from 'svelte/store';
  import { browser } from '$app/environment';
  
  // Constants
  const ANIMATION_CYCLE_INTERVAL = 2750;
  const DOT_ANIMATION_DURATION = 2000;
  const DOT_SEND_CHANCE = 0.4;
  const PULSE_DURATION = 500;
  const INTEGRATION_TRANSITION_CHANCE = 0.3;
  const INTEGRATION_SPIN_DURATION = 1500;

  // Integration data
  const allIntegrations = [
    { src: '/images/landing/integrations-drive.png', alt: 'Google Drive' },
    { src: '/images/landing/integrations-ga4.png', alt: 'Google Analytics' },
    { src: '/images/landing/integrations-gads.png', alt: 'Google Ads' },
    { src: '/images/landing/integrations-hubspot.png', alt: 'HubSpot' },
    { src: '/images/landing/integrations-meta.png', alt: 'Meta' },
    { src: '/images/landing/integrations-salesforce.png', alt: 'Salesforce' },
    { src: '/images/landing/integrations-amplitude.png', alt: 'Amplitude' },
    { src: '/images/landing/integrations-googlecloud.png', alt: 'Google Cloud' },
    { src: '/images/landing/integrations-braze.png', alt: 'Braze' },
    { src: '/images/landing/integrations-databricks.png', alt: 'Databricks' },
    { src: '/images/landing/integrations-iterable.png', alt: 'Iterable' },
    { src: '/images/landing/integrations-mailchimp.png', alt: 'Mailchimp' },
    { src: '/images/landing/integrations-snowflake.png', alt: 'Snowflake' }
  ];

  const iconPositions = [
    { x: -256, y: -128 }, { x: -312, y: 0 }, { x: -256, y: 128 },
    { x: 256, y: -128 }, { x: 312, y: 0 }, { x: 256, y: 128 }
  ];

  const pathData = [
    "M 144,97 H 242 C 252,97 262,100 269,107 L 400,225",    // upper left
    "M 88,225 L 400,225",                                   // middle left
    "M 144,353 H 242 C 252,353 262,350 269,343 L 400,225",  // lower left
    "M 656,97 H 558 C 548,97 538,100 531,107 L 400,225",    // upper right
    "M 712,225 L 400,225",                                  // middle right
    "M 656,353 H 558 C 548,353 538,350 531,343 L 400,225"   // lower right
  ];

  // State management
  const currentIntegrations = writable([]);
  const transitioningIcons = writable({});
  const dots = writable([]);
  let centerPulsing = false;
  let iconPulsing = Array(6).fill(false);
  let shouldSwitchIcons = false;
  
  // Responsive state
  let containerWidth = 800;
  let diagramScale = 1;
  let containerElement;
  let sectionElement;
  let animationFrameId;
  let animationInterval;
  
  // Parallax state
  let scrollY = 0;
  let sectionTop = 0;
  let sectionHeight = 0;
  let viewportHeight = 0;
  let parallaxFactor = 0.8;

  // Core functions
  function getRandomIntegrations() {
    const shuffled = [...allIntegrations].sort(() => 0.5 - Math.random());
    return shuffled.slice(0, 6);
  }

  function calculateOpacity(progress) {
    if (progress < 0.1) return progress * 10;
    if (progress > 0.9) return (1 - progress) * 10;
    return 1;
  }

  // Animation functions
  function pulseIcon(index) {
    iconPulsing[index] = true;
    setTimeout(() => iconPulsing[index] = false, PULSE_DURATION);
  }

  function pulseCenter() {
    centerPulsing = true;
    setTimeout(() => centerPulsing = false, PULSE_DURATION);
  }

  function sendDot(iconIndex) {
    pulseIcon(iconIndex);
    const newDot = { id: Date.now() + Math.random(), iconIndex, progress: 0, opacity: 0 };
    dots.update(allDots => [...allDots, newDot]);
    
    const startTime = Date.now();
    function animateDot() {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / DOT_ANIMATION_DURATION, 1);
      
      dots.update(allDots => allDots.map(dot => {
        if (dot.id === newDot.id) {
          return { ...dot, progress, opacity: calculateOpacity(progress) };
        }
        return dot;
      }));
      
      if (progress >= 0.75) {
        pulseCenter();
        setTimeout(() => dots.update(allDots => allDots.filter(dot => dot.id !== newDot.id)), 100);
      } else {
        animationFrameId = requestAnimationFrame(animateDot);
      }
    }
    animationFrameId = requestAnimationFrame(animateDot);
  }

  function startIconTransition(index) {
    const currentVisible = [...$currentIntegrations];
    Object.entries($transitioningIcons).forEach(([i, transition]) => {
      if (transition.new) currentVisible[parseInt(i)] = transition.new;
    });
    
    const availableIntegrations = allIntegrations.filter(i => 
      !currentVisible.some(ci => ci.alt === i.alt)
    );

    if (availableIntegrations.length > 0) {
      const newIcon = availableIntegrations[Math.floor(Math.random() * availableIntegrations.length)];
      transitioningIcons.update(state => ({
        ...state, [index]: { old: $currentIntegrations[index], new: newIcon }
      }));

      const container = document.querySelector(`.icon-wrapper:nth-child(${index + 1}) .icon-container`);
      if (container) void container.offsetWidth;

      setTimeout(() => {
        currentIntegrations.update(current => {
          const newCurrent = [...current];
          newCurrent[index] = newIcon;
          return newCurrent;
        });
        transitioningIcons.update(state => {
          const newState = { ...state };
          delete newState[index];
          return newState;
        });
      }, INTEGRATION_SPIN_DURATION);
    }
  }

  // Responsive functions
  function updateScale() {
    if (containerElement) {
      containerWidth = containerElement.clientWidth;
      diagramScale = Math.min(1, (containerWidth / 800));
    }
  }

  function updateParallax() {
    if (sectionElement) {
      const rect = sectionElement.getBoundingClientRect();
      sectionTop = rect.top;
      sectionHeight = rect.height;
      viewportHeight = window.innerHeight;
      scrollY = window.scrollY;
    }
  }

  // Reactive statements
  $: if (browser) {
    currentIntegrations.set(getRandomIntegrations());
    document.documentElement.style.setProperty('--scale-factor', diagramScale);
    document.documentElement.style.setProperty('--spin-duration', `${INTEGRATION_SPIN_DURATION}ms`);
  }
  $: scaledPathData = pathData.map(path => 
    path.replace(/(\d+)/g, match => (parseFloat(match) * diagramScale).toString())
  );
  $: parallaxOffset = (sectionTop + sectionHeight/2 - viewportHeight/2) / viewportHeight * parallaxFactor * 100;
  $: activeDots = $dots;
  $: currentIcons = $currentIntegrations;
  $: transitioning = $transitioningIcons;

  // Lifecycle
  onMount(() => {
    if (!browser) return;

    containerElement = document.querySelector('.integration-diagram-container');
    sectionElement = document.querySelector('.integration-section');
    
    animationInterval = setInterval(() => {
      if (shouldSwitchIcons) {
        for (let i = 0; i < 6; i++) {
          if (Math.random() < INTEGRATION_TRANSITION_CHANCE) startIconTransition(i);
        }
      } else {
        for (let i = 0; i < 6; i++) {
          if (Math.random() < DOT_SEND_CHANCE) sendDot(i);
        }
      }
      shouldSwitchIcons = !shouldSwitchIcons;
    }, ANIMATION_CYCLE_INTERVAL);
    
    updateScale();
    updateParallax();
    window.addEventListener('resize', updateScale);
    window.addEventListener('scroll', updateParallax);
    window.addEventListener('resize', updateParallax);
    
    return () => {
      clearInterval(animationInterval);
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', updateScale);
      window.removeEventListener('scroll', updateParallax);
      window.removeEventListener('resize', updateParallax);
    };
  });
</script>

<section class="relative py-24 bg-ivory overflow-hidden integration-section">
  <div class="px-4 md:px-16">
    <div class="max-w-[1280px] mx-auto">
      <!-- Background Circles with Parallax -->
      <div 
        class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[1326px] h-[1326px] transition-transform duration-100"
        style="transform: translate(-50%, calc(-50% + {parallaxOffset * 1.8}px));"
      >
        <svg class="w-full h-full" viewBox="0 0 1326 1326">
          <circle cx="663" cy="663" r="662" class="stroke-ink/5" stroke-width="4" fill="none"/>
        </svg>
      </div>
      <div 
        class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[1024px] h-[1024px] transition-transform duration-100"
        style="transform: translate(-50%, calc(-50% + {parallaxOffset * 0.6}px));"
      >
        <svg class="w-full h-full" viewBox="0 0 1024 1024">
          <circle cx="512" cy="512" r="510" class="stroke-ink/10" stroke-width="4" fill="none"/>
        </svg>
      </div>

      <!-- Header Area -->
      <div class="flex flex-col items-center text-center max-w-3xl mx-auto">
        <h2 class="text-4xl md:text-5xl font-[600] text-ink font-rem mb-6">
          <span class="block leading-[1.2]">All your data.</span>
          <span class="block leading-[1.2]">In one place.</span>
        </h2>
        <p class="text-md md:text-lg text-ink w-full lg:w-3/4">
          You're a marketer, not a data wrangler. We unify your data in one hub, so you can easily connect, analyze, and uncover winning insights.
        </p>
      </div>

      <!-- Integration Diagram -->
      <div class="relative w-full max-w-[800px] aspect-[16/9] mx-auto integration-diagram-container [transform-style:preserve-3d] [perspective:1000px] will-change-transform">
        <!-- Connection Lines -->
        <svg 
          class="absolute inset-0 w-full h-full" 
          style="z-index: 0;" 
          viewBox="0 0 800 450" 
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
            {#each pathData as path, i}
              <path id="path-{i}" d={path}></path>
            {/each}
          </defs>
          
          {#each pathData as path, i}
            <path 
              d={path} 
              class="stroke-ink/10 fill-none" 
              stroke-width="4"
            />
          {/each}
        </svg>

        <!-- Data Dots with Ring -->
        {#each activeDots as dot (dot.id)}
          <div class="data-dot absolute z-10 will-change-[offset-distance,opacity]"
            style="opacity: {dot.opacity}; offset-path: path('{scaledPathData[dot.iconIndex]}');
              offset-distance: {dot.progress * 100}%;
              transform: scale({diagramScale});">
            <div class="w-4 h-4 relative">
              <div class="absolute inset-0 rounded-full border-2 border-custom_green bg-transparent"></div>
              <div class="absolute top-1/2 left-1/2 w-2 h-2 rounded-full bg-custom_green -translate-x-1/2 -translate-y-1/2"></div>
            </div>
          </div>
        {/each}

        <!-- Center Icon -->
        <div 
          class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[200px] h-[200px] bg-white rounded-full shadow-[0px_32px_64px_0px_rgba(0,107,185,0.50)] flex items-center justify-center transition-transform duration-300 ease-in z-20"
          class:pulse-destination={centerPulsing}
          style="transform: translate(-50%, -50%) scale({diagramScale});">
          <img src="/images/landing/rethinking-logo.svg" alt="Soleda" class="w-3/4" />
        </div>

        <!-- Integration Icons -->
        {#each currentIcons as integration, i}
          <div class="icon-wrapper absolute top-1/2 left-1/2 z-20"
            style="transform: translate(calc({iconPositions[i].x * diagramScale}px - 50%), calc({iconPositions[i].y * diagramScale}px - 50%));">
            <div class="w-[100px] h-[100px] bg-white rounded-full shadow-[0px_8px_16px_0px_rgba(0,107,185,0.25)] flex items-center justify-center transition-transform duration-300 ease-in"
              class:pulse-source={iconPulsing[i]}
              style="transform: scale({diagramScale});">
              <div class="w-[90px] h-[90px] relative">
                {#if transitioning[i]}
                  <img src={transitioning[i].old.src} alt={transitioning[i].old.alt} 
                    class="absolute inset-0 w-full h-full object-contain animate-spin-out" />
                  <img src={transitioning[i].new.src} alt={transitioning[i].new.alt} 
                    class="absolute inset-0 w-full h-full object-contain animate-spin-in" />
                {:else}
                  <img src={integration.src} alt={integration.alt} 
                    class="w-full h-full object-contain" />
                {/if}
              </div>
            </div>
          </div>
        {/each}
      </div>
    </div>
  </div>
</section>

<style>
  /* Animation for source icon pulse */
  .pulse-source {
    transform: scale(calc(1.15 * var(--scale-factor, 1))) !important;
    transition-timing-function: ease-in !important;
    will-change: transform;
  }
  
  /* Animation for destination icon pulse */
  .pulse-destination {
    transform: translate(-50%, -50%) scale(calc(1.05 * var(--scale-factor, 1))) !important;
    transition-timing-function: ease-in !important;
    will-change: transform;
  }

  /* Cube rotation animation - can't be done with standard Tailwind */
  @keyframes cube-rotate {
    0% { transform: rotateX(0) rotateY(0) rotateZ(0); }
    100% { transform: rotateX(360deg) rotateY(360deg) rotateZ(360deg); }
  }

  /* Alternative pulse animation */
  @keyframes alt-pulse {
    0% { transform: scale(1); opacity: 0.6; }
    100% { transform: scale(2); opacity: 0; }
  }

  /* Icon transition animations */
  @keyframes spinOut {
    0% {
      transform: rotate(0deg);
      opacity: 1;
    }
    100% {
      transform: rotate(180deg);
      opacity: 0;
    }
  }

  @keyframes spinIn {
    0% {
      transform: rotate(-180deg);
      opacity: 0;
    }
    100% {
      transform: rotate(0deg);
      opacity: 1;
    }
  }

  .animate-spin-out {
    animation: spinOut var(--spin-duration, 1000ms) ease-in-out forwards;
  }

  .animate-spin-in {
    animation: spinIn var(--spin-duration, 1000ms) ease-in-out forwards;
  }
</style>
