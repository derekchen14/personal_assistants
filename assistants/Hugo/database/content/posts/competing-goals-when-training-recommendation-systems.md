---
layout: post
title: Competing Goals when Training Recommendation Systems
date: '2016-08-29 03:08:03'
---

Although not intractable, the problem of training recommendation systems includes many difficult components that must be resolved in order to have practical use in the real world.  Based on my current understanding, there are three separate problem domains:

  1. **Memorization** of explicitly stated user preferences
  2. **Generalization** to unseen examples not found in the dataset
  3. **Exploration** of new option spaces that the user might like

The ultimate goal of coming up with the best recommendation is especially difficult because these sub-goals are often at odds with each other such that  generating the "right answer" can change based on something as capricious as the user's mood.  In particular, let's take an example of recommending desserts to a user.  For the first situation, the best recommendation for the user might be to offer a Option A (i.e. strawberry cheesecake) because they are in a straightforward typical mood.  In another situation, the best recommendation for the user might be to offer Option B (i.e. blueberry cheesecake) because the restaurant doesn't offer strawberry cheesecake, so a different, but similar dessert should be recommended.  Finally, in a third situation, the best recommendation for the user might be Option C (i.e. Tiramisu) because the user is feeling particularly adventurous that day and wants to try something new.  This is all to say, there is no one right answer which makes training decidedly more difficult.

If we build a neural network large enough and wide enough, this largely resolves the problem of memorization.  However, training times starts to take too long and the systems starts to overfit.  Regularization can get us back to a state of good generalization, but the problem of exploration still remains.  Sometimes, when the network "messes up", the outcome might actually end up being good because the user appreciates well-timed moments for trying novel options. 

One possible way to model this is potentially use neural turing machines to handle the Memorization issue by taking advantage of explicit storage capabilities.  Then similar to an LSTM, there are forget gates that "randomly" drop in the optimal output in favor of a slightly different option.  This would work such that for a random percentage of outputs, the NTM outputs a different recommendation than the conservative best guess.

Next, using variable rewards feedback signals from reinforcement learning, the algorithm can once again be trained through gradients to update the "likelihood to forget" mechanism.  Once again, the training must be done through variable rewards, rather than explicit "right/wrong" classification because in the real world, even suboptimal recommendations (i.e. Rocky Road ice cream) still yields marginal utility for the user.   Thus, the algorithm should not try model an exact right answer, but rather it should focus on maximizing the reward, or overall utility, to the end user.

### Forgetting the Future

Collaborative Filtering and Deep Learning both already have methods for dealing with Generalization, so I would view balancing these needs with Exploration as probably the trickiest part.  If there are readers who believe this is a "solved problem", I would love to hear in the comments since I could definitely be missing something.

With that as the background, the most important question in my mind is what are the details of the "forget mechanism" as outlined above?  First, note that randomly choosing to forget the optimal output and then using policy gradients to slowly update the model is probably not the most ideal strategy because we aren't being very smart about how we initialize the random value.

As we've seen with Batch Norm, Glorot Initialization, Adagrad,  and other optimization methods, where we start and how we make updates can cause meaningful improvements in our outcomes.  To that end, perhaps rather than just forgetting at random, we can be a little smarter about it by using genetic algorithms that randomly choose what to let through, but are more sophisticated in figuring out what combination of options are allowed to "breed" into the next generation. Since the output head follows a slightly different policy than the input head, the chosen model must be flexible enough to train those two aspects separately, which explains why I chose a Neural Turing Machine rather than a relatively simpler Attention Mechanism for remembering long-term dependencies.

At the same time, using a Genetic algorithm might actually be an atrocious idea because we lose the end-to-end gradient descent benefits that are so useful in training.  However, this is where the reinforcement learning comes in.  Just as we are able to reinforcement learning to translate hard attention models into fully trainable soft attention models, we might use a similar technique for "smoothing out" the process of training genetic algorithms.

### Final Thoughts

There are still some huge holes with this process, but hopefully it covers many of the practical aspects of training deep learning recommendation systems, namely how to deal with the competing goals when finding the best recommendation at a given point in time for a given user at scale.  Some other ideas also come to mind to improve the output.  Specifically, putting together an ensemble of such systems, and/or combining with manual human oversight will probably produce better results.  However, these tweaks do not detract from the general hypothesis so the debate of their merits can be saved for a later discussion.
