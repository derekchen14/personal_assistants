---
layout: post
title: Optimizing RecSys Training
date: '2016-06-23 16:25:14'
---

Given the goal of creating an optimal recommendation system, one could consider using a neural turing machine (NTM) with a "programmable" head performing read/write operations on the various inputs in order to generate a prediction.  The inputs would be encoding of the situation (shopping for clothes), encodings of the options (sweater, jacket, T-shirt, dress shirt) along with their features of those options (blue/green, soft, polyester, wool), tons of other previously collected data points, and obviously a vector embedding of the individual for whom we are making the recommendation.  The predictions would just the result of softmax classifier with thousands of possibilities, each one representing a cluster of clothing items.  (There is no need to recommend just one item because eve a mobile UI can display 7-10 items fairly easily to let the customer make the final decision.)

Proposed idea for optimization is rather than using (and training) a traditional controller to adapt to different user profiles, why not try a pub-sub model instead?  First, note that explicitly training a controller is hard, needs millions of examples, and thus takes a long time.  Additionally, "user preference" vectors (possibly created through word2vec or GloVE mechanisms) might change over time -- should change over time -- because people's tastes evolve as they mature.  This makes training on these vectors nearly impossible even with massive collaborative filtering databases full of anonymized data.

As such, diffs on the user preference vectors (UPV) will signal when a change has occurred, similar to how Google Docs passes diffs around for real time editing of documents.  These UPVs essentially become event emitters publishing their changes to a centralized listener (CL) that subscribes to all sorts of changes.   The CL is then trained through gradient descent to react appropriately.  This simplifies the problem because rather than training on a unique result for each user, you train on the unique action to take for each given input.  

Since a population of shoppers on a whole are similar, the number of actions they take (or moods they exhibit) can be efficiently clustered into a reasonable amount of inputs that a deep neural network can accommodate.  Each population of shoppers will need new training (since different stores offer different products, and the buying behavior of buying shoes is different than buying homes), but this allows for much more effective direct scaling.  By direct scaling, what I mean is that the CL does not have to be trained at once for all things the user might buy (because the training takes into account UPV but does not depend directly on them.)  Rather the CL is trained on a certain population of buyers, and can then scale to other buyers are new companies are added into the mix.  Although this particular pub-sub method might not end up being correct, the ability to arbitrarily scale up and down is essential because business partnerships will come (and go) for reasons completely unrelated to data or technology.

Overall, the idea here is to use lightweight components (inspired by Smalltalk) to communicate changes, and train off of those changes rather than monolithic feature vectors.







