<script lang="ts">
  import { displayAlert } from '@alert';
  import { serverUrl, tableView, chatActive, displayLayout, activeConnector, availableSheets } from '@store';
  import { selectedSpreadsheet, selectedTable, initializeSheetData, initializeSocket, updateTabProperties } from '@store';
  import { securedFetch } from '$lib/apiUtils';
  import { extensionToMIME, prepareTableName, preprocessCSV, trimLargeCSV } from '$lib/fileUtils';
  import Dropzone from 'svelte-file-dropzone/Dropzone.svelte';
  import { read as xlsx_read } from 'xlsx';
  import { logger } from '$lib/logger';

  const MAX_FILE_SIZE = 32;  // in MB
  const MIN_TABLE_NAME_LENGTH = 3;
  const MAX_TABLE_NAME_LENGTH = 32;
  const MAX_SPREADSHEET_NAME_LENGTH = 64;
  const DEFAULT_METADATA = {
    name: 'Marketing Analytics',
    description: 'Cleaning or analyzing marketing data to understand user behavior'
  };

  let files = [];
  let tableNames = [];
  let globalExtension = null;
  let isDragging = false;
  let emptyFile = true;
  let isLoading = false;
  let [ssName, description] = [DEFAULT_METADATA.name, DEFAULT_METADATA.description];
  let isMultiTabFile = false;

  function isValidFileSize(file) {
    const fileSizeMB = file.size / (1024 * 1024);
    return fileSizeMB <= MAX_FILE_SIZE;
  }

  function validateFileType(file) {
    const segments = file.name.split('.');
    const extension = segments.pop()?.toLowerCase() || '';
    const expectedMimeType = extensionToMIME(extension);
    
    if (!expectedMimeType) {
      throw new Error(`Unsupported file type: ${extension}`);
    }
    // Note: Some browsers may report different but valid MIME types
    // So we're being less strict here while still maintaining security
    if (!file.type.includes(extension)) {
      console.warn(`File MIME type (${file.type}) may not match extension (${extension})`);
    }
    
    return extension;
  }

  async function checkFileValidity(acceptedFiles) {
    if (!acceptedFiles.length) {
      throw new Error('No files provided for validation');
    }

    // Validate file sizes
    const oversizedFiles = acceptedFiles.filter(file => !isValidFileSize(file));
    if (oversizedFiles.length > 0) {
      throw new Error(
        `Following files exceed ${MAX_FILE_SIZE}MB limit: ${oversizedFiles.map(f => f.name).join(', ')}`
      );
    }

    // Validate and get extensions
    const extensions = acceptedFiles.map(file => validateFileType(file));
    const uniqueExtensions = new Set(extensions);

    if (uniqueExtensions.size > 1) {
      throw new Error(
        `All files must have the same type. Found: ${Array.from(uniqueExtensions).join(', ')}`
      );
    }

    return extensions[0];
  }

  async function processFile(file) {
    let cleanedFile = file;
    if (file.name.toLowerCase().endsWith('.csv')) {
      try {
        let parsedData = await preprocessCSV(file);
        if (file.size / (1024 * 1024) > MAX_FILE_SIZE) {
          parsedData = await trimLargeCSV(parsedData, MAX_FILE_SIZE);
        }
        // Create new file with cleaned content
        cleanedFile = new File([parsedData], file.name, {
          type: 'text/csv',
          lastModified: file.lastModified || Date.now(),
        });
      } catch (err) {
        console.error('Error preprocessing CSV:', err);
      }
    }
    return cleanedFile;
  }

  async function handleFileUpload(event) {
    isDragging = false;
    isLoading = true;
    const { acceptedFiles, rejectedFiles } = event.detail;

    try {
      if (!Array.isArray(acceptedFiles) || acceptedFiles.length === 0) {
        throw new Error('No valid files detected for upload.');
      }

      // Process files and validate
      const processedFiles = await Promise.all(acceptedFiles.map(processFile));
      globalExtension = await checkFileValidity(processedFiles);
      
      // Handle multi-tab Excel/ODS files
      if (globalExtension === 'xlsx' || globalExtension === 'ods') {
        if (processedFiles.length > 1) {
          throw new Error('Dana can handle one multi-tab Excel file or multiple single-tab files, but not both.');
        }
        isMultiTabFile = true;
        
        // Read all sheets from the Excel file
        const arrayBuffer = await processedFiles[0].arrayBuffer();
        const workbook = xlsx_read(arrayBuffer, { type: 'array' });
        const allSheets = workbook.SheetNames;
        
        // Generate table names from all sheets
        if (allSheets.length === 1) {
          // For single-tab Excel files, use the filename without extension instead of sheet name
          tableNames = [
            prepareTableName(processedFiles[0].name.split('.').slice(0, -1))
          ];
        } else {
          // For multi-tab Excel files, use sheet names
          tableNames = allSheets.map(sheetName => (
            prepareTableName([sheetName])
          ));
        }
      } else {
        // Regular file handling for non-Excel files
        tableNames = processedFiles.map(file => (
          prepareTableName(file.name.split('.').slice(0, -1))
        ));
      }
      
      // Ensure unique names regardless of file type
      const uniqueNames = new Set();
      tableNames = tableNames.map((tabName) => {
        let counter = 1;
        
        while (uniqueNames.has(tabName)) {
          tabName = `${tabName}_${counter}`;
          counter++;
        }
        uniqueNames.add(tabName);
        return tabName;
      });

      // Get column headers from files
      const tables = {};
      for (let i = 0; i < processedFiles.length; i++) {
        const file = processedFiles[i];
        const tabName = tableNames[i];
        
        if (file.name.toLowerCase().endsWith('.csv')) {
          const text = await file.text();
          const headers = text.split('\n')[0].split(',').map(h => h.trim());
          tables[tabName] = headers;
        } else if (file.name.toLowerCase().endsWith('.xlsx') || file.name.toLowerCase().endsWith('.ods')) {
          const arrayBuffer = await file.arrayBuffer();
          const workbook = xlsx_read(arrayBuffer, { type: 'array' });
          const sheet = workbook.Sheets[workbook.SheetNames[0]];
          const headers = Object.keys(sheet).filter(key => key.match(/^[A-Z]+1$/))
            .map(key => sheet[key].v);
          tables[tabName] = headers;
        }
      }
      // Generate metadata using LLM
      // const response = await securedFetch(`${serverUrl}/sheets/generate-metadata`, {
      //   method: 'POST',
      //   headers: {
      //     'Content-Type': 'application/json',
      //   },
      //   body: JSON.stringify(tables),
      // });

      // if (response.ok) {
      //   const metadata = await response.json();
      //   ssName = metadata.name?.trim() ? metadata.name : DEFAULT_METADATA.name;
      //   description = metadata.description?.trim() ? metadata.description : DEFAULT_METADATA.description;
      // } else {
      //   console.warn('Failed to generate metadata, using defaults');
      // }
      files = processedFiles;
      emptyFile = false;
    } catch (error) {
      console.error('File upload error:', error);
      displayAlert('error', error.message);
      cancelUpload();
    } finally {
      isLoading = false;
    }
  }

  async function cancelUpload() {
    files = [];
    tableNames = [];
    emptyFile = true;
    isMultiTabFile = false;
    displayAlert('warning', 'File upload has been canceled.');
  }

  function initSheetMetadata() {
    const tabNames = tableNames.map(tabName => {
      const sanitizedName = tabName.replace(/ /g, '_');
      return ['select', 'from', 'where'].includes(sanitizedName) 
        ? `${sanitizedName}_tbl` 
        : sanitizedName;
    });

    // Validate table names
    const invalidNames = tabNames.filter(
      name => name.length < MIN_TABLE_NAME_LENGTH || name.length > MAX_TABLE_NAME_LENGTH
    );
    
    if (invalidNames.length > 0) {
      displayAlert('warning', 
        `Table names must be between ${MIN_TABLE_NAME_LENGTH} and ${MAX_TABLE_NAME_LENGTH} characters: ${invalidNames.join(', ')}`
      );
      return [null, true];
    }

    return [{
      ssName: ssName.slice(0, MAX_SPREADSHEET_NAME_LENGTH),
      tabNames,
    }, false];
  }

  async function submitForUpload() {
    let [ssMetadata, hitError] = initSheetMetadata();
    if (hitError) return;

    const socketConnection = await initializeSocket();
    if (socketConnection) {
      selectedSpreadsheet.set(ssMetadata);
      $activeConnector = null;
      $displayLayout = 'bottom';
    } else {
      let error_msg = 'Failed to load spreadsheet due to socket connection issue.';
      displayAlert('error', error_msg);
      logger.error('file_upload_failure', 'UploadFile', {
        error: {
          error_type: 'client_error',
          error_code: 'SOCKET_CONNECTION_ERROR',
          error_message: error_msg,
          browser: navigator.userAgent,
        },
      });
      return;
    }

    try {
      // Store properties received from server before initializing sheet data
      let schemaProperties = {};
      
      for (let index = 0; index < files.length; index++) {
        const tab = ssMetadata.tabNames[index];
        const sheetDetails = {
          ssName,
          tab,
          description,
          globalExtension
        };
        const response = await uploadFile(files[index], tab, index, tableNames.length, sheetDetails);
        
        if (response && response.properties) {
          Object.entries(response.properties).forEach(([tabName, schema]) => {
            schemaProperties[tabName] = schema;
          });
        }
      }
      
      availableSheets.update((currentSheets) => [...currentSheets, ssMetadata]);
      
      initializeSheetData(ssMetadata.tabNames);
      Object.entries(schemaProperties).forEach(([tabName, schema]) => {
        updateTabProperties(tabName, schema);
      });
      
      selectedTable.set(ssMetadata.tabNames[0]);
    } catch (error) {
      selectedSpreadsheet.set(null);
      $activeConnector = 'upload';
      $displayLayout = 'split';

      if (error.isWarning) {
        displayAlert('warning', error.message);
        logger.warning('file_upload_failure', 'UploadFile', {
          message: error.message,
        });
      } else {
        console.error(error);
        displayAlert('error', 'There was an error uploading your file. Please try again later.');
        logger.error('file_upload_failure', 'UploadFile', {
          error: {
            error_type: 'client_error',
            error_code: error.code || 'UNKNOWN_ERROR',
            error_message: error.message || "Unknown error in file upload",
            browser: navigator.userAgent,
          },
        });
      }
    } finally {
      emptyFile = true;
    }
  }

  async function uploadFile(file, tab, index, total, sheetInfo) {
    const formData = new FormData();
    // file.lastModified, file.size and file.lastModifiedDate are also available
    formData.append('file', file, file.name);
    if (isMultiTabFile) {   // rather than a single tab, we send over all table names at once
      formData.append('sheetInfo', JSON.stringify({ ssName, tableNames, description, globalExtension }));
      formData.append('position', JSON.stringify({ index: -1, total }));  // use negative index to indicate multi-tab
    } else {
      formData.append('sheetInfo', JSON.stringify(sheetInfo));
      formData.append('position', JSON.stringify({ index, total }));
    }

    const response = await securedFetch(`${serverUrl}/sheets/upload`, {
      method: 'POST',
      body: formData,
    });

    
    if (response.ok) {
      const info = await response.json();
      if (info['done']) {
        // We won't update properties directly here anymore
        // Instead we'll return the info to be processed after all uploads
        tableView.set(info['table']);
        chatActive.set(true);
        return info;
      }
      return null;
    } else {
      const errorData = await response.json();
      console.error(`HTTP error (status ${response.status}): ${errorData.detail}`);
      throw { message: errorData.detail, isWarning: true };
    }
  }

</script>

{#if emptyFile}
  <div id="file-uploader" class="w-full h-full rounded-md py-8 px-10 flex">
    {#if isLoading}
      <div class="flex flex-col items-center justify-center w-full h-full">
        <div class="animate-spin rounded-full h-16 w-16 border-b-2 border-teal-500 mb-4"></div>
        <p class="text-gray-600">Processing your files...</p>
      </div>
    {:else}
      <Dropzone
        on:drop={handleFileUpload}
        name="csvUpload"
        accept=".csv, .tsv, .xlsx, .ods"
        required
        disableDefaultStyles
        inputElement={null}
        on:dragenter={() => { isDragging = true; }}
        on:dragleave={() => { isDragging = false; }}
        containerClasses="flex h-full w-full items-center justify-center rounded-md border-2 border border-dashed
        {isDragging ? 'bg-gradient-to-br from-teal-100 to-cyan-200 border-gray-400' : 'bg-gray-100 border-gray-300'}"
      >
        <div class="justify-center items-center text-center text-gray-500 p-3 align-middle m-1 lg:m-2">
          <svg xmlns="http://www.w3.org/2000/svg"  fill="white" viewBox="0 0 24 24"
            stroke-width="1.4" stroke="currentColor" class="m-auto w-14 h-14">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 
              4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z"/>
          </svg>
          <p class="m-1 mt-3 font-bold">Drag & drop to upload</p>
          <p class="m-3 text-sm">— OR —</p>
          <button class="m-1 mb-3 bg-teal-500 hover:bg-teal-600 text-white font-bold py-2 px-4 rounded">
            Click to browse
          </button>
        </div>
      </Dropzone>
    {/if}
  </div>
{:else}
  <div class="text-slate-800 w-full h-full py-8 px-10">
    <p class="font-medium text-xl mb-2">Spreadsheet Details</p>
    <p class="my-2">
      Enter a title for your spreadsheet and a short description of what you hope to accomplish.
      Also, review the table names and edit as necessary. Then scroll down to submit your
      information. Keep in mind that the more specific you are, the more likely Dana will be able to
      help.
    </p>
    <div id="ss-details-form" class="my-2 pb-4 text-md">
      <form on:submit|preventDefault={submitForUpload}>
        <div class="grid grid-cols-2 gap-4">
          <!-- left side  -->
          <div>
            <div class="form-title my-2 flex items-center">
              <label for="title" class="pr-1 mr-14">Title:</label>
              <input type="text" id="title" name="title" bind:value={ssName}
                class="rounded border-gray-300 text-sm px-2 py-1 w-full" required/>
            </div>

            <div class="form-desc my-2 flex items-center">
              <label for="description" class="mr-2">Description:</label>
              <textarea id="description" name="description" bind:value={description}
              class="rounded border-gray-300 p-2 text-sm min-h-16 placeholder:italic placeholder-slate-300 w-full"
              placeholder="I want to ..." required></textarea>
            </div>
          </div>

          <!-- right side  -->
          <div class="form-tables my-2">
            <div class="flex flex-wrap gap-1">
              {#each tableNames as tabName, idx (idx)}
                <div>
                  {#if idx == 0}
                    <label for={'t-name-' + idx}>Table Names:</label>
                  {:else}
                    <label for={'t-name-' + idx} class="invisible">Table Names:</label>
                  {/if}
                  <input type="text" id={'t-name-' + idx} name={'t-name-' + idx} value={tabName}
                    on:input={(event) => { tableNames[idx] = event.target.value}}
                    class="rounded border-gray-300 text-sm ml-2 py-1"/>
                </div>
              {/each}
            </div>
          </div>
        </div>

        <div class="flex justify-center text-sm mb-6 {tableNames.length <= 3 ? 'mt-3' : 'mt-1'}">
          <!-- buttons div -->
          <button type="button" on:click={cancelUpload}
            class="bg-zinc-300 text-white rounded-md px-4 py-2 mr-4 hover:bg-zinc-400">
            Cancel
          </button>
          <button type="submit" class="bg-green-500 text-slate-50 rounded-md py-2 px-4 hover:bg-green-600">
            Looks Good!
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}
