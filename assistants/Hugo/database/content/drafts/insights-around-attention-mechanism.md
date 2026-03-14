---
layout: post
title: Insights around Attention Mechanism
---

The attention mechanism is used in all sorts of deep learning tasks, most notably Neural Machine Translation (NMT).  Some thoughts on how it works:


 * *Attention vector replaces the input vector* - A LSTM cell takes in (a) input vector (b) hidden state vector and (c) cell state.  In the first time step, the hidden state vector is the final encoder output.  The attention vector does _not_ replace this hidden vector, but rather the input vector of each word.
   - Intuitively, this makes sense because the input word doesn't carry much info, so we would rather keep around the context vector to make the prediction.  For example, suppose the target sentence is "I like to eat cookies ." and we have predicted [I, like, to], then the input word is "to", from which we would like to predict "eat".  However, that's not much to go by, so replacing "to" with our attention vector seems beneficial.    This is more apparent in the degenerate case during the start of predictions, when the input is just <SOS>. Now, suppose this were not the case, and instead we replaced the hidden state vector, then we would lose all the information about the previously predicted words and the original context, which seems like bad times.  Thus, we replace input vector.
  - Mechanically, this also makes sense because LSTM includes the cell state.  If we were replacing "information that gets passed through time", then we would want an attention vector for both hidden state and cell state.  This is not the case, so once again what we replace is the single input vector.
  - Diagrammatically, this is also the case.  Look at the picture from the original paper: https://arxiv.org/abs/1409.0473
![attention](http://d3kbpzbmcynnmx.cloudfront.net/wp-content/uploads/2015/12/Screen-Shot-2015-12-30-at-1.16.08-PM-235x300.png)
 * *Importance* - 
 * *Importance is in how attention weights are generated, not how they are applied* - The attention weights are not a big matrix that forms a complicated calculation with the encoder outputs, but rather just a linear weighting that tells you where to look that is the same size as in the input.  So if the input is a sentence with 9 words, then there are only 9 weights, not 9x128 where 128 is the word embedding size. The magic comes from the interaction between the decoder hidden state and the decoder input, not from the interaction between the attention weights and the encoder output.