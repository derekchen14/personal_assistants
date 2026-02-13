<script>
  import { serverUrl } from '@store';
  import { goto } from '$app/navigation';

  let fields = [
    { id: 'first', label: 'First Name', type: 'text', value: '' },
    { id: 'last', label: 'Last Name', type: 'text', value: '' },
    { id: 'email', label: 'Email Address', type: 'email', value: '' },
    { id: 'password', label: 'Password', type: 'password', value: '' },
  ];
  let signupSuccess = false;
  let feedbackMessage = '';

  const handleSignup = async () => {
    feedbackMessage = 'Creating your account, please wait...';

    // Check if all fields are filled
    if (fields.some(field => !field.value)) {
      feedbackMessage = 'Please fill in all the fields.';
      return;
    }
    // Create an object with the field values
    const user = fields.reduce((acc, field) => {
      acc[field.id] = field.value;
      return acc;
    }, {});
    
    // Call the signup function with the user object
    const response = await signup(user);
    if (response.ok) {
      signupSuccess = true;
      feedbackMessage = 'Your account was created successfully!';
      goto('/onboarding');
    } else {
      signupSuccess = false;
      feedbackMessage = 'User already exists. Please try again.';
    }
  };

  const signup = async (user) => {
    // Make a POST request to the backend API for user signup
    const response = await fetch(`${serverUrl}/user/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(user),
    });
    if (response.status === 400) {
      feedbackMessage = 'User already exists';
    }
    const data = await response.json(); // Assuming the response is JSON data, parse it
    return response; // Return the response data to handle it in the calling function
  };
</script>

<svelte:head>
  <title>Soleda: Sign-Up</title>
</svelte:head>
<div class="flex flex-col my-auto mx-auto md:col-6">
  <div class="text-center mb-8">
    <h1 class="text-3xl font-bold text-black mb-2">Welcome to Soleda</h1>
    <p class="text-gray-600">Create your account to get started</p>
  </div>

  <form on:submit|preventDefault={handleSignup}>
    <div class="{signupSuccess ? 'text-green-600' : 'text-cyan-700'} signature-font mb-4 text-xl">
      {#if feedbackMessage}
        <p>{feedbackMessage}</p>
      {/if}
    </div>

    {#each fields as field}
      <div class="my-2 px-8">
        <label for={field.id} class="block mb-1 roboto-font">{field.label}</label>
          {#if field.type === 'text'}
            <input type="text" id="${field.id}" bind:value={field.value}
            class="w-full rounded border border-gray-300 px-3 py-1 text-lg" />
          {:else if field.type === 'email'}
            <input type="email" id="${field.id}" bind:value={field.value}
            class="w-full rounded border border-gray-300 px-3 py-1 text-lg" />
          {:else if field.type === 'password'}
            <input type="password" id="${field.id}" bind:value={field.value}
            class="w-full rounded border border-gray-300 px-3 py-1 text-lg" />
          {/if}
      </div>
    {/each}

    <div class="flex justify-center mt-6">
      <button type="submit" class="bg-blue-500 text-white py-2 px-4 rounded roboto-font hover:bg-blue-600 text-lg">
        Signup
      </button>
    </div>
  </form>
</div>
