<script lang="ts">
  import logo from '@assets/logo_color.png';
  import { onMount } from 'svelte';
  import { Feedback_URL, Video_URL } from '$lib/constants.js';
  let authorized;
  let isSafari = false;

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop()?.split(';').shift()?.trim();
  }

  onMount(() => {
    authorized = getCookie('access_token') ? 1 : 0;
    console.log("is authorized: " + getCookie('access_token'));
    
    // Detect Safari browser
    isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);
  });

  let scrollPosition = 0;
  $: headerOpacity = Math.min(scrollPosition / 50, 1);
</script>

<svelte:window bind:scrollY={scrollPosition} />
<!--Nav-->
<nav id="header" class="fixed w-full z-30 top-0 transition-all duration-" 
     style={isSafari ? 
       "background-color: #FFFEFA;" : 
       `background-color: rgba(255, 245, 238, ${headerOpacity * 0.15}); backdrop-filter: brightness(${1 + headerOpacity * 8}) saturate(${1 + headerOpacity * .05}) blur(${headerOpacity * 16}px);`}>
  <div class="w-full px-4 md:px-16 mx-auto flex items-center justify-between mt-0 pt-3 pb-2">
    <div class="max-w-[1280px] w-full mx-auto flex items-center justify-between">
      <div class="flex items-center">
        <!-- svelte-ignore a11y-invalid-attribute -->
        <a href="/" class="flex items-center gap-2">
          <img src={logo} class="h-8 my-auto" alt="Soleda Logo" />
          <span class="text-3xl font-semibold title-font leading-none pt-[2px]">Soleda</span>
        </a>
      </div>
      <div id="nav-content" class="hidden md:flex flex-row items-center z-20 gap-4">

        {#if authorized}
          <a class="text-ink font-semibold hover:underline transition duration-300 py-2 ml-4" 
             href="/logout">Log out</a>
          <a href="/application" 
             class="bg-custom_green text-ivory_light px-8 py-3 rounded-full font-bold hover:bg-opacity-80 transition duration-300">
            Open app
          </a>
        {:else}
          <a class="text-ink font-semibold hover:underline transition duration-300 py-2 ml-4" 
            href="/login">Log in</a>
          <a class="bg-custom_green text-ivory_light px-8 py-3 rounded-full font-bold hover:bg-opacity-80 transition duration-300"
            href="/payment">Sign up</a>
        {/if}
      </div>
    </div>
  </div>
</nav>
