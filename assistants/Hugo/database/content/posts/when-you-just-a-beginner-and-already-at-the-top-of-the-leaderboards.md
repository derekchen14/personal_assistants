---
layout: post
title: When you just a beginner and already at the top of the leaderboards
date: '2016-01-31 10:51:43'
---

A couple of days ago, I found out that I had achieved partial Internet fame! Unfortunately, it was for a negative reason due to a simple misunderstanding.  A random person took a screenshot of a Twitter exchange I had with the founder of [Keras](https://twitter.com/fchollet), in which I mentioned being very proud of my high score on a MNIST toy competition.  

The exact transcript (without links) says:

 - *Me:* Jumped to 12th spot on MNIST Digit recognizer #kaggle Not bad for a guy w/o a CS degree, eh? Props to @fchollet #keras
 - *Francois:* @derekchen14 0.998 is pretty good on MNIST.  Is your code on Github? I'd be interested in taking a look at your model.
 - *Me:* @fchollet Sure, [link to github] The "trick" was serendipitously training on 60k samples I found when testing your example code
 - *Me:* So, just luck. Next step is create gridsearchCV method for testing hyperparams.  Will deserve credit only if I get that working
 - *Francois:* that's not luck, that's called training on the test data ..

After the random person posted on Reddit, the story blew up with the context of "a beginner who accidentally trained on the test set had the hubris to brag about the outcome".  The reality is the person who posted the image probably interpreted the tweet as, "I am so lucky to get such a good score", which is not true.  I was not under the impression that I was somehow an expert for getting such a score (nor do I believe I am an expert now).  I knew perfectly well that by using the test data during training, I was more likely to get a higher score during validation. And that's exactly what happened!

Rather, I meant "I am lucky to stumble upon (external) test data which allowed me to (seemingly) get such a good score".  I know such methods wouldn't work in a real competition, but in this instance, I was able to circumvent the Kaggle auto-grader, which I thought was amusing.  This is why I wrote the word "trick" in quotes.  Frankly, this is MNIST! It's a dataset meant for messing around – no one is getting recognition anymore for achieving high accuracies, made through legitimate means or otherwise.

Ultimately, I believe it was a misunderstanding on the part of the Reddit thread to assume they know the full story from just 140 characters.  How does one deal with Internet trolls though?  Well, in my case, it seems the community caught onto a different event a couple of days later. Looking back, I wonder if these people meant to shamelessly ridicule another member of their own machine learning group even if this individual truly did commit the error exactly as accused.  I'd like to believe this was just a lapse in judgement, and when faced with beginners in the future, I hope to have the mindfulness to behave otherwise.