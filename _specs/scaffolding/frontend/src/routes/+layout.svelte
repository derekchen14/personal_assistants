<script>
  import { page } from '$app/stores';
  import Header from './navigation/header.svelte';
  import AppHeader from './navigation/app_header.svelte';
  import Footer from './navigation/footer.svelte';
  import Analytics from './application/Analytics.svelte';
  import '../app.css';
</script>

<Analytics />
<div class="flex flex-col min-h-screen bg-repeat background">
  {#if $page.url.pathname.includes('/application')}
    <AppHeader />
  {:else if !$page.url.pathname.includes('/dashboard')}
    <Header />
  {/if}
  <main class="flex flex-col flex-grow">
    <slot />
  </main>
  {#if $page.url.pathname.includes('/application')}
    <Footer />
  {/if}
</div>

<style>
  .background {
    background-image: url('../assets/dana_background.png');
  }
</style>