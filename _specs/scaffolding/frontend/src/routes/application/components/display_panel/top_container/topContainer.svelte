<script>
  import { managerView, fileSelectorView, exportView, interactionView, currentFlow, selectedSpreadsheet, displayLayout } from '@store';
  import WelcomeMessage from './welcomeMessage.svelte';
  import FileManager from './fileManager.svelte';
  import ExportData from './exportData.svelte';
  import DataSourceSelector from './dataSourceSelector.svelte';
  import SimilarTerms from './similarTerms.svelte';
  import SelectScreens from './selectScreens.svelte';
  import VisualizeScreens from './visualizeScreens.svelte';
  import CleanScreens from './cleanScreens.svelte';
  import TransformScreens from './transformScreens.svelte';
  import LoadingLogo from './loadingLogo.svelte';
  import DefaultContent from './stages/defaultContent.svelte';
  import ThoughtProcess from './stages/thoughtProcess.svelte';
</script>

<section class="h-full overflow-y-auto bg-slate-50">
  {#if $fileSelectorView}
    <DataSourceSelector />
  {:else if $selectedSpreadsheet === null}
    <WelcomeMessage />
  {:else if $managerView}
    <FileManager />
  {:else if $exportView}
    <ExportData />
  {:else if $interactionView }
    {#if $currentFlow }
      {#if $currentFlow === 'Detect(typo)'}
        <SimilarTerms />
      {:else if $currentFlow.startsWith('Select') }
        <SelectScreens />
      {:else if $currentFlow.startsWith('Visualize') }
        <VisualizeScreens />
      {:else if $currentFlow.startsWith('Transform') }
        <TransformScreens />
      {:else if $currentFlow.startsWith('Clean') }
        <CleanScreens />
      {:else if $currentFlow === 'Default(thought)' }
        <ThoughtProcess />
      {:else }
        <DefaultContent />
      {/if}
    {:else}
      <LoadingLogo />
    {/if}
  {/if}
</section>

<!-- Connectors is not ready, so we hide the <WalkThrough />
{:else if $chatActive} -->
