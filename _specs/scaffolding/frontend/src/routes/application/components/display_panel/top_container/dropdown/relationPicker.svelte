<script>
  import { writable } from 'svelte/store';
  import { clickOutside } from './clickOutside.js';
  import { createEventDispatcher } from 'svelte';

  import PlusIcon from '@lib/icons/Plus.svelte';
  import MinusIcon from '@lib/icons/Minus.svelte';
  import MultiplyIcon from '@lib/icons/Multiply.svelte';
  import DivideIcon from '@lib/icons/Divide.svelte';
  import FilterIcon from '@lib/icons/Filter.svelte';
  import JoinIcon from '@lib/icons/Join.svelte';
  import GroupIcon from '@lib/icons/Group.svelte';

  export let initialRelation; // Receive the initial relation as a prop
  let opened = writable(false);

  const dispatch = createEventDispatcher();
  const relations = ['+', '-', '*', '/', 'filter', 'join', 'group'];
  const relationMap = {
    '+': { icon: PlusIcon, tooltip: 'Add' },
    '-': { icon: MinusIcon, tooltip: 'Subtract' },
    '*': { icon: MultiplyIcon, tooltip: 'Multiply' },
    '/': { icon: DivideIcon, tooltip: 'Divide' },
    'filter':{ icon: FilterIcon, tooltip: 'Filter By' },
    'join':  { icon: JoinIcon, tooltip: 'Join By' },
    'group': { icon: GroupIcon, tooltip: 'Group By' },
  };

  function selectRelation(relation) {
    dispatch('change', { relation }); // Dispatch an event with the selected relation
    opened.set(false); // Automatically close the dropdown after selection
  }

  $: RelationIcon = relationMap[initialRelation].icon || PlusIcon;
</script>

<div class="inline-block relative mr-0" use:clickOutside={opened}>
  <button on:click={() => opened.update(n => !n)}  class="mx-2 px-2 font-medium bg-white
    border-slate-600 border rounded-md appearance-none dropdown {$opened ? 'dropdown-open' : ''}">
    <span class="inline-flex items-center py-1.5 align-middle relative">
      <svelte:component this={RelationIcon} />
    </span>
  </button>

  {#if $opened}
  <div class="min-w-full z-10 absolute bg-white divide-y divide-gray-100 rounded-md shadow">
    <ul class="py-2 text-sm text-gray-700" aria-labelledby="dropdownDefaultButton">
      {#each relations as rel}
        <li on:click|stopPropagation={() => selectRelation(rel)}>
          <span class="relation-item inline-flex relative items-center px-4 py-1 hover:bg-cyan-100">
            <svelte:component this={relationMap[rel].icon} />
            <span class="tooltip absolute z-10 w-auto p-2 text-center text-zinc-600 bg-white rounded-md shadow-lg
              opacity-0 transition-opacity whitespace-nowrap hover:opacity-100"> {relationMap[rel].tooltip} </span>
          </span>
        </li>
      {/each}
    </ul>
  </div>
  {/if}
</div>

<style>
  .dropdown {
    transition: box-shadow 0.2s ease;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2), 0 1px 2px rgba(0, 0, 0, 0.6);
  }
  .dropdown:hover { /* sky-600 color */
    border-color: rgb(2, 132, 199);
    box-shadow: 0 4px 6px rgba(2, 132, 199, 0.2), 0 1px 2px rgba(2, 132, 199, 0.6);
  }
  .dropdown-open {
    box-shadow: inset 0 1px 3px rgba(0, 0, 0, 1);
  }
  .tooltip {
    left: 90%;
    top: 50%;
    transform: translate(10px, -50%);
    transition: visibility 0s, opacity 0.3s linear;
  }
  .relation-item:hover .tooltip {
    opacity: 1; /* Become fully visible on hover */
  }
</style>