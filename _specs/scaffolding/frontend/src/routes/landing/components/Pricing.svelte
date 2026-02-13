<script lang="ts">
  import ArrowRight from '../../application/lib/icons/ArrowRight.svelte';
  import { Waitlist_URL } from '$lib/constants.js';
</script>

<section class="relative py-20  bg-[url('/images/landing/pricing-background.webp')] bg-center bg-no-repeat" style="background-size: 100% 100%;">
  <div class="max-w-[1280px] mx-auto">
    <h2 class="text-4xl md:text-5xl font-[600] text-gray-1000 font-rem text-center mb-16">
      <span class="block leading-[1.2]">Plans & Pricing</span>
    </h2>
    
    <div class="flex flex-col [@media(min-width:1024px)]:flex-row justify-center my-8">
      <!-- Basic Plan -->
      <div class="w-full max-w-md mx-auto rounded-3xl [@media(min-width:1024px)]:rounded-none [@media(min-width:1024px)]:rounded-tl-3xl [@media(min-width:1024px)]:rounded-bl-3xl [@media(min-width:1024px)]:w-1/4 [@media(min-width:1024px)]:max-w-none [@media(min-width:1024px)]:mx-0 bg-ivory_light transition-all duration-300 flex flex-col h-full mb-6 [@media(min-width:1024px)]:mb-0 border-2 border-[#006BB9]/10 [@media(min-width:1024px)]:border-r-0 hover:-translate-y-1 hover:shadow-[0_0_20px_rgba(0,107,185,0.5)]">
        <div class="p-6 text-3xl font-bold text-center border-b border-b-2 border-[#006BB9]/10">
          Basic Plan
          <div class="text-lg mt-1">($20 per month)</div>
        </div>

        <ul class="w-full text-center text-md p-4 flex-grow">
          <li class="py-3">14-day Free Trial</li>
          <li class="py-3">Excel and CSV uploads</li>
          <li class="py-3">Ask Unlimited Questions</li>
        </ul>
        
        <div class="p-6 text-center mt-auto">
          <div class="w-full pb-4 text-gray-700 text-lg">
            Try it out Today!
          </div>
          <a href={Waitlist_URL} target="_blank" rel="noopener noreferrer" class="inline-block">
            <button class="hover:bg-white text-black font-medium w-[200px] h-[50px] text-[18px] rounded-full transition duration-300 relative flex items-center group border-2 border-black">
              <div class="flex-grow text-center">Activate Now</div>
            </button>
          </a>
        </div>
      </div>

      <!-- Pro Plan -->
      <div class="w-full bg-white max-w-md mx-auto [@media(min-width:1024px)]:w-1/3 [@media(min-width:1024px)]:max-w-none [@media(min-width:1024px)]:mx-0 rounded-3xl bg-ivory_light [@media(min-width:1024px)]:-mt-8 relative z-10 border-2 border-[#006BB9]/10 transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_0_20px_rgba(0,107,185,0.5)] flex flex-col h-full mb-6 [@media(min-width:1024px)]:mb-0">
        <div class="p-6 text-3xl font-bold text-center border-b border-b-2 border-[#006BB9]/10">
          Pro Plan
          <div class="text-lg mt-1">($99 per month)</div>
        </div>
        
        <ul class="w-full text-center text-base font-bold text-lg p-4 flex-grow">
          <li class="py-3">Automated Reporting</li>
          <li class="py-3">10+ Data Source Connectors</li>
          <li class="py-3">Long-term Data Storage</li>
          <li class="py-3">Priority Customer Service</li>
        </ul>
        
        <div class="p-6 text-center mt-auto">
          <div class="w-full pb-4 text-2xl font-bold">
            Our Most Popular Option
          </div>
          <a href={Waitlist_URL} target="_blank" rel="noopener noreferrer" class="inline-block">
            <button class="bg-[#006BB9] hover:bg-secondary text-white font-medium w-[200px] h-[50px] text-[18px] rounded-full transition duration-300 relative flex items-center group">
              <div class="flex-grow text-center pr-8">Get Started</div>
              <div class="absolute right-6 flex items-center transition-transform duration-300 group-hover:translate-x-1">
                <ArrowRight />
              </div>
            </button>
          </a>
        </div>
      </div>

      <!-- Enterprise -->
      <div class="w-full max-w-md mx-auto rounded-3xl [@media(min-width:1024px)]:rounded-none [@media(min-width:1024px)]:rounded-tr-3xl [@media(min-width:1024px)]:rounded-br-3xl [@media(min-width:1024px)]:w-1/4 [@media(min-width:1024px)]:max-w-none [@media(min-width:1024px)]:mx-0 bg-ivory_light transition-all duration-300 flex flex-col h-full mb-6 [@media(min-width:1024px)]:mb-0 border-2 border-[#006BB9]/10 [@media(min-width:1024px)]:border-l-0 hover:-translate-y-1 hover:shadow-[0_0_20px_rgba(0,107,185,0.5)]">
        <div class="p-6 text-3xl font-bold text-center border-b border-b-2 border-[#006BB9]/10">
          Enterprise
          <div class="text-lg mt-1">(Custom Pricing)</div>
        </div>
        
        <ul class="w-full text-center text-md p-4 flex-grow">
          <li class="py-3">Secure Private Cloud</li>
          <li class="py-3">Dedicated Admin Controls</li>
          <li class="py-3">Personally Trained Model</li>
        </ul>
        
        <div class="p-6 text-center mt-auto">
          <div class="w-full pb-4 text-gray-700 text-lg">
            Boost Your Marketing
          </div>
          <a href="mailto:sales@soleda.ai" class="inline-block">
            <button class="hover:bg-white text-black font-medium w-[200px] h-[50px] text-[18px] rounded-full transition duration-300 relative flex items-center group border-2 border-black">
              <div class="flex-grow text-center">Contact Sales</div>
            </button>
          </a>
        </div>
      </div>
    </div>
  </div>
</section>
