---
layout: post
title: Deep Learning for Recommendation Systems
date: '2016-11-19 00:00:03'
---

[**Wide & Deep Learning for Recommender Systems**](https://arxiv.org/abs/1606.07792)
(*Cheng, Koc, Harmsen, Shaked, Chandra, Aradhye, Anderson, et. al.*)

While deep learning is great for many things, it's progress in recommendations systems has been limited, partially because recommendation systems inherently have a cold-start problem and sparse data, whereas deep learning works best in the regime of data abundance. When applied to sparse data, DL models tend to overfit since it has so much flexibility in the parameters.  Thus, the authors present a model that jointly trains on deep neural nets (for memorization) and wide linear models (for generalization).  

Since there are over a million apps in the database, it is intractable to exhaustively score every app for every query within the serving latency requirements. Therefore, the first step upon receiving a query is limiting the options to a short list of items.  This is done through a combination of statistical-based machine-learned models and human-defined rules. Then the network can do the job of ranking the smaller list of returned app options.  The wide part of the network is just a shallow logistic regression layer.  The deep part is just a feed-forward network.  In the experiments, the authors used Followthe-regularized-leader (FTRL) algorithm with L1 regularization as the optimizer for the wide part of the model,
and AdaGrad optimizer for the deep part.

The exciting part of this model isn't the methods, but the fact that it runs in production. Multi-threading and other scalability techniques needed to be added in order to make sure the model worked within the time constraints (often ~10 milliseconds) for a consumer facing service.  The results show that the model actually drives increased app acquisitions over previous recommendation systems, which means that rather than just beating some benchmark, deep learning actually influence user behavior.

As a side node, since the linear models are used to prevent overfitting, I view this as a form of regularization.  I'm sure there are smarter ways to regularize the output.  The context for these recommendations is the Google Play store where users can download apps to their phone. As a result, the model in the paper seems to look at user features (e.g., country, language, demographics), contextual features (e.g., device, hour of the
day, day of the week), and impression features (e.g., app age,
historical statistics of an app).  But there are dozens more options here. For example,

  1. What page did the user come from
  2. Did they click on an add to arrive
  3. How long did the user stay on the app page
  4. What other Google Play apps has the user downloaded before?
  5. What is their location?
  6. This is Google right? So what pages did they visit on Chrome?What videos did they watch on YouTube? What topics do they discuss in Gmail? What places have they visited in Maps?
  7. We can even explicitly ask the user about their preferences!  What are songs you like to listen to?  What do you like doing for fun?  What kind of food to you like to eat?  Tell me about yourself.

Then, when there is too much data, apply some Variational Dropout or Zoneout to the problem to push the solution to the right space.  The folks at Google aren't doing this, possibly due to privacy concerns, but at the same time, I'm sure at least 1% of the users would be willing to opt in - and at Google's size that means over a million users to test.  Using all the data is so obvious it means Google probably is using it to improve the system, but just hasn't told us yet until the results are noteworthy.