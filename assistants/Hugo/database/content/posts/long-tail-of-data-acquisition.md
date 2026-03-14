---
layout: post
title: Solving the Long Tail of Data Acquisition
tags: [data-strategy, product-strategy, research, startups]
color: blue
---

<div class="hidden">The deep learning revolution was initiated not by intelligent algorithms alone, but with the help of powerful compute and access to data. While models have continued to improve and compute power has continued to advance, progress on data collection has not been so fortunate.  Data labeling companies would have you believe that they alone are the solution to all our data problems - provided, of course, that we pay their exorbitant fees.  However, relying on vendors avoids the core issue since the underlying cost and complexity of gathering high quality data remains untouched.  As things currently stand, the effort needed to annotate each additional batch of data increases over time as the examples reach the long tail of the distribution. Any company able to figure out a way to transform data annotation from a cost-center into an area of innovation gains an enviable competitive advantage. But how?</div>

 <!--more-->

The deep learning revolution was initiated not by intelligent algorithms alone, but with the help of powerful compute and access to data.[^1] While models have continued to improve and [compute power has continued to advance](https://blogs.nvidia.com/blog/2022/09/20/keynote-gtc-nvidia-ceo/), progress on data collection has not been so fortunate.  Data labeling companies would have you believe that they alone are the solution to all our data problems -- provided, of course, that we pay their exorbitant fees.  However, relying on vendors avoids the core issue since the underlying cost and complexity of gathering high quality data remains untouched.  As things currently stand, the effort needed to annotate each additional batch of data _increases_ over time as the examples reach the long tail of the distribution. Any company able to figure out a way to transform data annotation from a cost-center into an area of innovation gains an enviable competitive advantage. But how?


## The Long Tail of Data Annotation

<!-- ![Jedi IQ on Labeled Data]({{"/assets/img/jedi_labeled_data.png"}}) -->

Given the obvious dependence on labels to perform supervised learning, even newcomers to AI recognize the necessity of annotated data.  It doesn't take much longer though to realize just how hard it is to collect those labels, so the conversation quickly shifts to the brighter and shinier parts of machine learning — the modeling.  But as alluded to earlier, this attitude just doesn't cut it though when an organization must face the reality that their raison d'être is to satisfy customer needs and not to play with cutting-edge toys.

In a [thought-provoking review](https://future.com/new-business-ai-different-traditional-software/) of the AI landscape, Martin Casado and Matt Bornstein from A16Z called out the fundamental flaws that prevented AI companies from enjoying the typical returns found in their SaaS counterparts.  They noted, in Feb 2020, that "scaling AI systems can be rockier than expected, because AI lives in the long tail."  The boost provided to the ML system by the first 10,000 training examples is significantly greater than the boost seen when adding data in later on.  Furthermore, the cost of labeling examples 100,000 to 110,000 has also increased exponentially along the way.  Instead of getting stronger, the [data moat erodes as the corpus grows](https://a16z.com/2019/05/09/data-network-effects-moats/).  The result: a negative fly-wheel where more customers means higher costs to serve them. The exact opposite effect that a scaling start-up wants to experience.

The same authors [provide some hints](https://a16z.com/2020/08/12/taming-the-tail-adventures-in-improving-ai-economics/) at improving the unit economics of such a business model.  Use the right tool for the job (ie. not deep learning).  Narrow the focus of the system into something manageable.  Consider the benefits of transfer learning.  These points are all correct, but they're mostly just bandages on a fundamentally difficult situation.  How exactly does transfer learning solve the long tail of data labeling?  It doesn't. So, where do we look to find the AI revolution we so desperately seek?

## Machine-in-the-Loop Annotation

A sizable number of incumbents already exist in the data labeling industry, providing annotations for self-driving cars, named entity recognizers and everything in between.  Millions of dollars have been poured in to prop these companies up into unicorn status.  If lack of labeled data is the sin, might these companies be our saviors?

At first glance, it does seem like such businesses should play an important role in moving the field forward.  They have invested heavily into streamlining their processes, in addition to designing high-usability platforms to make the annotation experience as smooth as possible.  There is no doubt that they will eventually build ML driven data augmentation right into the annotation process if they haven't already done so.  And there's a growing body of research to suggest that such machine-assisted labeling is indeed the way of the future.

As a quick aside, let's visit just a handful of examples.  To start, it might not be surprising that if you "Want To Reduce Labeling Costs, GPT-3 Can Help" through pseudo-labeling.[^2]  You can also use the model to generate the datasets, including synthesized inputs and outputs.[^3]  Others have showed that using GPT-3 followed by human verification improves Extractive QA.[^4] You can even use models to help with the verification process as well.[^5]

Now, back to the data labeling effort.  Does machine-in-the-loop annotation solve our problem?  [Let's think step-by-step](https://twitter.com/arankomatsuzaki/status/1529278580189908993).  An AI revolution requires scalable access to labeled data.  Data labeling companies outsource the effort to overseas workers, lowering their costs.  They employ technology to lower the costs further.  Now the cost of dealing with the long-tail is much lower than before. But the negative feedback cycle still remains.

The issue has been mitigated, but not eliminated.

Now, let's be clear.  If you are running a firm or department in charge of annotating large amounts of data, you should certainly make an effort to take full advantage of the current state-of-the-art techniques.  The point is not that machine-assistance is bad, but more that machine-assistance is not enough.

<blockquote>
"We must flip the script such that the burden of annotation is placed on the machine, with humans merely assisting."
</blockquote>

Data labeling firms generate a profit by farming tasks out to lower paid crowdsource workers, taking advantage of labor arbitrage.  Notably, they are _not_ taking advantage of economies of scale since the cost of annotating each marginal data point doesn't budge.[^6]  AI-assisted annotations certainly helps, but improved GUIs and task reformulation are likely to help just as much.

In order for an AI-first company to survive, we have to move from a _machine-assisted_ data labeling process to a _machine-driven_ one. At the moment, humans still bear the bulk of the annotation effort, and machines just help where possible. Instead, we must flip the script such that the burden of annotation is placed in the machine, with humans merely assisting.  Only then would we be able to invert the negative flywheel into a positive loop.

## Towards a Human-in-the-Loop Paradigm

A fully automated annotation system that can operate without any intervention is essentially AGI.  To expect such an outcome is unrealistic.  However, we can ask ourselves if it is possible to reach a reality where human intervention is minimized, or perhaps even where the amount of data being labeled is decoupled from the level of human involvement.

To see how a sustainable business might operate in this world, we can consider how building in the cloud has evolved.  Let's define Software 1.0 as a process whereby a number of software developers write a bunch of code instructing the machine on what do to.  In contrast, machines in Software 2.0 learn what to do for themselves by training on a bunch of labeled data. Now if it weren't for that pesky step of manually labeling the data, we would have a completely machine-driven process.  That's not the case at the moment, but let's suppose it were.  Assume the data labelers were replaced by a magical technology fairy.  Would humans still be involved at all?

If we were to replace software developers in the same manner (🤨 [CoPilot](https://betterprogramming.pub/github-copilot-a-tool-or-doom-for-programmers-dfa79ba84bbc?gi=b2851c166d2a)?), we would see that there are still many humans involved with launching new features.  Even discounting the product managers, designers and business analysts outside the development process, there already exist a number of programmers helping with code review, QA and IT Ops.

As more code is deployed, the more QA is needed to review the code.  This level of human intervention is acceptable though because there isn't a long tail effect where the amount of code written exacerbates the amount of QA needed.  The increase in effort is linear rather than exponential.  Moreover, the degree of QA controls the likelihood of the bugs in production, and not the lines of code being written.  This decoupling means the human QA effort does not bottleneck the coding effort.
Arguably, there is even a positive feedback loop.  As the programmer writes more code, the more feedback they receive from QA and the better code they write as they learn to avoid common mistakes over time.

How does this translate to a Software 2.0 environment?  If the data labeling pipeline is managed in the same manner, then the humans-in-the-loop are there simply to QA the quality of the data.  Model deployments (ie. feature releases) are no longer blocked by manual exercises, yet model accuracy improves when more human effort is applied.  We have effectively transformed heavy human involvement into lightweight human verification, letting the machine perform the bulk of the work instead.  The development process has shifted into something safe and reliable, almost mundane, in its implementation.

Why hasn't this already happened?  Looking back, we notice that this world starts with the assumption of a technology fairy.  What we need to now is figure out how to engineer such a system capable of generating labeled data.

## Controllable, Reliable, Explainable

Large, pre-trained LMs are capable of generating high quality, high fluency text.  Fantastic performance is possible even without explicit training through in-context learning.  But their gargantuan size can make them hard to control,[^7] lexically or semantically.  When they work well, all is fine, but when predictions are incorrect or generations are toxic, there's not much that can be done about it.  Fine-tuning is impractical at best, and unattainable at worst since the model is hidden behind a pay-to-play API.  With training already this difficult, probing for explanations is effectively impossible.

Human annotators on the other hand are also able to produce fluent and coherent text.  They are relatively easy to control through guidelines and training manuals.  They behave in well understood ways and often make a good faith effort to be correct.  Critically, when mistakes are inevitably made, human annotators can easily explain their thought process and quickly adapt to changing circumstances.

If we're willing to look past the hype, we see that LLMs still have a way to go before matching human performance on data labeling.  They fall short on three key desiderata: controllability, reliability and explainability.

<blockquote>
"By leveraging large LMs as data generators rather than directly as classifiers, a number of strategic benefits are now unlocked."
</blockquote>

Is there a way out?  The key insight is to control the output of the LLM enough to be able to generate label-preserving training data.  We then fine-tune smaller, more manageable models on this data for downstream applications.  By leveraging large LMs indirectly as data generators rather than directly as classifiers, a number of strategic benefits are now unlocked.

Rather than using the model directly for prediction, we now have access to tangible data which can be further molded and manipulated as desired.  If the diversity generated data is too low, we can apply additional data augmentation procedures.  If the noise of the generated data is too high, we can apply data denoising or data filtering techniques.  This format allows us to reliably produce high quantity and high quality data since we can repeat the process indefinitely until we have converged on a result we are satisfied with.

The discrete nature of the outputs means we can also directly observe what the large LM is thinking (to a certain extent).  If it starts to generate biased text, we can deal with it right away before feeding to the downstream model.  If we're exploring a new area due to domain shift, we can see interpretable examples of what the LLM believes is right.  This gets us the best of both worlds - automated, scalable data annotation leading directly to improved downstream model performance.

But where did the control of the large model come from?  While it's true that we can't fine-tune the entire model (ie. CTRL),[^8] we can nudge it in the right direction using soft-prompting and adapters. The outputs aren't perfect, but they don't have to be.  The augmented data is directly manageable so we can clean and denoise until it fits our goals.  The research on how to make this happen is an active, ongoing direction.[^9]

Finally, and maybe most critically, we can use the improved data to train better models.  The improved models interact with humans, collecting more real-world cases that are then fed back to the large LM for labeling.  For the first time, we have a truly positive feedback loop, where AI genuinely gets better the more it is used.

### Conclusion

Machine-assisted data labeling naturally hit limitations due to the complexities of real-life scenarios.  Machine-driven data labeling is required instead to cover the long tail, where humans are in the loop simply to verify.  This allows AI-first companies to scale into the future long after the funding and hype have faded away.

<!-- Large language models are Few-Shot Learners.[^1] And Zero-Shot Learners.[^2] And Zero-shot Reasoners too, why not?[^3]  So why hasn't AI [taken over the world](https://www.gwern.net/fiction/Clippy) yet? Well, apocalyptic scenarios aside, applying AI to real world problems just isn't that simple. -->

---

[^1]: (Sun et al., 2017) [Revisiting Unreasonable Effectiveness of Data in Deep Learning Era](https://arxiv.org/abs/1707.02968)
[^2]: (Wang et al., 2021) [Want To Reduce Labeling Costs, GPT-3 Can Help](https://aclanthology.org/2021.findings-emnlp.354/)
[^3]: WANLI (Liu et al., 2021) [Worker and AI Collaboration for NLI Dataset Creation](https://arxiv.org/abs/2201.05955)
[^4]: DADC (Bartolo et al., 2022) [Models in the Loop: Aiding Crowdworkers with Generative Annotation Assistants](https://aclanthology.org/2022.naacl-main.275.pdf)
[^5]: (Wiegreffe et al., 2022) [Reframing Human-AI Collaboration for Generating Free-Text Explanations](https://aclanthology.org/2022.naacl-main.47/)
[^6]: Data labeling companies are possibly the _least_ likely group to innovate a novel method of data annotation.  Their business model incentives them to maintain the status quo since any deviation risks depreciating the tremendous investment poured into their current infrastructure, including their network of crowdworkers, optimized onboarding routines and refined sales copy.  This pushback is common whenever a new way of doing things makes the old way obsolete.
[^7]: Prefix-tuning (Li and Liang, 2021) [Prefix-Tuning: Optimizing Continuous Prompts for Generation](https://aclanthology.org/2021.acl-long.353/)
[^8]: CTRL (Keskar et al., 2019) [A Conditional Transformer Language Model for Controllable Generation](https://arxiv.org/abs/1909.05858)
[^9]: Driven by yours truly