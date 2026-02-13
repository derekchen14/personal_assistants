<script>
  // Panels take care of layout, while the Containers handle the content
  import AgentContainer from './agent_container/agentContainer.svelte';
  import ChatContainer from './chat_container/chatContainer.svelte';
  import InputContainer from './input_container/inputContainer.svelte';
  import { chatActive } from '@store';
</script>

<div class="flex flex-col w-full shadow-md bg-white rounded-md overflow-hidden
  xl:w-[540px] xl:min-w-[540px] lg:w-[480px] lg:min-w-[480px] md:w-96 md:min-w-96 grow-[1] md:grow-1">
  <AgentContainer />
  <ChatContainer />
  <InputContainer />
</div>
