<script>
  import Carousel from '@lib/carousels/Carousel.svelte';
  import { images } from '@assets/integration/+server.js';
  import { displayAlert } from '@alert';
  let showThumbs = false;
</script>

<div class="max-w-4xl">
  <Carousel {images} {showThumbs} showCaptions={true} />
</div>
