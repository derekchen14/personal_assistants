<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  
  // Props
  export let content = {
    imageSrc: '',
    altText: 'Uploaded image'
  };
  
  // State variables
  let isUploading = false;
  let fileInput;
  let dragOver = false;
  
  // Event dispatcher
  const dispatch = createEventDispatcher();
  
  // Trigger file selector
  function openFileSelector() {
    if (fileInput) {
      fileInput.click();
    }
  }
  
  // Handle file upload from input
  function handleFileSelected(event) {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    uploadFile(files[0]);
  }
  
  // Upload and process the file
  function uploadFile(file) {
    if (!file || !file.type.startsWith('image/')) {
      // Not an image file
      return;
    }
    
    isUploading = true;
    const reader = new FileReader();
    
    reader.onload = (e) => {
      const imageSrc = e.target.result;
      
      // Update content with new image
      const updatedContent = {
        ...content,
        imageSrc,
        altText: file.name || 'Uploaded image'
      };
      
      dispatch('update', updatedContent);
      isUploading = false;
      
      // Reset file input
      if (fileInput) {
        fileInput.value = '';
      }
    };
    
    reader.onerror = () => {
      isUploading = false;
      // Could add error handling here
      
      // Reset file input
      if (fileInput) {
        fileInput.value = '';
      }
    };
    
    reader.readAsDataURL(file);
  }
  
  // Handle drag enter
  function handleDragEnter(event) {
    event.preventDefault();
    event.stopPropagation();
    dragOver = true;
  }
  
  // Handle drag over
  function handleDragOver(event) {
    event.preventDefault();
    event.stopPropagation();
    dragOver = true;
  }
  
  // Handle drag leave
  function handleDragLeave(event) {
    event.preventDefault();
    event.stopPropagation();
    dragOver = false;
  }
  
  // Handle drop
  function handleDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    dragOver = false;
    
    const files = event.dataTransfer.files;
    if (!files || files.length === 0) return;
    
    uploadFile(files[0]);
  }
</script>

<div 
  class="uploaded-file-container"
  on:dragenter={handleDragEnter}
  on:dragover={handleDragOver}
  on:dragleave={handleDragLeave}
  on:drop={handleDrop}
  class:drag-over={dragOver}
>
  <!-- Hidden file input -->
  <input 
    type="file" 
    accept="image/*" 
    class="hidden-input" 
    bind:this={fileInput} 
    on:change={handleFileSelected}
  />
  
  {#if isUploading}
    <!-- Loading state -->
    <div class="upload-loading">
      <div class="spinner"></div>
      <span>Uploading...</span>
    </div>
  {:else if content.imageSrc}
    <!-- Image preview -->
    <div class="image-container">
      <img 
        src={content.imageSrc} 
        alt={content.altText} 
        class="image-preview"
      />
      
      <button 
        class="replace-btn" 
        on:click={openFileSelector}
      >
        Replace
      </button>
    </div>
  {:else}
    <!-- Upload prompt -->
    <div class="upload-prompt" on:click={openFileSelector}>
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="upload-icon">
        <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
      </svg>
      
      <div class="upload-text">
        <p class="primary-text">Click to upload</p>
        <p class="secondary-text">or drag and drop</p>
        <p class="file-types">PNG, JPG, GIF up to 10MB</p>
      </div>
    </div>
  {/if}
</div>

<style>
  .uploaded-file-container {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    background-color: white;
    border-radius: 0.375rem;
    overflow: hidden;
    position: relative;
  }
  
  .hidden-input {
    display: none;
  }
  
  .upload-prompt {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 16px;
    border: 2px dashed #d1d5db;
    border-radius: 0.375rem;
    width: 90%;
    height: 90%;
    cursor: pointer;
    transition: all 0.2s ease;
  }
  
  .upload-prompt:hover {
    border-color: #9ca3af;
    background-color: #f9fafb;
  }
  
  .upload-icon {
    width: 32px;
    height: 32px;
    color: #6b7280;
  }
  
  .upload-text {
    text-align: center;
  }
  
  .primary-text {
    font-size: 0.875rem;
    font-weight: 500;
    color: #374151;
    margin: 0;
  }
  
  .secondary-text {
    font-size: 0.875rem;
    color: #4b5563;
    margin: 0;
  }
  
  .file-types {
    font-size: 0.75rem;
    color: #6b7280;
    margin: 4px 0 0 0;
  }
  
  .uploaded-file-container.drag-over .upload-prompt {
    border-color: #3b82f6;
    background-color: rgba(59, 130, 246, 0.05);
  }
  
  .upload-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
  }
  
  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid #e5e7eb;
    border-top-color: #3b82f6;
    border-radius: 50%;
    animation: spinner 0.8s linear infinite;
  }
  
  @keyframes spinner {
    to {
      transform: rotate(360deg);
    }
  }
  
  .image-container {
    width: 100%;
    height: 100%;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  .image-preview {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
  }
  
  .replace-btn {
    position: absolute;
    bottom: 8px;
    right: 8px;
    padding: 4px 8px;
    background-color: rgba(255, 255, 255, 0.8);
    border: 1px solid #d1d5db;
    border-radius: 4px;
    font-size: 0.75rem;
    color: #4b5563;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.2s ease;
  }
  
  .image-container:hover .replace-btn {
    opacity: 1;
  }
</style>