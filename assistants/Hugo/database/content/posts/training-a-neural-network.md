---
layout: post
title: Training a Neural Network
date: '2016-10-22 17:37:58'
---

`(aka. Living a Successful Life)`

One way to look at training a neural network is that you are minimizing a cost function to increase accuracy.  This is done through gradient descent, not trying to calculate the hessian.  Because the overall search space is non-convex and complicated. 

`One way to look at trying to live a successful life is that you are minimizing the resources you spend (e.g. time and money) to increase your happiness. This is done through getting better every day, not trying to have a master plan for life. Because the overall experience of life is constantly changing.`

There are some standard procedures people agree on.  Such as more layers and more units is generally better.  Sometimes a network even has 1000s of layers, which might be overkill, but certainly 100 layers is better than 10, and 10 layers is better than 1 - that's the whole point of deep learning right?

`There are some standard procedures people agree on.  Such as more schooling and more degrees is generally better.  Sometimes a person might even have PhD, which might be overkill, but certainly a masters is better than an undergrad degree, and an undergrad degree is better than a high school diploma - that's the whole point of education right?`

But common sense is never where people like to focus.  Most people like to tweak mini-batch sizes and testing 10 new features to improve your word embeddings (positional encoding, topic modeling, n-gram statistics, matrix factorization, etc.), even though the real gains come in gathering and pre-processing data rather than trying to build a fancier model - i.e. the dirty work.

`But common sense is never where people like to focus.  Most people like to go to self-improvement workshops or read 10 ways to hack your productivity, even though the real gains come from putting in the hard work rather than trying to take shortcuts - i.e. the dirty work.`

People like to focus on optimization techniques (Adam, Adagrad, Momentum), but honestly plain SGD with mini-batches works perfectly fine most of the time. This is because the majority of the work comes during the training, not whether you chose the right optimizer.

`People like to focus on optimization techniques (Pomodoro, GTD, Kanban), but honestly just setting goals and then doing them works perfectly fine most of the time. This is because the majority of the work comes during the execution of the task, not whether you have a fancy todo-list app.`

What are some gains that are truly worthwhile?  Well, we've seen that proper initialization is pretty critical.  But the "right way" to initialize is really to just have random weights centered on the mean.  In other words, you know you can't set everything to zero, but that doesn't necessarily mean you know where to start either.

`What are some gains that are truly worthwhile?  Well, we've seen that choosing the right career that you're passionate about is pretty critical.  But the "right way" to start your career is really to just try random activities centered around your interests.  In other words, you know you can't just sit on the couch all day, but that doesn't necessarily mean you know where to start either.`

One way to start at good initialization is through pre-training.  This alternate task isn't your final goal, but it points you in the right direction.  And on the topic of initialization, we can't forget the benefits of batch norm in starting each layer the best way possible.  You can start with VGG-net if you really want, but that jolt from transfer learning will only take you so far.  Eventually, your model needs to do some learning for itself. Finally, let's not forget about dropout.  It's like building an ensemble of multiple networks and getting the best experiences of every network involved. 

`One way to make sure you are starting the right career is through internships.  This alternate task isn't your final goal, but it points you in the right direction.  And on the topic of initialization, we can't forget the benefits of a good night's sleep to help starting each day the best way possible.  You can drink all the coffee you want, but that jolt of caffeine will only take you so far.  Eventually, you need to do just grind through some long nights yourself. Finally, let's not forget about learning from other's mistakes and mentors.  It's like building an ensemble of multiple lives and getting the best experiences of every person involved. `

Even with all these tips and tricks though, sometimes you just need to restart the whole training process with a new model.  

`Even with all these tips and tricks though, sometimes you just need to restart the whole growth process with a new career.`

Hopefully, you understood your situation well enough to not require such a drastic change as going from a CNN to a LSTM, but maybe you need to make a more subtle change from a 3-layer bi-LSTM with character inputs into a 2-layer GRU with morpheme inputs. 

Let's be honest though, even the more "subtle" change is really difficult, and often requires a completely new set of hyper-params, so that means a completely new grid search process.  This is not to mention that re-training itself takes a long time, even if you happened to magically have all the right params from the start.

`Hopefully, you understood your situation well enough to not require such a drastic change as going from a being a doctor to being an engineer, but maybe you need to make a more subtle change from a web developer focused on e-commerce into a systems engineer focused on healthcare.`

`Let's be honest though, even the more "subtle" change is really difficult, and often requires a completely new set of industry connections, so that means a completely new networking period to meet people.  This is not to mention that building credibility in a new field itself takes a long time, even if you happened to magically have all the right skills for the job from the start.`

So what happens?  Most people just pick a standard off-the-shelf model and start training.  And if their test accuracy is low, they complain about their slow CPU (eg. if only I were rich enough to afford a GPU) or try to redirect people's attention to their amazing validation accuracy (or even their train accuracy if they're desperate).  Thus most results end up being very average.

But you already have a NIPs conference to attend and the deadline for submitting a paper is coming soon.  Plus, you just received that new research grant, and the committee is expecting some results soon, so right now isn't really the time to rock the boat.

`So what happens?  Most people just pick a safe career and start getting promoted.  And if their success is poor, they complain about their unreasonable boss (eg. if only I were rich enough to quit immediately so I could look for a new job) or try to redirect people's attention to their amazing college years (or even the glory days of high school if they're desperate). Thus most lives end up being very average.`

`But you already have a mortgage to pay and that deadline for figuring out your health insurance is coming soon.  Plus your wife is 8-months pregnant, and the baby is expected to come out any day now, so right now isn't really the time to rock the boat.`

Starting from the bottom again is just way too painful and time consuming.  The model I have now isn't horrible - my current perplexity score is certainly nothing to be ashamed of.  There's no point in trying to compete with Jeff Dean, that guy knows everything.

`Starting from the bottom again is just way too painful and time consuming.  The career path I have now isn't horrible - my current salary is certainly nothing to be ashamed of.  There's no point in trying to compete with Jeff Dean, that guy knows everything.`

So, stop.  This is where you have to ask yourself "Are you really satisfied with where you are?"  Sure, not everyone can get state-of-the-art results, but have you actually collected all the data that you could before giving up?  Is it really too late to start with a new model?   Maybe getting this done right isn't about just trying to just beat current benchmarks by 1.2%.  Maybe you need to stop comparing yourself to everyone else's results on ArXiv and just ask yourself what really matters.

`So, stop.  This is where you have to ask yourself "Are you really satisfied with where you are?"  Sure, not everyone can get the perfect job, but have you actually tried learning everything you could before giving up?  Is it really too late to start with a new career?  Maybe getting this done right isn't about just trying to just beat your friend's stock options package by 1.2%.  Maybe you need to stop comparing yourself to everyone else's lives on Facebook and just ask yourself what really matters.`

Because you know you can do better.  Because you know you were meant for something more.

`Because you know you can do better.  Because you know you were meant for something more.`