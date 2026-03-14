---
layout: post
title: Tiling Tensors in PyTorch
date: '2019-03-11 19:06:59'
---

Suppose you had sample = tensor([[3,5,4] &nbsp; [0,2,1]])

Then these will all return the _exact_ same output:

- sample.repeat(2,1)
- sample.view(1,-1).expand(2,-1).contiguous().view(4,3)
- sample.index\_select(0, tensor([0,1,0,1])
- torch. cat( [sample, sample], 0 )
<!--kg-card-begin: markdown-->

Explanations

- Repeat - this is the correct tool for the job
- Expand - meant for expanding a tensor when one of the dimensions is a singleton
  - in other words, if the sample is (4,1) and we want to repeat (4,3)
  - we should use sample.expand(4,3) and not sample.repeat(1,3)
- Index Select - meant for re-ordering the items in a tensor
  - so we might have a tensor that was shuffled, and we want to shuffle it back into place
- Concat - meant for joining together two different tensors
  - also, do not confuse with torch.stack, which would add an extra dimension
  - concat a list of four 2x3 matrices and you will get 8x3 back
  - stack a list of four 2x3 matrices and you will get 4x2x3 back
<!--kg-card-end: markdown-->