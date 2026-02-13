<script lang="ts">
  import { writable } from 'svelte/store';
  import { clickOutside } from './clickOutside.js';
  import { pickedColumns, activatedItem } from '@store';
  import { displayAlert } from '@alert';

  export let tabColKey = ''
  export let allColors;
  let opened = writable(false);

  // Reactive statement to dynamically construct the Tailwind class
  $: colorClass = $pickedColumns[tabColKey] ? getColorClass($pickedColumns[tabColKey]['color']) : 'bg-gray-300';
  function getColorClass(color) {
    switch (color) {
      case 'sky':     return 'bg-sky-500';
      case 'emerald': return 'bg-emerald-300';
      case 'N/A':     return 'bg-gray-300';
      default:        return `bg-${color}-400`;
    }
  }

  function pickColor(color) {
    let takenColors = Object.values($pickedColumns).map(pc => pc.color);
    if (takenColors.includes(color)) {
      displayAlert('warning', `The ${color} color is already taken. Please choose different one.`);
    } else {
      pickedColumns.update(pc => {  // Written with 'update' function to trigger Svelte reactivity
        pc[tabColKey]['color'] = color; // Update the color for the target column
        return pc;
      });
    }
    activatedItem.set(''); // Reset the activatedItem
    opened.set(false); // Close the dropdown
  };
</script>

<div class="inline-block align-text-top" use:clickOutside={opened}>
  <div on:click={() => opened.update(n => !n)} class="square border-slate-300 cursor-pointer {colorClass}"></div>

  {#if $opened}
  <div class="right-side-dropdown inline-block -mt-5 ml-2 z-10 absolute">
    <div class="side-caret bg-white divide-y divide-gray-100 rounded-sm shadow">
      <div class="p-1 text-sm text-gray-700" aria-labelledby="dropdownDefaultButton">
        <div class="grid grid-cols-3 gap-1">
          {#each allColors as color}
            <div class={`w-4 h-4 z-20 ${getColorClass(color, true)}`}
                on:click={() => pickColor(color)}>  
            </div>
          {/each}
        </div>
      </div>
    </div>
  </div>
  {/if}
</div>

<!-- To prevent Tailwind CSS purging. Do not remove: 
  bg-amber-400 bg-sky-500  bg-emerald-300
  bg-rose-400 bg-violet-400 bg-orange-400
  bg-green-400 bg-cyan-400 bg-fuchsia-400 -->

<style>
  .square {
    display: inline-block;
    position: relative;
    vertical-align: sub;  /* align as a subscript text */
    width: 25px; /* Size of the square */
    height: 25px; /* Size of the square */
    border-width: 1px; /* Border thickness */
  }

  .side-caret {
    position: relative; /* Needed for absolute positioning of the caret */
    border: 1px solid rgb(30, 41, 59);
    border-radius: 4px;
  }

  .side-caret::after {
    content: '';
    position: absolute;
    top: 25px;
    left: -7px;
    width: 12px;
    height: 12px;
    background-color: white;
    transform: rotate(45deg);
    transform-origin: center;
    border-bottom: 1px solid rgb(30, 41, 59); 
    border-left: 1px solid rgb(30, 41, 59); 
  }
</style>
