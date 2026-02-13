<script>
  import { chatActive, selectedTable, activeConnector, oauthSuccess, tableView } from '@store';
  import SheetTabs from './table_section/tabs.svelte';
  import SheetContent from './table_section/content.svelte';
  import UploadFile from './connectors/uploadFile.svelte';
  import ConnectData from './connectors/connectData.svelte';
  import LoadProgress from './loadProgress.svelte';

  // Reset view state when showing upload
  // TODO: Figure out what we want to do with the view state
  $: if ($activeConnector !== null) {
    tableView.set(null);
  }
</script>

<section class="bg-slate-50 w-full h-full overflow-auto">
  {#if $activeConnector === 'upload'}
    <UploadFile />
  {:else if $oauthSuccess}
    <ConnectData />
  {:else if $chatActive}
    <SheetContent />
  {:else}
    <LoadProgress />
  {/if}
</section>
{#if $chatActive}
  <SheetTabs />
{/if}
