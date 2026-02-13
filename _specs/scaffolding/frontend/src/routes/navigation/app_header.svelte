<script lang="ts">
  import { onMount } from 'svelte';
  import { chatActive } from '@store';
  import { getCookie } from '../getCookie';
  import appBanner from '/src/assets/banner_app.png';
  import standardLogo from '/src/assets/logo_white.png';
  let accessToken;
  let authorized;

  onMount(() => {
    accessToken = getCookie('access_token');
    // Check if the access token is NOT present. If not, redirect to the login page.
    authorized = !accessToken ? false : true;
  });
</script>

<nav class="flex items-center justify-between flex-wrap bg-gray-600">

  {#if $chatActive}   <!-- Logos -->
    <div class="flex items-center flex-shrink-0 text-white mr-3">
      <img src={standardLogo} class="logo w-8 my-2 ml-4 mr-3" alt="Soleda Logo" />
      <h2 class="title-font text-3xl mt-1">Soleda</h2>
    </div>
  {:else}
    <div class="h-16 lg:h-24 xl:h-24">
      <a href="/">
        <img src={appBanner} class="logo ml-1 h-full" alt="Soleda Logo" />
      </a>
    </div>
  {/if}

  <!-- Primary Navigation -->
  <div class="w-full flex-grow hidden p-2 lg:flex lg:items-center lg:w-auto xl:text-lg">
    <div class="lg:flex-grow space-x-4 {$chatActive ? 'ml-2 text-sm' : ''} ">
      <a href="/dashboard" class="block mt-4 lg:inline-block lg:mt-0 text-white hover:text-teal-300">
        Dashboard
      </a>
      <a href="https://x8l3b1ogtwp.typeform.com/to/dXWQchhR"
        class="block mt-4 lg:inline-block lg:mt-0 text-white hover:text-teal-300">
        Feedback
      </a>
      <a href="/logout" class="block mt-4 lg:inline-block lg:mt-0 text-white hover:text-teal-300">
        Logout
      </a>
    </div>
    <div>
      <a href="mailto:help@soleda.ai"
        class="inline-block text-sm mt-4 leading-none border rounded text-teal-200 border-teal-300
        lg:mt-0 xl:text-lg {$chatActive ? 'px-3 py-1.5' : 'px-4 py-2 mr-3'}
      hover:border-transparent hover:text-white hover:bg-teal-500">Help</a>
    </div>
  </div>

  <!-- For mobile and smaller screens -->
  <div class="block lg:hidden px-5 py-3">
    <button
      class="flex items-center px-3 py-2 border rounded text-teal-200 border-teal-400
        hover:border-transparent hover:text-white hover:bg-teal-500">
      <svg class="fill-current h-3 w-3" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"
        ><title>Menu</title><path d="M0 3h20v2H0V3zm0 6h20v2H0V9zm0 6h20v2H0v-2z" /></svg>
    </button>
  </div>

</nav>
