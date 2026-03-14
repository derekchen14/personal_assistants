---
layout: post
title: Intent Tracking For Task Oriented Dialogue - Best Paper Award Winner
date: '2018-12-21 01:46:06'
---

Another quarter, another class project on task oriented dialogue agents! &nbsp;This quarter I completed a paper studying the details of Intent Tracking within UW Graduate Machine Learning - CSE 546. &nbsp; And this time around, the paper won the award for best paper in the class!

<figure class="kg-card kg-image-card kg-card-hascaption"><img src="/content/images/2018/12/uw_ml_final_project.jpg" class="kg-image"><figcaption>Poster Presentation at Paul Allen Computer Science and Engineering Building</figcaption></figure>

Dialogue agents are employed in a wide variety of interactive systems including chat widgets and voice-activated bots. Despite their prevalence, a bot’s ability to understand the user is noticeably limited with most systems heavily reliant upon rule-based models where each new skill must be entered manually. Recent research has explored the use of modular, deep-learning networks which combines the neural-based gains popularized by end-to-end models with the interpretability benefits of more structured models.

The first module within such dialogue systems is a natural language understanding unit responsible for gathering the user intent. Referred to as the belief tracker or dialog state tracker, this component aims to understand the user in any given turn. Afterwards, this information is passed to the next module, the policy manager, for deciding the agent action. Given the chosen action, the final module generates the text response. In this context, this paper focuses on building numerous belief tracking baselines, starting from a basic neural network and progressively advancing to the state-of-the-art.

More specifically, I explored the nuances of belief tracking by experimenting with different approaches for preprocessing the labels, designing the pipeline, and building the network architecture. In doing so, we gain a better understanding of which trade-offs matter when constructing such data-driven models, and a greater appreciation of why robust intent tracking remains an elusive goal. Overall, we find that optimization methods, intelligent decomposition, and pre-trained embeddings play a key role in determining dialogue success.

Full paper here: [https://www.dropbox.com/s/qyda58bgkgwuit6/CSE546%20-%20Project%20Final%20Report.pdf?dl=0](https://www.dropbox.com/s/qyda58bgkgwuit6/CSE546%20-%20Project%20Final%20Report.pdf?dl=0)

