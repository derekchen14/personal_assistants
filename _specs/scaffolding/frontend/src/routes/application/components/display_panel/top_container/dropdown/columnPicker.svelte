<script>
  import { writable } from 'svelte/store';
  import { clickOutside } from './clickOutside.js';
  import { createEventDispatcher } from 'svelte';
  import { pickedColumns } from '@store';

  export let columns = [];
  export let clause;
  let showMore = writable(false)
  const dispatch = createEventDispatcher();

  function selectColumn(colItem) {
    if (colItem === 'Show More ...') {
      showMore.set(true);
    } else {
      // Remove the previous tabCol item
      let prevTabCol = `${clause.tab}.${clause.col}`;
      pickedColumns.update(pc => {
        pc[prevTabCol]['count'] === 1 ? delete pc[prevTabCol] : pc[prevTabCol]['count'] -= 1;
        return pc;
      });
      dispatch('select', { colItem });
    }
  }

  $: columnMenuItems = $showMore ? columns : [...columns.slice(0, 3), 'Show More ...'];
</script>

<div class="min-w-full z-20 absolute bg-white divide-y divide-gray-100 rounded-md shadow">
  <ul class="py-2 text-sm text-gray-700 dark:text-gray-200" aria-labelledby="dropdownDefaultButton">
    {#each columnMenuItems as colItem}
    <li on:click|stopPropagation={() => selectColumn(colItem)}>
      <span class="{colItem === 'Show More ...' ? 'border-t border-t-zinc-600' : ''}
        whitespace-nowrap block px-4 py-1 hover:bg-cyan-100">
        {colItem}
      </span>
    </li>
    {/each}
  </ul>
</div>