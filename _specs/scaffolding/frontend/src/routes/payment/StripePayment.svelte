<script>
  import { onMount, onDestroy } from 'svelte';
  import { logger } from '$lib/logger';

  // Add prop for planType with default value
  export let planType = 'basic';

  let checkoutElement;
  let stripeCheckout;

  onMount(async () => {
    // Load Stripe.js dynamically. This is a publishable key.
    const stripe = await loadStripe('pk_live_51RBIu7J0BU0orn1IZnJg1Q9QIZrVfOpjMeUQGkObsyoZQYrmJwu15YAIYv9UxRbJKpveqnLyh5Cid4GNPURipy9w00kaT0HMLa');

    // Create a function to fetch the client secret from your backend
    const fetchClientSecret = async () => {
      console.log('fetching client secret');
      console.log(planType);
      const response = await fetch('/api/payments/create-checkout-session', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        // Add planType to the request body
        body: JSON.stringify({ planType })
      });

      if (!response.ok) {
        const errorData = await response.json();
        logger.error('stripe_secret_fetch_failure', 'Payment', {
          error: {
            error_message: errorData.detail,
            browser: navigator.userAgent,
          },
      });  
        throw new Error(errorData.error?.message || 'Failed to create checkout session');
      }

      const { client_secret } = await response.json();
      return client_secret;
    };

    // Initialize the embedded checkout
    try {
      const stripeCheckout = await stripe.initEmbeddedCheckout({
        fetchClientSecret
      });
      
      stripeCheckout.mount(checkoutElement);
    } catch (error) {
      logger.error('stripe_checkout_init_failure', 'Payment', {
        error: {
          error_message: error,
          browser: navigator.userAgent,
        },
      });
      console.error('Error initializing checkout:', error);   
    }
  });

  onDestroy(() => {
    // Clean up on component destruction
    if (stripeCheckout) {
      stripeCheckout.unmount();
    }
  });

  // Helper function to load Stripe.js
  async function loadStripe(key) {
    // Return existing Stripe instance if it exists
    if (window.Stripe) {
      return window.Stripe(key);
    }

    // Otherwise load the script and create a new instance
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://js.stripe.com/v3/';
      script.onload = () => resolve(window.Stripe(key));
      script.onerror = () => reject(new Error('Failed to load Stripe.js'));
      document.head.appendChild(script);
    });
  }
</script>

<svelte:head>
  <title>Checkout - Pay with Stripe</title>
  <meta name="description" content="Complete your payment securely with Stripe" />
</svelte:head>

<div class="container">
  <h1></h1>
  
  <!-- Checkout will insert the payment form here -->
  <div bind:this={checkoutElement} id="checkout"></div>
</div>

<style>
  .container {
    max-width: 800px;
    margin: 0 auto;
    padding: 2rem 1rem;
  }

  h1 {
    margin-bottom: 2rem;
    font-size: 1.5rem;
  }

  #checkout {
    width: 100%;
    min-height: 400px;
    border-radius: 4px;
  }
</style>