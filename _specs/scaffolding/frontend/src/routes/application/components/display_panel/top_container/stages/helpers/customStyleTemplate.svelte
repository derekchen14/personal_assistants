<script>
  import CodeIcon from '@lib/icons/merge/Code.svelte'
  import Placeholder from '@lib/icons/Placeholder.svelte'
  import { createEventDispatcher } from 'svelte';
  import { displayAlert } from '@alert';

  export let name;
  export let title;
  export let chosenStyle;
  let inputValue = ''; // For input box
  const dispatch = createEventDispatcher();

  function chooseStyle() {
    if (inputValue.length > 64) {         
      displayAlert('warning', 'Your code input is too long, please trim it down before submitting.');
    } else {

      console.log("custom", inputValue);
      dispatch('update', { name: name, setting: inputValue });
    }
  }
</script>

<div on:click={chooseStyle} class="col-span-3 px-4 py-2 text-sm rounded-lg border-4 cursor-pointer
  {chosenStyle.name === name ? 'border-teal-400' : 'border-transparent'}">
  
  {#if name === 'customText'}
    <h3 class="underline font-medium text-base text-center">Custom Text Format</h3>

    <div class="grid grid-cols-3 gap-2 text-sm">
      <p class="mt-1">Use column variables as A, B, C to create your own customized format.
      Total length of input must be 64 characters or less. See examples on the right for details.</p>

      <div class="flex flex-col items-center">
        <CodeIcon selected={chosenStyle.name === name}/>
        <div class="input-box flex items-center justify-center space-x-2">
          <span>Format:</span>
          <input type="text" class="w-3/5 p-1" placeholder="A, B" bind:value={inputValue} on:change={chooseStyle}/>
        </div>
      </div>

      <div class="flex flex-col">
        <p class="italic">Examples</p>
        <ul class="list-disc list-inside pl-2">
          <li>A, B => Los Angeles, CA</li>
          <li>(A) B-C => (650) 934-1566</li>
          <li>A / C / B => 07/04/2023</li>
          <li>B, A => Smith, John</li>
        </ul>
      </div>
    </div>

  {:else if name == 'customNumber'}
    <h3 class="underline font-medium text-base text-center">Custom Python Formula</h3>

    <div class="grid grid-cols-3 gap-2 text-sm">
      <p class="mt-1">Use column variables as A, B, C to write your own custom code for combining content.
      Total length of input must be 64 characters or less. See examples for details.</p>

      <div class="flex flex-col items-center">
        <CodeIcon selected={chosenStyle.name === name}/>
        <div class="input-box flex items-center justify-center space-x-2">
          <span>Code:</span>
          <input type="text" class="w-3/5 p-1" placeholder="Enter formula" bind:value={inputValue} on:change={chooseStyle}/>
        </div>
      </div>

      <div class="flex flex-col">
        <p class="italic">Examples</p>
        <ul class="list-disc list-inside pl-2">
          <li>A * C * (1 + B)</li>
          <li>A if B > 0 else 20</li>
          <li>B * math.pow((1 + A), C)</li>
          <li>(A / B) * 100</li>
        </ul>
      </div>
    </div>

  {/if}
</div>