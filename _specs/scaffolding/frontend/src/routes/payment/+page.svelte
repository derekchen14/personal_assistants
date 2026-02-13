<script>
  import StripePayment from './StripePayment.svelte';

  // You can extract any query parameters if needed
  // const referrer = $page.url.searchParams.get('ref');
</script>

<svelte:head>
  <title>Basic Plan - Subscribe</title>
  <meta name="description" content="Subscribe to our Basic plan and start analyzing your data today." />
</svelte:head>

<StripePayment planType="basic" />