<script>
  import { serverUrl } from '@store';
  import { goto } from '$app/navigation';
  import howToReset from '@assets/how_to_reset.png';
  import { v4 as uuidv4 } from 'uuid';
  import { logger } from '$lib/logger';
  
  let fields = [
    { id: 'email', label: 'Email Address', type: 'email', value: '' },
    { id: 'password', label: 'Password', type: 'password', value: '' },
  ];
  let loginSuccess = false;
  let feedbackMessage = '';

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
      credentials: 'include',
    });
    if (response.status === 400) {
      feedbackMessage = 'User not found';
    }

    const json = await response.json()
    const isSuccess = json?.success;
    if (isSuccess == true) {
      const userID = json?.user?.userID;
      // Set new session and user ID
      const sessionID = `sess-${uuidv4().substring(0, 8)}`;
      logger.setSessionID(sessionID);
      logger.setUserID(userID);

      console.log('User logged in successfully');
    } else {
      console.log('logged in user, did not get access token');
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

        logger.info('user_login_success', 'UserLogin');

        goto('/application');
      } else {
        loginSuccess = false;
        feedbackMessage = 'Incorrect email and password.';

        logger.warning('invalid_credentials', 'UserLogin', {
          email: email,
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
  <title>Soleda: Onboarding</title>
</svelte:head>

<h1 class="text-2xl font-bold mb-6 md:text-center">Welcome to the world of AI Agents!</h1>

<div class="flex flex-col my-auto mx-auto md:col-6 mb-2 items-center max-w-screen-md">
  <p>To get fully set-up, please select a time here:
    <a href="https://calendar.app.google/uf63qjFgkYxJW5NB8" class="underline font-bold text-cyan-600">Onboarding Calendar</a>
  </p>
  <p>In the meantime, feel free to try it out by using a sample dataset or by uploading a CSV file.
    Dana understands anything related to marketing analytics, but is still learning. 
    When things don't work, you can reset the conversation.
  </p>
  <img src={howToReset} alt="How to Reset Chat" />
    
  <p class="text-center mt-6">Please enter your email and password to continue.</p>
</div>

<form on:submit|preventDefault={handleLogin} class="flex flex-col my-auto mx-auto md:col-6">
  <div class="{loginSuccess ? 'text-green-600' : 'text-cyan-700'} signature-font mb-4 text-xl">
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
