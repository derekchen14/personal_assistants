<script>
  import { onMount } from 'svelte';
  import { serverUrl } from '@store';
  import { goto } from '$app/navigation';
  import { logger } from '$lib/logger'; 

  async function handleLogout() {
    try {
      const response = await fetch(`${serverUrl}/user/logout`, {
        method: 'POST',
        credentials: 'include',
      });
      logger.info('user_logout', 'UserLogin');

      logger.resetSessionID();
      logger.resetUserID();
      logger.resetConversationID();
      
      setTimeout(() => {
        goto('/');
        window.location.href = '/'; // Replace "/" with the URL of your homepage
      }, 3000);
    } catch (error) {
      console.error('Logout failed:', error);
    }
  }

  onMount(() => {
    handleLogout(); // Automatically call handleLogout when the component is mounted
  });
</script>

<svelte:head>
  <title>Soleda: Log-Out</title>
</svelte:head>

<div class="flex flex-col my-auto mx-auto md:col-6">
  <div class="text-center mb-6 px-4">
    <h2 class="text-xl font-semibold mb-2">Thank You for Using Soleda</h2>
    <p class="text-gray-700">
      You have been successfully logged out.
    </p>
    <p class="text-gray-700">
      If you need to use Dana again, please log back in.
    </p>
  </div>

  <div class="text-green-600 signature-font mb-4 text-xl text-center">
    <p>You're being redirected to the home page...</p>
  </div>

  <div class="flex justify-center mt-6">
    <svg class="w-16 h-16 text-green-500" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/>
      <path d="M8 12L11 15L16 9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
  </div>
</div>

<style>
  /* No styling needed */
</style>
