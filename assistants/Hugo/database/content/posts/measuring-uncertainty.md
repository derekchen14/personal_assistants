---
layout: post
title: Measuring Uncertainty
date: '2020-07-29 20:06:00'
---

Compared to typical goal-oriented dialogue systems, interactive dialogue agents not only aim to solve the task at hand, but also engage with the user by asking questions. &nbsp;Questions can be used to push the conversation forward or to spark some new ideas, but for now we will focus on the use of questions to clarify understanding. &nbsp;[Clarification requests](https://www.researchgate.net/profile/Matthew_Purver/publication/236273309_The_Theory_and_Use_of_Clarification_Requests_in_Dialogue/links/00b7d5313817a20f30000000/The-Theory-and-Use-of-Clarification-Requests-in-Dialogue.pdf), as they are referred to in the academic literature, come in many forms, but the key issues to solve are when to ask such questions and in what format. &nbsp;Asking questions too often, or at inappropriate times, causes the conversation to feel disjointed or annoying. &nbsp;Asking the wrong type of question causes the dialogue agent to seem incoherent or useless.

Recognizing [when to ask questions](/deciding-when-to-ask-questions-for-dialogue/) and what questions to ask can be tackled by having a NLU module which has a interpretable and [well-calibrated](https://papers.nips.cc/paper/5658-calibrated-structured-prediction.pdf) measure of uncertainty, often expressed as a confidence score. &nbsp;If the score is low, then the model is uncertain and should ask a clarification question (even if model is unable to generate questions, it should at least abstain from offering any solutions). &nbsp;If the score is higher, then the model is more certain and can ask a different set of questions. &nbsp;Once the score is past a certain threshold, we can deem the model to be confident enough to formulate a reasonable recommendation.

As we study the landscape of options for measuring uncertainty, there seem to be four broad methods of generating confidence scores. &nbsp;Let's examine each one in detail.

### (1) Posterior Probabilities

The most straightforward manner of measuring the model's uncertainty is to [ask the model itself](https://arxiv.org/abs/1805.04604). Namely, a typical classification or ranking problem will have a softmax at the end which represents the $$p(y \mid x)$$ .

<!--kg-card-begin: markdown-->

1A) [Max Item](https://arxiv.org/pdf/2006.09462)  
If the max output of [softmax is below some threshold](https://arxiv.org/abs/1610.02136), then mark the model as uncertain. However, numerous papers have noted that the pure softmax is [largely uncalibrated](https://arxiv.org/abs/1701.06548) and tends to make the model overconfident due to the exponeniating factor. Thus, the uncalibrated logits tend to work better. There are various tricks, [like working with temperature](https://arxiv.org/abs/1706.04599) to improve the calibration, but ultimately, you will still be looking at the likelihood of the model itself.

1B) Top-K Rank  
Rather than depending on just the top item, we can possibly glean some information from the other predictions. For example, we can look at the gap between the confidence score of top two items. If the gap is below some threshold, this indicates low confidence, so we mark the model as uncertain. We can also think of the ratio between the top items instead. If we generalize this further, we can look at the gap between the second and third ranked item or the first and third item. In total, [we can expand this to arbitrary K](https://arxiv.org/abs/1805.04604).

1C) Full distribution  
If we look at the gap between certain items, the signal here is probably diminishing at a certain point. However, looking at the [overall entropy](https://arxiv.org/abs/2005.07174) of the entire distribution can tell us something. Along those lines, we might also want to check the total variance of the softmax/logits.

<!--kg-card-end: markdown-->
### (2) Ensembles

On the topic of variance, ensembles are a method for inducing variance upon our model. &nbsp;Essentially, we perturb the model such that it produces different outputs, and if there is high variance in the outputs, then our model is considered less certain. &nbsp;The intuition is that a more confident model will still make the same prediction even if the input has been slightly shifted since the latent label has not changed.

<!--kg-card-begin: markdown-->

2A) Post-Training  
The most common form of ensemble is one created by [Gal and Ghahramani](http://www.jmlr.org/proceedings/papers/v48/gal16.pdf). In this paper, they propose MC-dropout where random masks are placed on model to simulate dropout at [_test_ time](https://arxiv.org/pdf/2006.09462). This brilliant insight allows us to gain a measure of uncertainty without any extra heavy lifting to come up with a new model. Alternatively, any sort of perturbation, such as gaussian noise or brown noise can be added to the model to see its reaction.

2B) Pre-Training  
Of course, [straightforward ensembles](http://papers.nips.cc/paper/7219-simple-and-scalable-predictive-uncertainty-estimation-using-deep-ensembles.pdf) can also give a sense of the variance of the outputs. This turns out to work better, but at the cost of having to train _M_ models for a better measure of uncertainty. If we are doing all the extra work of training extra models, we don't even have to really restrict ourselves to the same architecture. We could theoretically try M=5 different models and go off the assumption that confident prediction should hold true across all the architectures.

<!--kg-card-end: markdown-->
### (3) Outlier Detection

Another method of predicting uncertainty is to look at other sources of uncertainty. &nbsp;The previous methods roughly falls under the bucket of epistemic uncertainty since they examine how the model performs. &nbsp;Alternatively, we can also study the data for aleatoric uncertainty. &nbsp;This falls under the assumption that the data varies due to natural variation in the system, but should not vary beyond some reasonable bounds. &nbsp;(If this interpretation is totally wrong, feel free to comment below.)

<!--kg-card-begin: markdown-->

3A) Input Outliers  
Although this is a false dichotomy, we can somewhat split up the data based on inputs and outputs. By inputs, we mean looking at the distribution of the data before it is passed into the model. For example, we might look at the n-gram distribution of a sentence and compare that to the n-grams of the average sentence in the training corpus. Additionally, we could [pass an utterance into a Language Model](https://arxiv.org/abs/1805.04604) to get a sense of its perplexity. In both cases, utterances that are "not typical" could be considered more likely to be uncertain, and dealt with accordingly.

Perhaps looking at a datapoint before it is processed is too biased. So as a practical matter, we might say that instead, the pre-computed statistic simply gives us a [Bayesian prior](https://arxiv.org/abs/2002.07965), after which we can use any of the other methods described to get us a better sense of the posterior likelihood of uncertainty. Assuming we are working with sentences, we can examine the prior uncertainty of either the tokens or the sentence as a whole.

3B) Output Outliers  
Moving on to processed data, we can imagine passing the datapoint through our main model to make predictions. If the predicted class itself is rare, this can be a warning signal to [possibly abstain](https://arxiv.org/abs/2006.09462). Of course rare classes do occassionally appear, or otherwise they shouldn't even be considered, so this method shouldn't be taken too far. We could also imagine embedding the data using any embedding algorithm and then clustering the results. Any [embeddings that are not near any known centroids](https://arxiv.org/abs/1803.04765) can then be flagged for review. In this sense, any tool that gives a sense of outlier detection can be used as a measure of uncertainty.

<!--kg-card-end: markdown-->
### (4) Second-order Methods

Finally, we can consider second-order methods where a separate model makes a prediction of the uncertainty. &nbsp; Training a model to do the heavy lifting for us is actually quite ingenious, but perhaps the papers don't think of it this way, so they ironically don't aggrandize this direction as much as some of the papers which proposed the other methods.

<!--kg-card-begin: markdown-->

4A) Reinforcement Learning  
Suppose we want to train a dialogue agent or semantic parser to ask a clarification question when it is uncertain of the situation. Using an RL system, we can instead [have a policy manager decide](https://arxiv.org/abs/1911.03598) when to take such an action, and simply train it with a reward signal. The [REINFORCE algorithm can be used](https://www.aaai.org/ojs/index.php/AAAI/article/download/4101/3979), but certainly the whole back of tricks with RL can be used now as long as we can design some intermediate rewards for the model to follow.

This ends up working quite well for certain problems, but my instinct says that it doesn't work on real-world use cases for all the same reasons why reinforcement learning often fails outside of the simulated scenarios. We could have a model that tries to recognize the domain shift from the simulated enviroment to the real world, but then we start back at square one with some inception style behavior.

4B) Direct Prediction  
If the training data included a not-applicable or [none-of-the-above](https://arxiv.org/abs/2004.01926) option, then we can possibly get a model to choose that when none of the given options fit nicely. The hard part here is that we would need to know the ground truth of when to choose this option, which pretty much never happens unless we perform data augmentation. This gives the original model a chance to decide for itself that it is uncertain, but often does not work that well, especially on out-of-domain predictions.

An interesting line of work might be to handcraft options that are known to be unclear and to also have training examples that can clearly be answered. Efforts such as [AmbigQA](https://arxiv.org/abs/2004.10645) and [Qulac](https://arxiv.org/abs/1907.06554) are in the right direction, but fail to cover the nuance needed to really understand that a topic is unclear. Oftentimes, what might be obvious to one person requires clarification from another person, so the entire dataset is a bit subjective and thus hard to generate at scale. Given the current techniques around crowdsourcing, this is a limitation without any clear solution at the moment.

4C) Predictions on Statistics  
Saving the best for last, one of the most promising methods for generating a confidence score is to develop an [uncertainty predictor](https://arxiv.org/abs/1610.02136) based on dev set. Concretely, we can pre-train some model using the training data (D-train) to see how well it performs. Then because we know the ground truth (either because it was part of the original dataset or because we augmented it), we can say that whenever the original model made a mistake, [the model should have been more uncertain on that training example](https://arxiv.org/abs/2004.01926). To prevent overfitting, we freeze the D-train model and pass in D-dev data into the model for training the predictor. Thus, we train a confidence estimator that can hopefully generalize to example from the D-test distribution.

<!--kg-card-end: markdown-->

<u>Takeaways</u>

As we analyze all these methods of measuring uncertainty, one final thought is to consider how humans know to ask clarification questions. &nbsp; How do or I know that something is unclear? &nbsp;Is it just a feeling? My general thought is that we have a sense of outlier detection when asking questions, but this is only triggered when something is far outside the what we expect. &nbsp;What we expect is measured likely by some external function, which implies some support for the methods under Category Four. &nbsp;

However, the key is that humans have this expectation, a [theory of mind](https://arxiv.org/abs/1902.08355) of the other individual and a general view of the world at large. &nbsp; Building a comprehensive opinion of the world at large is intractable in the near future, but I remain optimistic that perhaps we can get a model to "fake it" well enough that general users either won't notice or won't care.

