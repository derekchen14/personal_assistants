
<script>
  import { Accordion, AccordionItem } from 'flowbite-svelte';
  import { Feedback_URL, Waitlist_URL, Sales_Email } from '$lib/constants.js';

  const faqData = [
    {
      header: 'What is Soleda?',
      content: `
        <ul class="list-disc pl-6"">
          <li>Soleda enables you to focus on doing your best work with the help of useful, reliable, and trustworthy AI Agents.</li>
          <li>Our agents combine traditional ML and modern generative AI to deliver accurate results. They're not simple LLM-wrappers.</li>
          <li>Rather than making assumptions, our agents work hard to understand what you want. Their explicit understanding module untangles ambiguity, building mutual understanding before taking action.</li>
        </ul>
      `,
      open: true,
    },
    {
      header: 'Who is Dana?',
      content: `
        <ul class="list-disc pl-6"">
          <li>Dana, Soleda's first AI Agent, supports all marketing analytics activities.</li>
          <li>It can integrate data across multiple sources, transform & clean your data, analyze marketing campaign performance, and build visualizations for dashboards.</li>
          <li>Dana can handle data of any size, from individual spreadsheets to large cloud data warehouses. We believe in <em>Small Data, Big Insights.</em></li>
          <li>In the future, Dana will handle A/B testing, sentiment analysis, behavioral targeting, and anything else related to marketing analytics.</li>
        </ul>
      `
    },
    {
      header: 'What can Dana do?',
      content: `
        <ul class="list-disc pl-6"">
          <li>While Dana is capable of general purpose data analysis, it is fine-tuned to help Growth Marketing Teams excel.</li>
          <li>Use Dana if you work with Marketing, Sales, and RevOps teams to reliably & accurately analyze data for decision-making insights.</li>
          <li>It can provide all standard visualizations such as bar charts, line charts, scatterplots, as well as dashboards for persisting figures and recurring reports for sharing.</li>
          <li>We currently do not provide any customizations for product, engineering, design, legal or HR teams. If you are interested in this, please <a href="${Sales_Email}" target="_blank" class="underline">contact sales</a>.</li>
        </ul>
      `
    },
    {
      header: 'How can I use your agent?',
      content: `
        <ul class="list-disc pl-6"">
          <li>We currently support uploading CSVs and spreadsheets.</li>
          <li>We are actively working on integrating Snowflake, DataBricks, BigQuery and RedShift.</li>
          <li>If you are interested in these integrations, please <a href="${Feedback_URL}" target="_blank" class="underline">let us know</a> and we will prioritize them on our roadmap.</li>
        </ul>
      `
    },
    {
      header: 'What makes Dana different from other agents?',
      content: `
        <ul class="list-disc pl-6"">
          <li>You can trust Dana to provide accurate & reliable insights from your data!</li>
          <li>Unlike block-box agents that you can't trust, Dana will show you the queries used to pull data.</li>
          <li>Dana helps you identify gaps in the data to deal with missing or incomplete data.</li>
          <li>Dana is trained using supervised fine-tuning with custom labeled data. It uses the latest advancements in AI technology.</li>
          <li>Learn more about Dana <a href="/about" class="underline">here</a>.</li>
        </ul>
      `
    },
    {
      header: 'What is your privacy and data retention policy?',
      content: `
        <ul class="list-disc pl-6"">
          <li>At Soleda takes data privacy and security very seriously.</li>
          <li>We do not store any user data, and all information is encrypted in transit and at rest.</li>
          <li>It is impossible for us to lose your data, since your data stays on your machine.</li>
          <li>We only ever see related meta-data, such as schema information.</li>
        </ul>
      `
    },
    {
      header: 'How much does it cost?',
      content: `
        <ul class="list-disc pl-6"">
          <li>Our basic analysis service which covers CSV uploads is free forever.</li>
          <li>If you would like to connect a cloud data warehouse, we charge a monthly subscription fee. Please <a href="${Sales_Email}" target="_blank" class="underline">contact us</a> for more information.</li>
        </ul>
      `
    },
  ];

</script>

<section>

  <div class="container mx-auto section-content flex flex-col mb-6">  
    <h1 class="section-eyebrow text-4xl text-center font-bold">Learn More</h1>
    <h2 class="section-header text-xl text-center font-normal mb-2">All about AI agents you can trust.</h2>
  </div>

  <div class="container mx-auto">
    <Accordion multiple flush
      classInactive=""
      inactiveClass="text-black"
    >
      {#each faqData as { header, content, open }}
      <AccordionItem
        defaultClass="flex items-center justify-between w-full py-0 pr-4 mt-0 bg-white rounded-lg mb-2"
        open={open ? true : undefined}
        paddingFlush=""
        borderClass=""
        borderBottomClass=""
      >
        <h2 class="text-md md:text-lg p-3 font-bold text-left" slot="header">{header}</h2>
        <p class="m-0 px-4 py-4 text-black">{@html content}</p>
      </AccordionItem>
      {/each}
    </Accordion>
  </div>

  <div class="container mx-auto section-content flex flex-col my-6">  
    <h1 class="section-eyebrow text-3xl text-center font-bold mt-6 title-font">Ready to talk to Dana?</h1>

    <a href={Waitlist_URL}
      class="mx-auto"
      target="_blank"
    >
      <button class="hover:underline text-gray-800 font-bold rounded-full 
        my-4 py-4 px-12 shadow-lg bg-[#4c788b] text-white
        focus:outline-none focus:shadow-outline transform transition hover:scale-105 duration-300 ease-in-out">
        Join Waitlist
      </button>
    </a>
  </div>
  
</section>