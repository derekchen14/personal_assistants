<script lang="ts">
  import { Book_Call_URL } from '$lib/constants';
</script>

<!-- Agents Section -->
<section class="relative py-20 bg-cyan-50 text-ink">
  <div class="px-8 md:px-16">
    <div class="max-w-[1280px] mx-auto">
      <h2 class="text-4xl md:text-5xl font-rem mb-16">
        Meet Soleda's agents.
      </h2>

      <!-- Cards Grid -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-16">
        <!-- Dana Card -->
        <div class="bg-white rounded-3xl p-8 flex flex-col gap-4 border-2 border-ink/5">
          <img 
            src="/images/landing/agents-icon-dana.svg"
            alt=""
            class="w-12 h-12"
            aria-hidden="true"
          />
          <h3 class="text-2xl text-ink">Dana</h3>
          <p class="text-sm text-ink">
            The data analyst that handles everything data related from grunt work to complex analysis.<br />
            <a href={Book_Call_URL} target="_blank" rel="noopener noreferrer" class="underline hover:text-gray-600 pt-4 block">Book a demo</a>
          </p>
        </div>

        <!-- Brooke Card -->
        <div class="bg-white rounded-3xl p-8 flex flex-col gap-4 opacity-40 border-2 border-ink/5">
          <img 
            src="/images/landing/agents-icon-redacted.svg"
            alt=""
            class="w-12 h-12"
            aria-hidden="true"
          />
          <h3 class="text-2xl text-ink">Brooke</h3>
          <p class="text-sm text-ink">Coming soon...</p>
        </div>

        <!-- Logan Card -->
        <div class="bg-white rounded-3xl p-8 flex flex-col gap-4 opacity-40 border-2 border-ink/5">
          <img 
            src="/images/landing/agents-icon-redacted.svg"
            alt=""
            class="w-12 h-12"
            aria-hidden="true"
          />
          <h3 class="text-2xl text-ink">Logan</h3>
          <p class="text-sm text-ink">Coming soon...</p>
        </div>
      </div>

      <!-- Vision Text -->
      <div class="max-w-4xl space-y-8">
        <p class="text-gray-600">
          The future of AI goes beyond LLMs and into assistants that are useful, reliable, and trustworthy. Our agents are
          carefully trained to be experts in their domain and equipped with custom tools specifically crafted for each job.
        </p>
        <p class="text-gray-600">
          Want to be part of the revolution? Reach out to us at <a href="mailto:hello@soleda.ai" class="underline hover:text-ink">hello@soleda.ai</a>.
        </p>
      </div>
    </div>
  </div>
</section>
