---
layout: post
title: Why Generative Models?
date: '2016-09-08 17:52:00'
---

Recently, there has been a lot of talk around generative models as the next big thing in deep learning.  There are articles about general adversarial networks, variational autoencoders, PixelRNNs, and perhaps some reinforcement learning augmentation.  But why all this sudden interest?  Why not pursue memory networks or other ideas?  I am by no means an expert, but my suspicion is that generative models offer superior context and speed.

To start, there is a very practical aspect to strong generative models because they turn unlabeled data into a useful tool that helps the supervised training portion to run faster. This happens because a model that is pre-trained using generative models have better initialization weights - starting closer to local minima means less road to travel.

More important than faster convergence though is the ability of generative models to (theoretically) lead to better convergence.
In other words, rather than just getting to the answer faster, we actually reach better answers overall, or similar answers with significantly less data than previously possible.

This happens because if a machine has a decent understanding of how the world works, then this context allows the machine to make inferences about the world to give a reasonable responses even in situations if has not previously encountered.  This concept has taken on various names in the past: One-shot learning, Semi-supervised learning, Transfer learning.  For example, from the machine's point of view:

  - When answering a question, I can produce more variety in my responses that are different in syntax yet still similar in meaning.
  - When offering a recommendation, I can offer choices that are novel yet reasonable because I have established concepts that are useful for reasoning and decision making
  - When classifying news, I can label snippets that have no words in common with the snippets found in my corpus
  - When listening for an input, I can understand different phrases that I have not heard in training
  - When recognizing objects in an image or video, I can make better predictions because I have a deep understanding of objects in the world and their factors of variation.  Concretely, since I know the essence of a car, I am not confused and can easily recognize a car even when if the car is viewed from different camera angles or painted a different color.
  - When generating new images, I can imagine the parts of the image that were originally occluded from view or otherwise damaged
When tracking events, I can detect anomalies since I have a good understanding of what is normal vs. surprising.

Thus, while generating jazz songs or Van Gogh style paintings is certainly entertaining, the true benefit of generative models is allowing practitioners to move more efficiently and effectively than ever before.  At least that is my opinion from an outsider's perspective - would love to hear an expert's thoughts on the subject!