---
layout: post
title: L1 vs. L2 Regularization
date: '2016-10-17 06:05:27'
---

It's straightforward to see that L1 and L2 regularization both prefer small numbers, but it is harder to see the intuition in how they get there. 

Specifically, the L1 norm and the L2 norm differ in how they achieve their objective of small weights, so understanding this can be useful for deciding which to use..  On the one hand, L1 wants errors to be all or nothing, which leads to sparse weights since all the errors are concentrated in one place.  As a simple example, let's say there are six weights, then L1 = |0|+|0|+|0|+|-3|+|0|+|1.8| = 4.8, or alternatively, L1 = |0.7|+|1.1|+|-0.6|+|0.9|+|0.7|+|-0.8| = 4.8.  For L1 Norm, they both look about the same, and generally will lean towards the former.

% Testing LaTeX

\sqrt{x^3}
$\sum_{i=0}^n i^2 = \frac{(n^2+n)(2n+1)}{6}$

On the other hand, L2 wants *all* errors to be tiny and heavily penalizes anyone who doesn't obey.  Looking back the at the our example, L2 = sqrt(0<sup>2</sup>+0<sup>2</sup>+0<sup>2</sup>+3<sup>2</sup>+0<sup>2</sup>+1.8<sup>2</sup>) = 3.5, or alternatively, L1 = sqrt(0.7<sup>2</sup>+1.1<sup>2</sup>+(-0.6)<sup>2</sup>+0.9<sup>2</sup>+0.7+(-0.8)<sup>2</sup>) = 2.  In this case, the L2 norm would clearly prefer the dispersed smaller values in the latter distribution.  

In summary, L1 = sparse weights, L2 = small distributed weights.

Reference: https://www.quora.com/What-is-the-difference-between-L1-and-L2-regularization, https://www.quora.com/When-would-you-chose-L1-norm-over-L2-norm