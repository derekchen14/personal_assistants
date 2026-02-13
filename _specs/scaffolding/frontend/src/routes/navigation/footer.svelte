<script>
  const currentYear = new Date().getFullYear();
</script>

<footer class="flex justify-between items-center h-8 pb-2 px-4">
  <span class="text-sm text-teal-500/70 sm:text-center dark:text-gray-400 hover:text-teal-500">
    © {currentYear} Soleda, Inc. All rights reserved.
  </span>
  <ul class="flex flex-wrap items-center justify-between mt-3 md:mt-0 
            text-sm text-teal-500/70 dark:text-gray-400">
    <li>
      <a href="/about" class="mr-4 hover:underline md:mr-6 hover:text-teal-500">About Us</a>
    </li>
    <li>
      <a href="mailto:feedback@soleda.ai" class="hover:underline hover:text-teal-500">Contact</a>
    </li>
  </ul>
</footer>
