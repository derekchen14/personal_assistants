---
layout: post
title: Data Collection Best Practices
tags: [ai, data-strategy, explainer, lists]
color: blue
excerpt_separator: <!--more-->
---

The first step to truly becoming an [AI-first](https://morethanoneturn.com/2021/05/23/embracing-ai-first.html) company is to adopt a [data-centric](http://datacentricai.org/) view, which naturally implies taking data collection seriously as a core competency of the business.  Even before involving any sophistcated algorithms to improve data quality, there are already many best practices to consider when performing manual data collection.  At a high level, this can be broken down into improvements 
<!--more-->
on the people, the tools and the process itself.  In total, they constitute a basic checklist of items to consider when performing data labeling for NLP tasks.

## Annotator Training

### Recruiting
Gathering quality data begins with reliable annotators who understand the problem you're working on.  Your first line of defense are the tools built directly into MTurk including filters and quals.  Filters should be set to 90-95% acceptance rate and specific English-speaking locations.  A pro-tip is to consider places beyond the United States, such as to include Canada, Britain and Singapore.  Of course, if your NLP task requires multi-language or code-switched labels, then you should branch out even further.  Qualifications are mini-exams that you can require annotators pass before starting your HIT.  The benefit of using these quals to both (a) prevent spammers and (b) ensure that the worker understands the task cannot be overstated.

Of course, you should also pay the crowd-workers a reasonable rate for their work.  It should be commonsense, but there is also a clear correlation between offering higher pay and attracting higher quality workers.  If you happen to be doing repeated work, it might make sense to keep a running list of known experts on your task such that you can invite them back rather than recruiting new folks every time.

### Onboarding
As new workers start your data collection task, they will need a well-written training manual to explain the task and how to go about labeling the text for any given situation.  Natural language utterances are extremely nuanced and thus require clear guidelines for picking out these detailed differences.  Dialogue in particular is heavily context dependent.  As you work more with crowdworkers, you will find almost all of them acting in good faith to provide the best annotations possible.  When something is mislabeled, it is much more likely the cause is due to lackluster guidelines or truly tricky conversations rather than workers behaving with ill-intent.  Thus, putting in the time to really write clear instructions is well worth the effort.

Tips for writing great guidelines:
  - give an explanation of your task in clear, simple writing -- without the jargon
  - remember that your reader is not an expert in linguistics or NLP
  - explain what is happening from the start, not from what you think they should already know
  - highlight the most important details in *italics*, __bold__ or <span style="color:green;">color</span>
  - offer examples of good annotations and examples of common mistakes when annotating
  - repeat yourself on the most critical parts if necessary

If you want to go above and beyond, consider creating tutorial videos and/or offering feedback through email.  When collecting data for ABCD,[^1] we found that offering live feedback through a Slack/Discord channel yielded tremendous gains.  Other research has corroborated the findings that expert feedback can be quite helpful.[^2]  Intutively, it also makes sense that superficial interventions, such as asking the workers to provide a justification for their labels does not help much.  An interesting trick is to have the highest rated crowdworkers provide feedback to other crowdworkers which can help to naturally scale the process. 

### Retention
For long-running tasks, you can also add in certain aspects to make sure the workers keep on their toes.  In particular, it is common practice to include occassional gold labels that you know are correct.  Then, any workers who mess up too many of these may have their qualifications revoked. Additionally, ideas such as time limits or other thresholds can help to prevent folks getting lazy.  More specifically, suppose you are collecting a dialogue chat, then a token minimum can be automatically checked to make sure the utterances they have generated match some minimum length.  Finally, you should perform occasional spot checks to ensure quality has not dropped.

Just like running any company though, employee satisfaction becomes paramount.  It makes much more sense to think about how to retain your best workers than to waste extra time worrying about a few bad apples.  One of the unmentioned benefits of feedback and iteration is that it keeps the workers engaged.  Along those lines any sort of reward system, such as bonuses for particularly good labels, warrant a bit of discussion.  Bonuses can be offered per HIT that is done well, or as a one-off system for people who perform well in aggregate.  If there are folks managing and supporting other crowdsource workers then this would certainly warrant some sort of bonus. Be creative in your rewards! Utimately, anything that can help the workers do their job better will end up helping you.

## Annotation Experience

### General principles
Making the data collection process as realistic as possible will drastically improve the data being collected because workers no longer need to conciously think about all the rules and regulations in the guidelines.  Instead, they can just focus on acting normally and letting their natural tendencies take over, which is what we want to train a model to do anyway.  This insight compelled us to develop Expert Live Chat,[^1] which differs from typical Wizard-of-Oz data collection by three aspects:
  1. Conversations are conducted continuously in real-time.
    - no set number of turns
    - no templated responses
    - interlocutors can speak for multiple turns in a row
  2. Users involved are not interchangeable.
    - there is an explicit agent and customer relationship, which mimics real-life
    - since people have distinct roles, the typical customs of how to behave naturally arise
  3. Players are informed that all participants are human.
    – there is no wizard behind the scenes
    - encourages people to act like they would with humans rather than with machines
While these aspects make data collection more difficult (methods for resolving this discussed in the paper), they dramatically increase the verisimilitude of the generated conversations.  More generally, even when dealing with non-dialogue related data tasks, any way to make the task itself feel natural should improve results.

### Human-computer interaction
There exists a large body of work in [HCI](https://en.wikipedia.org/wiki/Human%E2%80%93computer_interaction) and [Design Thinking](https://www.interaction-design.org/literature/article/what-is-design-thinking-and-why-is-it-so-popular) around how to make better software, much of which can be carried over to the [design of annotation tools](https://aclanthology.org/W12-3613/).

The basic idea behind designing great user experiences is to make the task as simple and intuitive as possible.  This encompasses making the labeling task itself straightforward (more on this in the next section), but also includes keeping the tool simple and easy to use as well.  If there are ways to minimize, or even eliminate, clicking around on a mouse, then you should do so.  For example, rather than having to click \[Next Item\] or \[Submit\], allow these to be transformed into keyboard shortcuts. Rather than a long dropdown menu the user must scroll through, allow for fuzzy search on the list of labels.  Even when restricted to just typing, find ways to minimize the number of keystrokes needed.  For example, offer a text autocomplete function for common phrases or inputs.

Prevent users from making mistakes, but if they do, then allow those users to fix them easily.  We can instantiate these principles through distinct elements in the user interface.  Buttons meant to be clicked should seem clickable (e.g. bolded, shaded), whereas buttons meant to be avoided should not (e.g. grayed out).  If a user clicks on a button that causes irreverisible changes or destructive actions (e.g. delete all annotations), show a warning dialog to check if this action is something they actually wanted to perform.  If a user _does_ click on something accidentally, provide an option to easily recover from the error; for example, a back button to return to the previous example.

### System architecture
Real world data collection tasks don't just end when the text has been annotated.  We should be desiging for the end-to-end data collection pipeline from ideation to shipping into production.  Is there anything that allows researchers or engineers to quickly spin up new experiments?  Perhaps it is very common for you to perform human evaluation on new iterations of your dialogue model.  Templates can be put into place to easily spin up new evaluation rounds.  This can even be automated such that whenever a new model is fully trained, automatically kick off qualitative evaluation (e.g. coherency, fluency) the same way you might kick off quantitative evaluation (e.g. BLEU, perplexity).

Automation can work in reverse as well.  Suppose the task is sentiment analysis where given an input utterance, you want to classify as either positive, negative or neutral.  After finishing a round of data collection, the system will automatically pass the labels to an in-house annotation team to QA.  High confidence labels can be directly integrated into data store to immediately start-up a new cycle of model training.

## Annotation Process

### Labeling platforms
When performing data collection, realize that a wide spectrum of services are available to do the actual annotation.  Starting with the broadest audience, serices such as [Toloka](https://toloka.yandex.com/) and [Amazon Mechnical Turk](https://www.mturk.com/) allow you to tap into a much wider pool for NLP annotation tasks.[^3]  Large commerical vendors are also an option, but frankly I would only recommend them when there are strict PII requirements, such as dealing with medical or enterprise data, since otherwise their high price points aren't justified.  The next level involves working with contractors such as those found through [upwork](https://www.upwork.com/) or [fiverr](https://www.fiverr.com/).  The benefit is the ability to retain knowledge over time, at the cost of a higher upfront investment to vet for quality workers.

If you have the budget, then moving the entire process in-house would obviously be preferred.  An in-house annotation team can be guided to the exact task you prefer and will always be available.  The internal communication can also allow for side-by-side iteration on the task design and data collection, since the ontology can often shift due to feedback from the raw data.  Finally, if you can afford to hire a handful of PhD linguists or a team of in-house experts to perform annotation, then you are probably a FAANG company.  In all seriousness, expert annotation was the traditional method of obtaining labels, but fails to scale to the size needed to train modern ML models.

### Task Design
If you can formulate your problem in a simple manner, then you can obviate the need for subject matter experts and take full advantage of crowd-source workers to scale the effort.  For example, rather than offering a long list of options to choose from for a label, offer just a few multiple choice options.  Even with a limited ontology, annotation can still be difficult when dealing with multi-class and multi-label tasks (ie. many intents can be present in a single dialogue utterance). One ingenious method is to break down the labeling task into a series of simple choices, effectively turning the annotator into a human decision tree where the number of choices for a single HIT is equivalent to the branching factor.[^4]  Another technique is to minimize the cognitive load so you can build a semantic parser[^5] or dialogue agent overnight.[^6] The authors transformed the task by reversing the process.  Rather than providing an utterance and asking for a label, the task starts with a known label and asking the worker to paraphrase a template associated with the known label into a natural language utterance.

If you can transform the problem into binary selection, perhaps with a contrastive learning algorithm, the task becomes that much easier to label and review.  But even more than the time savings, there is a certain level of simplicity where the task can rely on System I rather than System II processing.  Whereas human eyes and brains are naturally pre-disposed to perform image classification, concious effort must be made to parse speech and perform contextual reasoning.  Labeling then becomes a task the annotator can simply react to rather than think about conciously, which more closely matches how a neural network operates. In other words, effort spent on task simplication may offer exponential gains on model improvement.

### Active learning
A common idea to appears when trying to improve the annotation process is to be more intelligent about how we select what to label.  While active learning does seem to provide noticeable benefits,[^7] much of the research suggests that the gains are inconsistent[^8] or limited[^9].  More recent work has shown that the cause might be due to the fact that active learning often picks up on outliers which are hard or even impossible to learn from.[^10]

Given the difficulties of getting things to work well in practice, it is my opinion that active learning might not be a great avenue to explore.  While you may see gains of a few weeks in speed-up for example selection, it will cost you a few weeks to set up the process as well.  Assuming there are problems along the way, you might even end up in a net-negative position in terms of annotation speed.  In conclusion, if there are obvious cases where certain examples need extra labels (eg. a brand new class was added to the ontology), then some focused annotation might be worthwhile. But in general, active learning might not be worth the effort.

## Conclusion
Effective data collection is a skill and an art.  Depending on the nature of the task, certain methods may help speed up the process, but we want to careful that efficiency gains aren't occuring at local maxima.  Ultimately, investments in data collection will pay great dividends and should be taken seriously by any company desiring to become AI-first.


---

[^1]: Chen et al. (2021), [Action-Based Conversations Dataset](https://aclanthology.org/2021.naacl-main.239/)
[^2]: Nangia et al. (2021), [Effective Crowdsourcing Protocol for Data Collection](https://aclanthology.org/2021.acl-long.98/)
[^3]: Snow et al. (2008), [Evaluating Non-Expert Annotations for NLP Tasks](https://aclanthology.org/D08-1027/)
[^4]: Dian Yu and Zhou Yu (2020), [MIDAS: A Dialog Act Annotation Scheme](https://aclanthology.org/2021.eacl-main.94/)
[^5]: Wang et al. (2015), [Building a Semantic Parser Overnight](https://aclanthology.org/P15-1129/)
[^6]: Shah et al. (2018), [Building a Conversational Agent Overnight](https://aclanthology.org/N18-3006/)
[^7]: Ash et al. (2020), [BADGE: Deep Batch Active Learning](https://openreview.net/forum?id=ryghZJBKPS)
[^8]: Lowell et al. (2019), [Practical Obstacles to Deploying Active Learning](https://aclanthology.org/D19-1003/)
[^9]: Ein-Dor et al. (2021), [Active Learning for BERT](https://aclanthology.org/2020.emnlp-main.638/)
[^10]: Karamcheti et al. (2021),  [Investigating the Negative Impact of Outliers for VQA](https://aclanthology.org/2021.acl-long.564/)


