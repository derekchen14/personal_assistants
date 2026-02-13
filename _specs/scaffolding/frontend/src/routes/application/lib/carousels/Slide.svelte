<script>
  export let image = '';
  export let altTag = '';
  export let attr = '';
  export let slideClass = '';
</script>

<div class={slideClass}>
  <img class="custom-image-size" src={image} alt={altTag} title={attr} />
</div>

<style>
  .custom-image-size {
    width: 50%; /* Adjust as needed */
    height: auto; /* Maintains the aspect ratio */
    display: block; /* Centering the image */
    margin: 0 auto; /* Centering the image */
  }
</style>
