---
layout: post
title: Proper Assessment of Data Value
tags: [ai, data-strategy, explainer]
excerpt_separator: <!--more-->
---

Data is the new oil.  It underpins an undeniable aspect of growth in the popularity and dominance of deep learning.  But is all data created equal? What makes some data points worth more than others?  How could we go about calculating what each data point is worth?  If data is so important, we should certainly want to have a proper way to assess its value.  To do so, we should begin by recognizing that
 <!--more-->
some data is worth more than others.

For starters, labeled data should be worth more than unlabeled data.  Even with the most advanced pretraining, we would need a thousand to a million times more unlabeled data to rival the performance of valid labeled data for a given task.  As a next step, we might notice that even within annotated data, certain labels are more likely to be noisy as a natural consequence of crowdsourcing large datasets.  Thus, we could conclude that clean data is worth more than noisy data.  Going further, within the subset of correctly labeled data, certain examples will help the model learn more, perhaps because they are data points near the decision boundary or perhaps they are more closely aligned with test distribution.

With all that said, how could we go about calculating such a thing?  Is there a systematic and principled method for determining the proper value of data?  That's what this post will dive into.  Although there are no perfect answer, we chart three major directions worth exploring.  First, we consider data as more valuable when it maximizes information gain.  Next, we measure a datapoint's value by observing its impact on the model's training dynamics.  Lastly, we consider a training example's value as how much improvement it provides over not having that example.

## 1) Maximizing Information Gain

Data that contains more information should be considered more valuable.  We can quantify the level of information within the data as examples which provide more diversity or examples that lowers uncertainty.

### Diversity

Intuitively, diversity is helpful because data that adds something different from what I've seen before is more informative.  We can measure through various forms of novelty[^1] or mutual information.  From the novelty perspective, data points that are embedded in a space further away from anything we've seen so far is considered diverse.  Variants here include how we embed the data and how to calculate distance.  A notable case, as proposed by BADGE[^2], is to use the gradient of the training example as its embedding, which encodes not only diverse but also high magnitude.

From the information perspective, we can measure the mutual information of the training example compared to a subset of the training data. Mathematically, we measure mutual information as:

$$ MI(X, Y) = D_{KL}  [ P(X,Y) || P(X) \cdot P(Y) ]  $$

where X can be our given data so far and Y is our current data point. Diverse data should be less predictive of current training data, and thus have lower mutual information.

### Uncertainty

We also prefer data that allows us to learn more information regarding areas that I'm not so sure about. Mathematically, this can be formalized as lowering the entropy of a model's outputs.  Alternatively, we can use uncertainty as a tool by measuring a model's uncertain about that data point.  Then getting a correct label for that datapoint would be highly informative.  Since a single datapoint is less likely to have a large impact, we can measure the impact of a batch of data.  Then, to get the value of each data point, we average over all batches that the datapoint participated in.  Furthermore, recall that model uncertainty can be measured in multiple ways including variance approximation with dropout[^3] or explicit Bayesian networks[^4].

## 2) Observing Training Dynamics

Since modern neural networks are over-parameterized, they can completely memorize the training data[^5].  However, those same models typically learn cleanly labeled examples before the noisy examples.[^6].  Therefore, we can determine an example is being more valuable by observing how it fluctuates during training.

### Observing the Softmax

As suggested within Dataset Cartography[^7], examples can be divided into those that are easy-to-learn, ambiguous and hard-to-learn.  The ambiguous ones supposedly help the most with learning, as long as some easy-to-learn examples are also included to stabilize training.  These ambiguous examples are those likely to be near the decision boundary, and thus help the model generalize.  Most interesting for our examination are the hard-to-learn examples, which can often be considered mislabeled.

To find hard-to-learn examples, we track the model's confidence across time to calculate a score.  More specifically, we track the output of the model for each training example as measured by:

$$ \mu_i = \frac{1}{E} \sum_{e=1}^E p_{\theta^e} (y_i^{\star} | x_i) $$

where $$\theta^e$$ are the model's parameters at epoch $$e$$. Then, these scores are averaged over all training epochs where the examples that have a lower score are those most likely to be noisy.  We can then discard those examples or relabel them.  The general idea is that when a model is not confident in it's output (ie. places low probability mass), this suggests that the label assigned to that example is wrong.

### Observing Logits

Alternatively, rather than tracking the model's final outputs, we can also consider looking at it's logits. Specifically, Pleiss et al. suggest looking at the Area Under the Margin (AUM) of an example's logit compared to the largest other logit[^8].  In formula form, we measure the score as:

$$ AUM(x,y) = \frac{1}{T} \sum_{t=1}^T z_y^{(t)} (x)  - max_{i \neq y} \left( z_i^{(t)} (x) \right) $$

where $$z_y$$ represents the assigned logit and $$z_{i \neq y}$$ is the largest other logit.

To understand what is going on, suppose we are classifying some images as either dogs, cats, horses, frogs, cows, etc.  Additionally, suppose that the given example is a dog, then the assigned logit is also dog.  The model's next largest logit is, say, a cat but the the gap between them is large since the model has done a good job differentiating between the two.  This large gap translates to a large AUM score.  Now suppose we are given a fish example, labeled as a dog.  Then the model's assigned logit may be quite low, whereas the next largest logit of fish is likely to be quite high since the model (rightly) believes that the image is a fish. Thus, the AUM will be low and once again we have identified a low value data point.

### Observing Hidden State

As a final direction, we might also consider how the hidden state of the model changes over time as training progresses.  In particular, I would assume that correctly labeled examples need smaller gradients and have more steady hidden states, whereas incorrectly labeled examples will exhibit more fluctuation.  The additional benefit of looking at the hidden state is that we can potentially have multiple output heads, representing multiple tasks.  Since each task would have a different set of logits and softmaxes, we instead look at the latest common hidden state of all tasks to measure the training dynamics.  This is a novel idea that hasn't been tested yet, so it could be totally wrong, but I think it's worth a shot.

## 3) Measuring Marginal Improvement

### Naive Difference

The basic ideas is that if a data point offers high marginal improvement, then it should be considered valuable. So as a baseline, we could measure the accuracy of the model trained on a subset of the data $$p$$ and then measure the accuracy again after trained with the extra data point $$q$$.  The marginal gain in accuracy $$p - q$$ can then be attributed to the data point's influence.  This is quite reminiscent of how LIME operates for the purposes of ML explainability[^9].

The clear drawback is that this requires re-training the model for every single data point, which quickly becomes intractable.  The other issue is that a single datapoint might not make a much of a difference depending on the data that came before it, so the impact would be negligible.  As a degenerate example, suppose we had a datapoint $$x_1$$ that was duplicated in the dataset as $$x_2$$.  If the model encountered $$x_1$$ first, then it would have some value, but if the model had encountered $$x_2$$ in a prior round, then $$x_1$$ would be deemed to have no value despite not actually changing.  To mitigate the issues described above, we first describe Shapley Values as a formal method for dealing with the ordering and then an algorithmic update to deal with the tractability.

### Shapley Values

Originally developed for economic purposes, the Shapely Value (SV) calculates the marginal benefit offered by each person within a coalition[^10].  People with high values are important, while those with especially low values are not helpful, and perhaps even harmful to the team.  In the case of data collection, each person represents an annotated label.  Accordingly, the SV of each datapoint tells us whether it is clean or noisy. and thus should be relabeled and/or eliminated.

This is done by calculating the marginal utility of each datapoint, averaged over all permutations of the subsets of collected data.  The permutation of a subset represents shuffling the order of the data when training the neural network. Thus, not only would we need to retrain a network for all subsets of data, we would need to take into account all permutations of drawing the subset.

$$ s_i = \frac{1}{N} \sum_{S \subseteq D \\ z_i} \binom{N-1}{|S|}^{-1} [v(S \cup {z_i}) - v(S)] $$

In the equation above $$s_i$$ stands for the Shapley Value of the $$i^{th}$$ example out of *N* training examples.  $$S \cup {z_i}$$ represents the subset with the extra datapoint, whereas $$S$$ by itself represents the subset without it.  The function $$v(\cdot)$$ is the standalone point value of the data, which can be approximated by the accuracy of the model trained with that data.  Due to the special properties of this value, the Shapley Value actually provides a unique, ideal solution for calculating data values for a given model[^11].  We still need to deal with the issue of calculating the value in a reasonable time frame.

### KNN approximation with LSH

Authors within Jia et al. ingeniously get around the problem of re-training the model for every data by choosing a model that requires no training to operate[^12].  In particular, the authors cast the model as a KNN rather than a neural network, so training for each new datapoint is trivial (there isn't any), with only memory limitations to consider.  First, recall that for each training input, the KNN gets that example correct if the test input matched with the training input has the correct label.  The test label becomes the prediction without any extra effort beyond a lookup call.

 With this in mind, the algorithm proceeds as follows:
  - For each test example $$x_j$$:
    - Sort the distance towards all training data to that test example
    - Calculate the value of each test example as the normalized marginal improvement it provides
    - Marginal improvement means:
      - Case 1: training example $$x_i$$ and $$x_{i+1}$$ are both still wrong, then the improvement is zero since 0 - 0 = 0
      - Case 2: training example $$x_i$$ is right, while the point further away is wrong, then improvement is 1 - 0 = 1
      - Case 3: training example $$x_i$$ is wrong while the point further away $$x_{i+1}$$ is actually correct, then the improvement is negative 0 - 1 = -1
      - Case 4: both training examples are correct since we are dealing with nearby datapoints, so improvement is nullified since 1 - 1 = 0
    - Normalized means to divide by the number of the remaining train examples being considered to keep things fair
  - For each train example $$x_i$$:
    - Average over the contributions that $$x_i$$ made to the test examples calculated earlier

The secret is that calculating the value of each test example is much simpler compared to previous methods because it is simply a deciding which of the four cases the training label falls under.  Thus going through the loops is quite fast, where the bottleneck is the sorting of training data.

As another speed-up, the authors turn to LSH (locality sensitive hashing) to minimize the amount of searching needed. To see how this works, first note that training examples far away from the test example likely contribute no marginal improvement to the $$s_j$$.  So we choose some threshold T, where training points further than T are just assumed to have value = 0 and those items are all eliminated from calculation. To be even smarter, an extension could somehow eliminate the super close training examples as well, since they also offer no marginal value.  The authors do not explore this.

The other part is to obtain the $$M - T$$ candidates using truncated LSH, rather than sorting by exact distance.  Concretely, note that the LSH process will (a) embed all the documents into some fixed multi-dimensional space that has some semantic meaning.  Typically, minHash is used, but for this case we use a specially designed hash function that approximates a L2 norm. (b) Suppose each document is now a 80-dim vector.  Break apart all the documents into bands (eg. b = 8, which has 10-dim vector) and compare only the partial vectors within each bucket using a hash function. (c) The partial vectors which are hashed to the same bucket collide because they are supposedly similar.  The corresponding full documents become candidate pairs. (d) Compare the limited number of candidate pairs on an exact match basis.  So for our case, we just switch up Step D into calculating Shapely Values rather than searching for duplicate pairs.  Overall, this means that even with 1 million training examples, we can calculate approximate Shapley Values in under an hour.

## Key Use Cases

Since data collected from crowdsourcing is often noisy, redundant labels are collected for each datapoint so that we can determine a final label through a majority vote.  Given these methods of assessing data quality, we can now consider an alternative formulation whereby we do not need spend extra effort upfront for all training examples.  Instead, we can label once, identify low value / mislabled data and then throw that data away or put it up for relabeling.  Since most annotators act in good faith and provide the correct label, this direction should decrease costs by at least half.

Additionally, some of the methods described above are able to assign value to unlabeled data.  In those cases, we can perform active learning to further maximize our limited resources.  If we go the other way, after all the data is collected, we could also consider paying more to workers who annotated better labels.  More generally, we can pay workers at a rate commensurate with the value of the labels they provide.

Overall, having a measure of data quality is useful to understand not only the data but ultimately the strength of the model.  Higher quality data naturally leads to better performing models.  This means real-world impact for whatever we designed our models to do.

---

[^1]: [Novelty Seeking Agents](https://papers.nips.cc/paper/2018/file/b1301141feffabac455e1f90a7de2054-Paper.pdf) (Conti et al., 2018)
[^2]: [Deep Batch Active Learning by Diverse, Uncertain Gradient Lower Bounds](https://arxiv.org/abs/1906.03671) (Ash et al., 2019)
[^3]: [Dropout as a Bayesian Approximation](http://proceedings.mlr.press/v48/gal16.html) (Gal and Ghahramani, 2016)
[^4]: [Weight Uncertainty in Neural Networks](http://proceedings.mlr.press/v37/blundell15.html) (Blundell et al., 2015)
[^5]: [Understanding Deep Learning Requires Rethinking Generalization ](https://openreview.net/forum?id=Sy8gdB9xx) (Zhang et al., 2017)
[^6]: [A Closer Look at Memorization in Deep Networks](https://dl.acm.org/doi/10.5555/3305381.3305406)  (Arpit et al., 2017)
[^7]: [Dataset Cartography](https://aclanthology.org/2020.emnlp-main.746/) (Swayamdipta et al., 2020)
[^8]: [Identifying Mislabeled Data using AUM Ranking](https://arxiv.org/abs/2001.10528) (Pleiss et al., 2020)
[^9]: [Local Interpretable Model-Agnostic Explanations (LIME)](https://arxiv.org/abs/1602.04938) (Ribeiro et al., 2016)
[^10]: [Notes on the N-Person Game](https://www.rand.org/pubs/research_memoranda/RM0656.html) (Shapley, 1951)
[^11]: [Data Shapley: Equitable Valuation of Data](https://proceedings.mlr.press/v97/ghorbani19c/ghorbani19c.pdf) (Ghorbani and Zou, 2019)
[^12]: [Efficient Data Valuation for Nearest Neighbor Algorithms](https://arxiv.org/abs/1908.08619) (Jia et al., 2019)