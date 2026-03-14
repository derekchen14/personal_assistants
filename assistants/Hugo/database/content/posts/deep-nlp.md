---
layout: post
title: Deep NLP from Deep Learning Summer School
date: '2016-09-16 22:18:21'
---

*Notes from Kyunghyun Cho's lecture during Montreal's Deep Learning Summer School*

### Language Modeling
What does it mean to build an agent that can understand natural language?  It just means building a better language model.  Widely adopted approaches include:

  0. **Linguistics** - use theory and structure inherent in a language to model understanding:
   - The input question uses X syntax and Y grammar, so it must mean Z.
   - Problematic because language is too fluid and the "rules" for English are not very rigid. Perhaps more accurately, the rules for English are not followed very rigidly.
   - This is especially true in the age of the internet and tweets when highly unstructured text is being generated at an astounding rate.  The data does not represent formal English sentences, so trying to interpret the snippet as a normal sentence just falls apart.
  1. **N-grams** - use statistical phenomenon to predict what a sentence means:
   - What is the probability of output response Y given the input question X?
   - Using conditional probability, now you can simply model the sentence by trying to maximize the expected (log) probability of a series of words.  i.e. What is the probability of each words given the probability of all the words that came before it?
   - N-grams simplifies the model a bit by saying rather than looking at *all* previous words, let's just look back at n previous words, so if n = 5, then we only look back at the last 5 tokens preceding the word we are trying to predict
   - Process - collect lots of n-grams from a large corpus
unigram - only look at the single word, assumes all words are independent
     - bigram - look back at the one word
     - trigram - look back at the last two words
     - 4-grams - look back at the last three words
     - 5 -grams - look back at the last four words, etc.
   - The problem is that if a certain sequence never occurs in the corpus, then that particular n-gram product goes to 0 because multiplying anything by 0 goes to 0.
   - For example, let's say you are using a trigram model
You are trying to predict the likelihood of p(we, were, on, fire, last, night)
   - This is the product of the probabilities: 
     - p(*we*) x p(*were*| *we*) x p(*on*| *we, were*) x p(*fire* | *were, on*) x p(*last*| *on, fire*) x p(*night*| *fire, last*)
   - Let's make the reasonable assumption that the phrases "we were on", " we were" and "fire last night" all have high likelihood of occurring.
   - However, let's also assume that "on fire last" was never in the corpus, then p(x) = 0%. Now the entire sentence is rated as 0% even though the other phrases have high chance of occurring.
   - No matter how big your corpus, it won't cover all examples, so there is a Data Sparsity problem.
   - To over come this issue, conventional solutions include:
     - **Smoothing** - never allow a trigram to go to 0% by always adding some small epsilon (~0.01%)
     - **Back off** - even though you are supposed to look back at last two words for a trigram model, you limit yourself to only looking at last one word iff the last two words returns 0% probability or no words, if the last one word still returns a 0% probability
   - This is still unsatisfactory because there is still a lack of generalization.  For example, assume that the corpus includes
(chases, a, dog) (chase, a, cat), (chases, a, rabbit) but does not include (chases, a, llama).
   - Even after applying the smoothing or backoff, you still have either 0% or at the best, a workable suboptimal model. Thus, we move onto more sophisticated models ...
  2. **Feedforward neural nets** - use a parametric function approximator, which is to say we take a linear combination, but then we weight each factor differently according to their importance:
    - Process:
      - First, create vector embeddings using one-hot encoding
      - Then join these to create a continuous-space word representation
      - This goes into any number of non-linear representation (a tanh or ReLU), aka an activation function
      - then finally a softmax for prediction
    - To see why this model in an improvement, let's look at an example.  Assume that your corpus includes three sentences:
      - "there are three teams left for the qualification"
      - "four teams have passed the first round"
      - "four groups are playing in the field"
    - How likely is "groups" followed by the word "three"?
    - Under the normal n-gram model, the answer would be 0% chance since the phrase "three groups" has never occurred in the corpus.
      - This can be done a little smarter using NER and replacing "three" with 3, "four" with 4, and then tagging both as numbers.
      - Then tagging people, places, things in a similar fashion.
      - This is essentially make n-grams smarter by using feature engineering to add an extra layer of meta-data during training.
      - At the end of the day though, this is still suboptimal method of representing the language space. Just as decision trees can be augmented with dozens of extra tweaks, sometimes its best to just move onto another algorithm.
    - In this case, the neural network model has a strong advantage because doesn't follow a strict multiplication of seen vs. unseen occurrences.  In particular, the softmax calculates a non-linear, normalized probability that is optimized through a cost function (or optimization function)
    - This cost function calculates a soft distance between predicted (y-hat) vs actual (y).  Most importantly, these penalty "costs" are SUMMED together, rather than multiplied.
    - Thus, wildly off prediction are heavily penalized, but never pushed the probability to zero.
    - The distance of these items are normally based off the euclidean distance of the vector embeddings.  (Surprisingly, even just a matrix factorization with SVD or PCA of simple one-hot encoding can get reasonable results).
    - So from our example, we will see that "three" will be projected to a space close to "four" because "three teams" and "four teams" are both phrases that occur.  And since the phrase "four groups" also occur, the measure associated with "three groups" becomes more likely (and certainly non-zero).
    - Of course, even smarter vector embeddings such as word2vec will often yield even better results.
    - Altogether, this means that Neural Nets can be great for generalization, while non-parametric approaches (i.e. n-gram modeling) can often be great for memorization of the data.
      - One way to inspect this progress is to visualize the word space, using techniques such as t-SNE
      - We saw that this vector really convinced others of the efficacy of the model
  3. **Recurrent Modeling** (aka. Neural Machine Translation) - breaks from the Markov assumption of looking at the n-grams before a word (t-4) to predict the current word (t), which has a core issue that dependencies beyond the context window are ignored.
    - For example, "The bright red umbrella which had been left at the restaurant over the last four weeks was finally returned to its owner who used it immediately for cover from the rain."
    - In this sentence, we learn that an "umbrella" is a type of object that can be used for "cover", but the distance between the two words is so high that the relationship is never derived.
    - We made this simplification to ease our training, but if we train through another method, then perhaps this simplification is no longer necessary.
    - One way is to extend the length to much longer 5 --> 32 --> 64.  And then apply zero-padding to get the lengths of all words to be relatively similar.
    - An even better way is to use a RNN, namely a recurrent neural net.  An RNN allows the user to input one word at a time, and at each time step the function approximator takes into account the current word, but also the interactions of all past words
    - In this way, rather than feeding in a continuous concatenated word vector, we feed in one word at a time.  Similar to how CNNs give an advantage over vanilla NNs by taking spatial information into consideration, RNNs give an advantage over vanilla NNs by taking temporal ordering into consideration.
    - It keeps track of weights using (h_t), which is calculated by each cell unit, and then passed back to the same cell unit in the next time step.  This internal hidden state is also referred to as the memory of the network.  Not to be confused with attention (Bandahau) or storage (Graves).
    - Recursion example: p(*eating*|*the, cat, is*)
      - (1) Initialization: h0 = 0
      - (2) Recursion:
         - h1 = f (h0, the)
         - h2 = f (h1, cat)
         - h3 = f (h2, is)
      - (3) Readout: p(*eating*|*the, cat, is*) = g(h3)
    - Recurrent neural network example: p(*eating*|*the, cat, is*) - same as above except the function (f) is a neural network, the final result is just the product of each output
      - (1) Initialization: h0 = 0 --> p(the) = g(h0)
      - (2) Recursion with Readout:
         - h1 = f(h0, the)  --> p(cat|the) = g(h1)
         - h2 = f(h1, cat)  --> p(is|the, cat) = g(h2)
         - h3 = f(h2, is) --> p(eating|the, cat, is) = g(h3)
      - (3) Combination: p(the, cat, is, eating) = g(h0) g(h1) g(h2) g(h3)
   - Finally, in both example, you Read, Update, Predict next time step (until we predict a EOF token).
   - Now this is just a LSTM or GRU, that takes care of the vanishing gradient problem.  (Recall: you can just do gradient clipping to avoid the exploding gradient problem)

### Probability 101
  - Phrases > words > characters > bytes
  - Joint probability p(x, y)  - chance that both occur at the same time
  - Conditional probability p(x|y) - chance that X occurs given Y occurred
  - Marginal probability p(x) and p(y) - after removing the effect of the other variable, what is the effect of the remaining variable
  - Related by p(x, y) = p(x|y) p(y) = p(y|x) p(x)

### Continuous Space Representations (CSR)
Definition - the RNN for translation uses an encoder to push the original sentence into a continuous space representation.  Then a decoder is used to extract meaning back out into another language.

New opportunities in NLP based on Neural Nets.  Originally we were worried that:
  
1. We strongly believe that a word (lexeme) is a basic unit of meaning.
2. We have an inherent fear of data sparsity. 
3. We are worried that we cannot train a recurrent neural net because stuff is too big.  For example, the size of state space grows exponentially w.r.t. the length. Or a sentence is longer when counted in letters than in words.

But it turns out that none of these fears were legitimate:

1. This one is questionable to begin with since language is fluid
2. Data sparsity is not such a big deal when your word representation is a smooth vector embedding that can use distances to calculate differences rather than raw probabilities
3. Back then, the tech was not as good, but now we have GPUs and GRUs.  Thus, the benefits of training based on character level translation (more data) starts to outweigh the pitfalls of training on such granular data.

This is useful for many reasons.  Only English has spaces and clear "words".  In Arabic, there are single "words" that mean "and to his vehicle"  In Chinese, many ideas are represented by two "word" phrases  In Finnish, one word "three" is strictly less than a compound word "three thousand kilowatts per hour"

Put another way, words were never the most ideal representation of language.  Breaking down further always gives more accuracy, but technical constraints held this back.  Now that we no longer have these technical constraints, we should go ahead and dig deeper down into the character level.

NLP is easier now since word segmentation (a.k.a. tokenization) is no longer needed.  Furthermore, we don't even need to do this on the source (or target) side either.  The model just knows how to string together characters to make up words!