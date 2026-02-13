<script>
  import BalanceIcon from '@lib/icons/merge/Balance.svelte'
  import CalendarIcon from '@lib/icons/merge/Calendar.svelte'
  import KeyboardIcon from '@lib/icons/merge/Keyboard.svelte'
  import SubstringIcon from '@lib/icons/merge/Substring.svelte'
  import PlusInSquare from '@lib/icons/merge/PlusInSquare.svelte'
  import MinusInSquare from '@lib/icons/merge/MinusInSquare.svelte'
  import TimesIcon from '@lib/icons/merge/Times.svelte'
  import DividerIcon from '@lib/icons/merge/Divider.svelte'
  import SortIcon from '@lib/icons/merge/Sort.svelte'
  import RulerIcon from '@lib/icons/merge/Ruler.svelte'
  import SignPostIcon from '@lib/icons/merge/SignPost.svelte'
  import HalfStarIcon from '@lib/icons/merge/HalfStar.svelte'
  import CommaIcon from '@lib/icons/merge/Comma.svelte'
  import SpaceIcon from '@lib/icons/merge/Space.svelte'
  import PeriodIcon from '@lib/icons/merge/Period.svelte'
  import ComparisonIcon from '@lib/icons/merge/Comparison.svelte'
  import UnderscoreIcon from '@lib/icons/merge/Underscore.svelte'
  import ConcatIcon from '@lib/icons/merge/Concatenate.svelte'
  import SquareRootIcon from '@lib/icons/merge/SquareRoot.svelte'
  import SuperScriptIcon from '@lib/icons/merge/SuperScript.svelte'
  
  import QuestionIcon from '@lib/icons/Question.svelte'
  import Placeholder from '@lib/icons/Placeholder.svelte'
  import AutomaticIcon from '@lib/icons/Automatic.svelte'
  import ManualIcon from '@lib/icons/Manual.svelte'
  import { createEventDispatcher } from 'svelte';

  export let name;
  export let icon;
  export let title;
  export let example;
  export let styleType;
  export let chosenStyle;
  export let customClass = 'px-2';
  export let choices = {}; // there are exactly 2 choices

  const mergeStyleIcons = { 'placeholder': Placeholder, 'automatic': AutomaticIcon, 'manual': ManualIcon,
    'balance': BalanceIcon, 'calendar': CalendarIcon, 'keyboard': KeyboardIcon, 'substring': SubstringIcon,
    'plus': PlusInSquare, 'minus': MinusInSquare, 'times': TimesIcon, 'divider': DividerIcon, 'sort': SortIcon,
    'ruler': RulerIcon, 'halfstar': HalfStarIcon, 'signpost': SignPostIcon, 'question': QuestionIcon,
    'space': SpaceIcon, 'period': PeriodIcon, 'comparison': ComparisonIcon, 'underscore': UnderscoreIcon, 
    'concat': ConcatIcon, 'comma': CommaIcon, 'squareroot': SquareRootIcon, 'superscript': SuperScriptIcon
  };

  let chosen = Object.keys(choices)[0];
  let inputValue = ''; // For input box
  let StyleIcon; // imported icon component
  const dispatch = createEventDispatcher();

  function choosePriority() {
    let priority = 'N/A';

    if (styleType.startsWith('radio')) {
      priority = chosen;
    } else if (styleType === 'input_box') {
      priority = inputValue;
    }
    dispatch('update', { name: name, setting: priority });
  }

  function chooseStyle() {
    if (chosen !== 'description') {
      dispatch('update', { name: name, setting: chosen });
    } else {
      dispatch('update', { name: name, setting: '' });
    }
  }
</script>

<div on:click={chooseStyle} class="{customClass} text-center text-sm rounded-lg border-4 pb-2
    {chosenStyle.name === name ? 'border-teal-400' : 'border-transparent'}">

  <h3 class="underline font-medium text-base cursor-pointer -mb-0.5">{title}</h3>
  <div class="flex flex-col items-center cursor-pointer">
    <svelte:component this={mergeStyleIcons[icon]} selected={chosenStyle.name === name} />
    {#if styleType.startsWith('desc') || styleType === 'input_box'}
      <p class="leading-none mb-1">{choices['description']}</p>
    {:else}
      <p class="leading-none mb-1">{choices[chosen]}</p> 
    {/if}
  </div>

  {#if styleType.endsWith('exp')}
    <p><span class="italic">Example:</span> {example}</p>
  {/if}

  {#if styleType.startsWith('radio')}
    {#each Object.keys(choices) as choice}
      <label class="choices mr-3">
        <input type="radio" name={`styleChoice-${name}`} bind:group={chosen} value={choice}
          on:change={choosePriority} /> {choice}
      </label>
    {/each}

  {:else if styleType === 'input_box'}
    {choices['input box']}
    <input type="text" class="w-1/2 px-1 py-0"
        bind:value={inputValue} on:change={choosePriority} />
  {/if}

</div>