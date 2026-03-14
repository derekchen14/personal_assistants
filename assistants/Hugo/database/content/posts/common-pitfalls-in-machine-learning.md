---
layout: post
title: Common Pitfalls in Machine Learning
date: '2015-09-16 01:44:45'
tags: [machine-learning, research]
---

Machine Learning is hard because:

  - it requires a multitude of skills – data extraction, analytical data processing, choosing features, data munging, programming, data visualization, some domain knowledge, statistics, linear algebra, etc.
  - higher dimensionality reduces the ability for intuition to guide the process
  - feature engineering is an art/black magic with no absolute right answer

Perhaps the most difficult aspect is deciding where to focus your energy.

 - Choosing a clever algorithm might not always be the best answer because that algorithm requires orders of magnitude more data to perform better than a more naive learner.  Do you spend your time building a fancy algorithm, looking for more data or finding a faster computer?
 - Choosing the right representation (kNN, Naive Bayes, Logistic Regression, Neural Nets, Decision Trees, etc.) is only one part of the picture.  You also need to consider the right Evaluation technique (precision and recall, posterior probability, information gain, margin, least square error, etc.) and the right Optimization method (greedy search, gradient descent, constrained continuous optimization, beam search, etc.).  Do you spend your time on representation, evaluation or optimization?
 - Due to the curse of dimensionality, it is often better to keep the feature sets simple, which makes the system easier to understand and run faster on future iterations.  Do you spend your time engineering more features hoping to find a global minimum, or recognize that what you’ve got at the local minima might be good enough.

Practical advice.  To the extent it makes sense, always try to:

 - perform cross-validation to prevent variance (overfitting) and bias (underfitting)
 - create ensembles since they usually improve the accuracy of your results
look at all the different factors and trade-offs before diving into code