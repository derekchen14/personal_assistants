---
layout: post
title: EMNLP 2020 Highlights
tags: [conference, trends]
excerpt_separator: <!--more-->
---

This is nominally a review of trends from the EMNLP 2020, but also serves as the end of year review.  As this (crazy) year comes to a close, we take a moment to reflect on what has happened in the world of NLP and specifically in relation to Dialogue Modeling and Natural Language Understanding.  From my (limited) perspective, there are four trends which I noticed, including increased research into (1) data methods rather than models and (2) data efficiency techniques.  In the follow-up, we discuss observations around (3) limitations in dialogue state tracking and (4) convergence around similar ideas.

Let's dive into each one in more detail:

<!--more-->

## (1) Data Methods over Models

From the review of ACL earlier this year, we have already seen that the world belongs to Transformers and we're just living in it.  For most tasks, some version of BERT (including RoBERTa), BART, GPT or T5 have become the de facto baselines, taking over BiLSTMs w/ Attention and RNNs before that.  As evidenced on their performance on [SuperGLUE](https://super.gluebenchmark.com/), these models work suprisingly well across a wide range of tasks, and many traditional datasets are arguably "solved" in a loose sense of the word.  This has led to at least two major trends which highlight the importance of data and de-emphasize the efforts of designing a new model.

When current models outperform their benchmarks, the typical order of the ecosystem naturally tilts the balance in the other direction.  Researchers start producing datasets that are increasingly harder until we are able to once again fool the models, reaching a new equilibrium.  However this time around, for certain areas of study, we have started to hit on a fundamental limitation where naively collecting data from crowdsource workers using traditional methods yields a task that is immediately solvable by the strong baselines.  In other words, we can't make the tasks any harder because then the task becomes too hard for humans to reliably annotate correctly.

So does this mean that ML models have achieved human level performance in understanding language?  Certainly not, since all models (neural or otherwise), still lack even rudimentary common sense or other basic reasoning skills that we expect from toddlers.[^1] The issue lies not with humans or models, but rather in how we design the task and the associated data collection techniques.[^2] Consequently, we have started to see more folks thinking carefully about the issues we introduce during the data collection process.

As a number of papers have noted, one of the issues plaguing modern models is their ability to perform so well out-of-the-box by exploiting human annotator biases.[^3]  For example, when writing mulitple choice answers, humans will typically choose a positive example as the correct answer.  As such, models are sometimes able to choose the correct answer, without even having read the corresponding question.  Accordingly, new techniques, such as adversarial filtering, have been developed to combat this.  In EMNLP, the authors take this a step further by offering [Dataset Cartography](https://arxiv.org/abs/2009.10795) (Swayamdipta et al.) as a model-based tool for characterizing and diagnosing these types of issues.

In my experience, spending one or two days cleaning the data often has much better return than the same one or two days spent designing a new model architecture.  While this does not necessarily lead to novel advancements in the academic sense, it does yield notable gains in predictive performance that are quite meaningful in the practical sense.  Overall, it's an exciting time to be building tools for automating data pre-processing and analyzing data quality.

## (2) Data Efficiency

The second data-related trend comes from recognizing that while large transformer-based models perform
shocking well in zero-shot settings, real-world scenarios have no qualms around using further data to continue to boost performance.  As a result, data collection for the end task remains relevant, and perhaps even more so as we realize the degree of impact that simply adding more data can have.  To this extent, there has been a noticeable growth in the amount of papers which care about data efficiency, which I will define as the desire to make the most efficient use of the limited amount of available, annotated data.

In regards to data efficiency, large-scale LMs arguably fall under the category of self-supervision.  For dialogue in particular, authors Wu, Hoi, and Xiong suggest methods for [Improving Limited Labeled DST with Self-Supervision](https://arxiv.org/abs/2010.13920) by preserving latent consistency and modeling conversational behavior.  Whereas self-supervised models are often useful for fine-tuning on downstream tasks, meta-learned models perform this preparation explicitly.  [Efficient Meta Lifelong-Learning with Limited Memory](https://arxiv.org/abs/2010.02500) (Wang, Mehta, Póczos, Carbonell) tackles meta-learning of models to prevent catastrophic forgetting and negative transfer by designing a more efficient episodic memory component (MbPA++).[^4]

Interestingly, one of the ways the authors make the memory component more efficient is by being more selective about which prior examples are placed into memory, thus maximizing the chance of matching with an item during inference.  In particular, they aim to maximize the diversity of stored examples (rather than uncertainty) in a way that is reminiscent of methods in active learning.  On the topic of active learning, [Cold-start Active Learning](https://arxiv.org/abs/2010.09535) (Yuan, Lin, Boyd-Graber) attempts to take the best of both pre-training (with BERT) and active learning to produce samples most conducive to learning on the end task of text classification.  Similar to BADGE[^5], the authors propose to embed all examples into a shared vector space in order to choose the next sample to label, however they argue the embeddings should instead be selected based on their surprisal factor rather than their gradients.

One last method of using annotated data efficiently is to increase its impact through data augmentation methods.  Whereas there are some fairly simple techniques that can be applied in computer vision, naive data augmentation can often fail to perform well since swapping out even a single word can dramatically change the semantics of an utterance. Back translation is better since it is less likely to produce incoherent sentences, but does produce generic responses which are not as useful. Instead, [Data Boost](https://www.aclweb.org/anthology/2020.emnlp-main.726/) (Liu et al.) trains a generator (based off GPT-2) to come up with new examples. Condition the generation of each token on the class, but train the model through Reinforcement Learning, where the RL reward is the salience (i.e. relevance) of each token to the class plus a KL-penalty to discourage movement outside the trust-region.

The common insight from all data augmentation papers is rather than augment directly, instead generate new fake examples and include a filtering step to ensure quality.  To see how this theme recurs in dialogue, move onto the second half of the observations found in [Part Two](https://morethanoneturn.com/2020/12/30/year-end-review-2020.html).

---

[^1]: [CLEVR dataset](https://arxiv.org/abs/1612.06890) (Johnson et al.)
[^2]: [Are we modeling the task or the annotator?](https://www.aclweb.org/anthology/D19-1107/) (Geva, Goldberg, Berant)
[^3]: [Adversarial Filters of Dataset Biases](https://arxiv.org/abs/2002.04108) (Le Bras et al.)
[^4]: [Episodic Memory in Lifelong Language Learning](https://arxiv.org/abs/1906.01076) (d'Autume, Ruder, Kong, Yogatama)
[^5]: [Deep Batch Active Learning by Diverse, Uncertain Gradient Lower Bounds](https://arxiv.org/abs/1906.03671) (Ash et al.)