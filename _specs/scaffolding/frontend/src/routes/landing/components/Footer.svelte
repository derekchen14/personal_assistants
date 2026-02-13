<script lang="ts">
  const currentYear = new Date().getFullYear();
</script>

<footer class="bg-cyan-50 min-h-14 md:h-14 relative">
  <div class="px-6 md:px-16 h-full py-4 md:py-0">
    <div class="max-w-[1280px] mx-auto flex flex-col md:flex-row md:justify-between items-center 
      h-full text-sm text-slate-600 space-y-2 md:space-y-0">
      <div class="text-center md:text-left">
        © {currentYear} Soleda, Inc. All rights reserved.
      </div>
      <div class="flex justify-center md:justify-end space-x-6">
        <a href="/tos" class="hover:text-teal-700">Terms of Service</a>
        <a href="/privacy" class="hover:text-teal-700">Privacy Policy</a>
        <a href="mailto:support@soleda.ai" class="hover:text-teal-700">Contact</a>
      </div>
    </div>
  </div>
</footer>
