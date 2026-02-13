<script>
  import { serverUrl } from '@store';
  import { goto } from '$app/navigation';
  import { logger } from '$lib/logger'; 
  import { v4 as uuidv4 } from 'uuid';
  import { checkAuthentication } from '$lib/apiUtils';
  import { onMount } from 'svelte';

  let fields = [
    { id: 'email', label: 'Email Address', type: 'email', value: '' },
    { id: 'password', label: 'Password', type: 'password', value: '' },
  ];
  let loginSuccess = false;
  let feedbackMessage = '';
  let isLoading = true;

  onMount(async () => {
    // Check if user is already authenticated
    const isAuthenticated = await checkAuthentication();
    if (isAuthenticated) {
      // If already authenticated, redirect to application
      goto('/application');
    }
    isLoading = false;
  });

  const getUserDetails = async (email, password) => {
    // Make a POST request to the backend API for user login
    const response = await fetch(`${serverUrl}/user/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email: email,
        password: password,
      }),
      credentials: 'include', // Important: include cookies
    });

    // Clone the response so we can use it in two places
    const responseClone = response.clone();
    
    try {
      const json = await responseClone.json();
      const isSuccess = json?.success;
      if (isSuccess == true) {
        const userID = json?.user?.userID;
        // Set new session and user ID
        const sessionID = `sess-${uuidv4().substring(0, 8)}`;
        logger.setSessionID(sessionID);
        logger.setUserID(userID);
      }
    } catch (error) {
      console.warn("Could not parse response JSON:", error);
    }
    
    return response;
  };

  async function handleLogin() {
    feedbackMessage = 'Waking Dana up, please wait...';

    const email = fields.find(field => field.id === 'email').value;
    const password = fields.find(field => field.id === 'password').value;

    if (email.trim() === '' || password.trim() === '') {
      feedbackMessage = 'Please fill in email and password.';
      return;
    }
    try {
      const response = await getUserDetails(email, password);
      if (response.ok) {
        loginSuccess = true;
        feedbackMessage = 'You can now start talking to Dana!';

        // No need to parse response.json() again - userID is already set in getUserDetails

        logger.info('user_login_success', 'UserLogin');
        goto('/application');
      } else if (response.status === 429) {
        loginSuccess = false;
        feedbackMessage = 'Too many login attempts, please try again later.';      

        logger.warning('too_many_login_attempts', 'UserLogin', {
          error_message: feedbackMessage,
          details: {
            email: email,
          },
        });
      } else {
        loginSuccess = false;
        feedbackMessage = 'Incorrect email or password.';      

        logger.warning('invalid_credentials', 'UserLogin', {
          error_message: feedbackMessage,
          details: {
            email: email,
          },
        });
      }
    } catch (err) {
      console.error(err);
      feedbackMessage = 'An error occurred during login.';

      logger.error('user_login_failure', 'UserLogin', {
        details: {
          email: email,
        },
        error: {
          error_type: "client_error",
          error_code: err.code || 'UNKNOWN_ERROR',
          error_message: feedbackMessage,
          browser: navigator.userAgent,
        },
      });
    }
  }
</script>

<svelte:head>
  <title>Soleda: Log-In</title>
</svelte:head>

{#if isLoading}
  <div class="flex justify-center items-center h-screen">
    <p>Loading...</p>
  </div>
{:else}
  <form on:submit|preventDefault={handleLogin} class="flex flex-col my-auto mx-auto md:col-6">
    <div class="text-center mb-6 px-4">
      <h2 class="text-xl font-semibold mb-2">Welcome to Soleda</h2>
      <p class="text-gray-700">
        You must login to use Dana, our data analysis agent.
      </p>
      <p class="text-gray-700">
        If you have any trouble, please contact <a href="mailto:support@soleda.ai" class="text-blue-600 hover:underline">support@soleda.ai</a>.
      </p>
    </div>

    <div class="{loginSuccess ? 'text-green-600' : 'text-cyan-700'} signature-font mb-4 text-xl text-center">
      {#if feedbackMessage}
        <p>{feedbackMessage}</p>
      {/if}
    </div>

    {#each fields as field}
      <div class="my-2 px-8">
        <label for={field.id} class="block mb-1 roboto-font">{field.label}</label>
          {#if field.type === 'email'}
            <input type="email" id="${field.id}" bind:value={field.value}
            class="w-full rounded border border-gray-300 px-3 py-1 text-lg" />
          {:else if field.type === 'password'}
            <input type="password" id="${field.id}" bind:value={field.value}
            class="w-full rounded border border-gray-300 px-3 py-1 text-lg" />
          {/if}
      </div>
    {/each}

    <div class="submit-container mt-6 mx-auto">
      <button type="submit" class="bg-blue-500 text-white py-2 px-4 rounded roboto-font hover:bg-blue-600 text-lg">
        Enter
      </button>
    </div>
  </form>
{/if}