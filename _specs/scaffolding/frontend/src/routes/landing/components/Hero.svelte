<script lang="ts">
  import { onMount } from 'svelte';
  import ArrowRight from '../../application/lib/icons/ArrowRight.svelte';
  import { Book_Call_URL } from '$lib/constants';

  onMount(() => {
    const splineViewer = document.getElementById('hero-spline');
    if (splineViewer) {
      splineViewer.addEventListener('load-complete', () => {
        console.log('Spline scene loaded');
        const splineApp = splineViewer._spline; // Access runtime via _spline
        const icosphere = splineApp.findObjectByName('Icosphere');
        let initialRotation = icosphere.rotation.x;
        window.addEventListener('scroll', () => {
          icosphere.rotation.x = initialRotation - (window.scrollY * 0.0013);
        });
      });
    }
  });
</script>

<section class="relative pt-0 -mb-4 md:-mb-10 bg-[url('/images/landing/hero-background.webp')] 
                bg-center bg-no-repeat text-ink" style="background-size: 100% 100%;">
  <!-- Spline Scene Container -->
  <div class="absolute inset-0 w-full h-full">
    <script type="module" src="https://unpkg.com/@splinetool/viewer@1.9.81/build/spline-viewer.js"></script>
    <spline-viewer id="hero-spline" class="w-full h-full fixed inset-0"
      url="https://prod.spline.design/w-cMQROThPJpsGey/scene.splinecode">
    </spline-viewer>
  </div>

  <!-- Content Container -->
  <div class="relative z-10">
    <div class="container mx-auto pt-40 pb-4 md:px-6">
      
      <!-- Text and CTA -->
      <div class="max-w-3xl flex flex-col gap-6 mx-auto text-center relative">
        <!-- Your Cursor -->
        <div class="absolute left-10 top-[20%] hidden md:block">
          <img  src="/images/landing/hero-cursor.svg" 
            alt="Your Cursor" class="w-4 h-4 hidden md:block scale-x-[-1]" aria-hidden="true"/>
          <div class="absolute top-4 right-4 rounded bg-blue-600/80 text-ivory_light py-1 px-3">
            You
          </div>
        </div>
        
        <h1 class="text-4xl md:text-6xl font-[600] leading-tight font-rem">
          The Only AI Agent<br />
          Who <span class="relative inline-block"> Understands
            <img src="/images/landing/hero-text-underline.svg" alt="underline" 
              class="absolute -bottom-3 left-[0%] w-[100%]"aria-hidden="true"/>
          </span>
           You
        </h1>
        
        <!-- Dana Cursor -->
        <div class="absolute right-4 top-[-4%] hidden md:block">
          <img 
            src="/images/landing/hero-cursor.svg" 
            alt="Dana Cursor" 
            class="w-4 h-4 hidden md:block"
            aria-hidden="true"
          />
          <div class="absolute top-4 left-4 rounded bg-indigo-600/80 text-ivory_light py-1 px-3">
            Dana
          </div>
        </div>
        
        <p class="text-[20px]">
          Clean & analyze your RevOps data to uncover insights in seconds.
        </p>
        <div class="pt-4 flex justify-center">
          <button class="bg-custom_green hover:bg-custom_green_hover text-ivory_light font-medium w-[300px] h-[64px] text-[24px] rounded-full transition duration-300 relative flex items-center group">
            <a href={Book_Call_URL} target="_blank" rel="noopener noreferrer" class="flex-grow text-center pr-8">Book a call</a>
            <div class="absolute right-8 flex items-center transition-transform duration-300 group-hover:translate-x-1">
              <ArrowRight />
            </div>
          </button>
        </div>
        
        <!-- Dashboard image under CTA -->
        <div class="px-4 md:px-0">
          <div class="w-full mt-8 md:mt-16 relative rounded-3xl bg-sky-50 overflow-hidden pb-4 md:pb-8 shadow-[0px_64px_128px_0px_rgba(0,107,185,0.35)]">
            <div class="w-full h-16 flex flex-row justify-start items-center gap-2 px-4 text-ivory_light bg-ink">
              <img src="/images/landing/hero-cursor-ripple.svg" alt="Cursor Ripple" class="w-10 h-10"/>
              <span class="font-bold">Campaign Performance</span>
            </div>
            <div class="w-full flex justify-between gap-.5 md:gap-2 px-2 md:px-6 pt-2 md:pt-4">
              <div class="flex-1 flex flex-col justify-center items-center h-16 md:h-20 bg-slate-50 rounded-xl shadow-[0_16px_32px_0_rgba(17,24,38,0.15)] mx-1">
                <span class="text-xs">CTR</span>
                <span class="font-bold font-rem">3.2%</span>
              </div>
              <div class="flex-1 flex flex-col justify-center items-center h-16 md:h-20 bg-slate-50 rounded-xl shadow-[0_16px_32px_0_rgba(17,24,38,0.15)] mx-1">
                <span class="text-xs">CPC</span>
                <span class="font-bold font-rem">$1.51</span>
              </div>
              <div class="flex-1 flex flex-col justify-center items-center h-16 md:h-20 bg-slate-50 rounded-xl shadow-[0_16px_32px_0_rgba(17,24,38,0.15)] mx-1">
                <span class="text-xs">CVR</span>
                <span class="font-bold font-rem">4.6%</span>
              </div>
              <div class="flex-1 flex flex-col justify-center items-center h-16 md:h-20 bg-slate-50 rounded-xl shadow-[0_16px_32px_0_rgba(17,24,38,0.15)] mx-1">
                <span class="text-xs">CAC</span>
                <span class="font-bold font-rem">$70</span>
              </div>
              <div class="flex-1 flex flex-col justify-center items-center h-16 md:h-20 bg-slate-50 rounded-xl shadow-[0_16px_32px_0_rgba(17,24,38,0.15)] mx-1">
                <span class="text-xs">ROAS</span>
                <span class="font-bold font-rem">2.4x</span>
              </div>
            </div>
            <div class="w-full flex justify-between gap-.5 md:gap-2 px-2 md:px-6 pt-2 md:pt-4">
              <div class="flex-1 flex flex-col gap-2 justify-start items-center bg-slate-50 rounded-xl shadow-[0_16px_32px_0_rgba(17,24,38,0.15)] mx-1 py-4 px-4">
                <span class="w-full text-left font-bold font-rem">Conversions by Channel</span>
                <img src="/images/landing/hero-conversions.svg" alt="Conversions by Channel" class="w-full h-auto"/>
              </div>
              <div class="flex-1 flex flex-col gap-2 justify-start items-center bg-slate-50 rounded-xl shadow-[0_16px_32px_0_rgba(17,24,38,0.15)] mx-1 py-4 px-4">
                <span class="w-full text-left font-bold font-rem">Return on Ad Spend</span>
                <img src="/images/landing/hero-roas.svg" alt="Return on Ad Spend" class="w-full h-auto"/>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>
