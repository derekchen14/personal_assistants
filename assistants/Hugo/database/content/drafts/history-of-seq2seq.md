---
layout: post
title: History of Seq2Seq
---

Even though deep networks have been successfully used in many applications, until recently, they
have mainly been used in classification: mapping a fixed-length vector to an output category [21].
For structured problems, such as mapping one variable-length sequence to another variable-length
sequence, neural networks have to be combined with other sequential models such as Hidden
Markov Models (HMMs) [22] and Conditional Random Fields (CRFs) [23]. A drawback of this
combining approach is that the resulting models cannot be easily trained end-to-end and they make
simplistic assumptions about the probability distribution of the data.
Sequence to sequence learning is a framework that attempts to address the problem of learning
variable-length input and output sequences [17]. It uses an encoder RNN to map the sequential
variable-length input into a fixed-length vector. A decoder RNN then uses this vector to produce
the variable-length output sequence, one token at a time. During training, the model feeds the
groundtruth labels as inputs to the decoder. During inference, the model performs a beam search to
generate suitable candidates for next step predictions.
Sequence to sequence models can be improved significantly by the use of an attention mechanism
that provides the decoder RNN more information when it produces the output tokens [16]. At each
output step, the last hidden state of the decoder RNN is used to generate an attention vector over
the input sequence of the encoder. The attention vector is used to propagate information from the
encoder to the decoder at every time step, instead of just once, as with the original sequence to
sequence model [17]. This attention vector can be thought of as skip connections that allow the
information and the gradients to flow more effectively in an RNN.
The sequence to sequence framework has been used extensively for many applications: machine
translation [24, 25], image captioning [26, 27], parsing [28] and conversational modeling [29]. The
generality of this framework suggests that speech recognition can also be a direct application [14,
15].