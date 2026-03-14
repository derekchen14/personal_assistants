---
layout: post
title: ML as Software 2.0
tags: [thoughts, trends]
excerpt_separator: <!--more-->
---

We've heard from Andrej Karpathy that ML is software 2.0.  But what does this mean on a practical level.  We know it is different, but if (as a company) we want to embrace this difference, what should we do?

Perhaps a key, understudied aspect of machine learning is data strategy.  As an analogy, consider a comparison to web development as Software 1.0.  To start, both areas had a lot of hype required some time to really mature and understand.  In moving from desktop publishing to the web, developers needed to adopt a new mindset around iterative development of software.  Whereas strict and rigid frameworks were needed for the writing desktop software, this was no longer needed for the web.  When shipping shrink-wrapped software, you had better be certain the code is right the first time, but when shipping to the web, you can update the code on the server and the end-user simply refreshes their browser to get the latest version.  Thus, many people thought choosing the right JavaScript framework or other rigid structures were needed to build solid websites.  But it turns out developers can be a lot more flexible and any number of frameworks or pipelines are viable.  Rather, having solid unit tests, version control and having methods for quickly adapting were what ruled the day.

Once again, as we are witnessing the adaption to a new medium.  As usual, we still have lots of people arguing over which framework (PyTorch, TensorFlow, JAX, etc.) is the best.  And we also have people debating which models are most critical.  But these are all about writing code.  Instead, the key differentiator of Machine learning is in what kind of data you feed into the model.

If this is true, then there should be massive amount of research into what type of data is most suited for best performance.  What is quality data and how can we gather that at scale?  Given a finite budget, what is the trade-off between quality of versus quantity of data.  But we don't really see this.  Part of the reason is that annotating data can be some expensive and it's much easier to rely on unsupervised pre-training.  But then again, doesn't that just warrant increased research into how we can annotate training data with higher efficiency?  Perhaps, it is seen as too boring or not publish-worthy.  In any case, seems like a great area in which to gain an expertise 😉
