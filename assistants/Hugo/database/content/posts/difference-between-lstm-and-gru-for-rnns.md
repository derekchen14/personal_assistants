---
layout: post
title: Difference between LSTM and GRU for RNNs
date: '2016-02-19 15:25:00'
tags:
- modeling
---

So if you've started studying RNNs, and you heard that LSTMs and GRUs at the type of RNNs you should use because vanilla RNNs suffer from the vanishing gradient problem.  That makes sense because the hidden state is passed along for each iteration, so when back-propagating, the same Jacobian matrix is multiplied by itself over and over again.  If that matrix has a principal eigenvalue less than one, then we have a vanishing gradient.  Incidentally, if the matrix has a principal eigenvalue greater than one: exploding gradient.

To solve this problem, we would like to have gradient values that persist as they go flow backward.  And this is exactly what LSTMs do - they have a cell that stores the previous values and hold onto it unless a "forget gate" tells the cell to forget those values.  LSTMs also have a "input gate" which adds new stuff to the cell and an "output gate" which decides when to pass along the vectors from the cell to the next hidden state.  

Recall that with all RNNs, the values coming in from `X_train` and `H_previous` are used to determine what happens in the current hidden state.  And the results of the current hidden state (`H_current`) are used to determine what happens in the next hidden state.  LSTMs simply add a cell layer to make sure the transfer of hidden state information from one iteration to the next is reasonably high.  Put another way, we want to remember stuff from previous iterations for as long as needed, and the cells in LSTMs allow this to happen.

At a high level, GRUs work the same way.  They take `X_train` and `H_previous` as inputs.  They perform some calculations and then pass along `H_current`.  In the next iteration `X_train.next` and `H_current` are used for more calculations, and so on.  What makes them different from LSTMs is that GRUs don't need the cell layer to pass values along.  The calculations within each iteration insure that the `H_current` values being passed along either retain a high amount of old information or are jump-started with a high amount of new information. 

In the diagram below of a LSTM network, each block has two parallel lines going in and out.  The top line is the cells, the bottom line is the hidden state information.  Finally, there is a third line going in from the bottom, representing X.  In total, three inputs and two outputs. X*t*  would be `X_train`, h*t-1*  would be `H_previous`, X*t+1*  would be `X_train.next`, and h*t*  would be `H_current`. 
![LSTM](/content/images/2016/03/LSTM3-chain.png)

In contrast, a GRU network only has two inputs and one output (and no cell layers):
![GRU](/content/images/2016/03/gru.png)

*Images taken from [Understanding LSTM Networks](http://colah.github.io/posts/2015-08-Understanding-LSTMs/)*

As with all intuitive/simplified explanations of complex subjects, please take with a grain of salt. Many important details have been left out.  If something I stated above is flat out wrong though, please comment and I will update - I am still learning as well.