---
layout: post
title: Getting Started with Machine Learning in Python
date: '2015-12-26 00:56:22'
---

Recently, you've read numerous HN articles telling you machine learning is the future. You've heard that Google uses it for [search](http://www.bloomberg.com/news/articles/2015-10-26/google-turning-its-lucrative-web-search-over-to-ai-machines), Facebook uses it to [detect faces](http://fortune.com/2015/06/15/facebook-ai-moments/), and Netflix uses it for [recommendations](http://techblog.netflix.com/2012/04/netflix-recommendations-beyond-5-stars.hml).  Your interest is sufficiently piqued.  But you might still be left wondering, *"How do I get started?"*

Well, assuming you've gone through the famous [ML course](https //www.coursera.org machine learning) taught by Andrew Ng, you should already know that the general process includes:

 * Input lots of data
 * (magic) ???
 * Profit

Ok, so maybe you know that it's actually a lot more complicated:

 * Data Gathering (10% of your time)
 * Exploratory Data Analysis (30% of your time)
 * Pre-processing and Cleaning (30% of your time)
 * Training and Optimization (20% of your time)
 * Presenting Results (10% of your time)

But what tools do you use for each of these phases? What libraries are even available? In other words, now that you have a basic grasp of the ideas involved, what are the next steps?

###The Basics

A bit of common sense can go a long way when starting out -- pick tools you already know, pick an ecosystem with a vibrant community, pick a library with lots of documentation.  For example, let's assume you have an existing toolset chosen from previous projects, such as your language (R vs. Python vs. Java) and text editor (Sublime Text vs. Jupyter Notebooks vs. Emacs) of choice.  If you're comfortable with those tools, keep using them!

However, the explosion of choices soon forces a more strategic approach to selecting the right tools for building machine learning pipelines. When evaluating your options, a useful framework is the combination of speed, power, and longevity:

 * **Speed** means you can get up and running sooner
 * **Power** means that once you get going, you can get a lot more done
 * **Longevity** means your decision will have lasting value, such that it is worth the investment to learn a new tool

As an example, when applying this framework, you might choose to study [Decision Trees](https://en.wikipedia.org/wiki/Decision_tree) for *speed*, [Support Vector Machines](https://en.wikipedia.org/wiki/Support_vector_machine) for *power*, and [Recurrent Neural Nets](https://en.wikipedia.org/wiki/Recurrent_neural_network) for *longevity*.  This is not to say that Decision Trees are not powerful (indeed performance for GBMs rivals SVMs), but simply that getting started with training and understanding the intuition behind Decision Trees can happen much faster.  Roughly speaking, these three buckets correspond to finding a balance between the short-term, medium-term, and  long-term view.

###The Options

*Choosing an algorithm* - the first decision you might encounter that leaves you scratching your head is which algorithm to use when training your model.  The list is [quite long](https://en.wikipedia.org/wiki/List_of_machine_learning_concepts).  However, this is a red herring since depending on what your company or project requires, it should be clear which algorithms are best suited to get the job done.  For example, kNN is great for unsupervised clustering and convolutional neural nets are great for image recognition, but you wouldn't really use one algorithm in the place of the other.

Additionally, once you have narrowed the field down to smaller batch of reasonable candidates, you can just choose to train using the entire collection and then pick the algorithm that gives the best result.  Or even better, aggregate all the algorithms together to get [a super result](https://en.wikipedia.org/wiki/Ensemble_learning). Thus, rather than spending time figuring out which algorithm is the "best", start instead by determining what you want to build.

*Data Gathering* - As mentioned above, gathering and storing data is where real machine learning starts. Good sources of data include the [UCI Machine Learning Repository](https://archive.ics.uci.edu/ml/datasets.html) and [Amazon Public Datasets](http://aws.amazon.com/public-data-sets/), but there are many [more options](http://www.kdnuggets.com/datasets/index.html) as well.  Additionally, you might want to create your own data by [scraping the internet](http://scrapy.org/) or [using a service](https://www.kimonolabs.com/).  Then there's the question of how to store the data - flat files, csv, json, [sql database](https://www.reddit.com/r/Python/comments/3wa22v/120gb_csv_is_this_something_i_can_handle_in_python)?  Furthermore, even if the data is directly available from a Kaggle competition, just downloading can take awhile.  Although data gathering is quite straightforward, the process should not be discounted since it is also quite time-consuming.
  
*Exploratory Data Analysis* - If you're just starting out with data analysis, Excel is probably your best friend.  As you scale up though, you should also level up into either [Pandas](http://pandas.pydata.org/) or R.  Given that this post is about Python, the option here is relatively straightforward.  The work in EDA truly comes down to performing the due diligence for discovering insights and feature engineering.  Protip: be sure to take advantage of `df.shape`, `df.describe()`, and `pd.unique(df.col_name.ravel())`.

*Pre-processing and Cleaning* - While you could do quite a bit of munging using just Pandas, [SK-Learn](http://scikit-learn.org/stable/index.html) offers a wide range of pre-built methods to do all the things every tutorial suggests, including [scaling](http://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html) or normalization, [principal components analysis](http://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html), and [feature selection](http://scikit-learn.org/stable/modules/feature_selection.html).  Additionally, SK-Learn also has great libraries and a super simple API for fitting and predicting all the basic machine learning algorithms.  Even if you plan to move onto more advanced work in the future, Scikit Learn is definitely the place to begin.

*Training and Optimization* - If the goal is simply to get your feet wet in machine learning, SK-Learn alone will suffice.  Although, all the hype these days is about deep learning with neural networks that contain dozens of layers and millions of parameters – something SK-Learn was not built to handle. For this purpose, you might have heard about Google open-sourcing [Tensorflow](https://www.tensorflow.org/), a software library based upon what they use internally for machine learning.

You might immediately conclude TensorFlow is the way to go, but unfortunately the reality is a bit more complicated.  If being backed by a large tech company is your concern, then Microsoft released [DMTK](https://github.com/Microsoft/DMTK) and Facebook has contributed [Torch](http://torch.ch/).  If you want strong research foundations and wide adoption, then [Caffe](http://caffe.berkeleyvision.org/) and [Theano](http://deeplearning.net/software/theano/) are prime options.  For enterprise use with Java, [DeepLearning4J](http://deeplearning4j.org/) and [H20.ai](http://h2o.ai/) have open source packages as well.  [MetaMind](http://metamind.com) and [Clarifai](http://www.clarifai.com/) offer direct APIs so you don't have to code at all! The long tail of options can get quite overwhelming, so instead let's take a step back to evaluate our goals again.

Which tools will help with *speed*?  SK-Learn is the clear winner with the easiest set-up, especially if you are already using it for preprocessing tasks.  Which tools are the most *powerful*? [Keras](keras.io), [Lasagne](http://lasagne.readthedocs.org/en/latest/user/tutorial.html) and [Blocks](http://blocks.readthedocs.org/en/latest/) all offer clean APIs built on top of the lower level libraries, so you get the benefits of academic strength without requiring a PhD for operation.  For *longevity*, I would suggest taking the time to learn TensorFlow or Theano.  To help you make a decision, [this evaluation](https://github.com/zer0n/deepframeworks/blob/master/README.md) offers an amazing breakdown.  

*Presenting Results* - When choosing your [visualization tool](http://pbpython.com/visualization-tools-1.html), keep in mind whether your final outcome is a research paper, blog post or PowerPoint since that naturally guide your decision.  Some common options include ggplot, bokeh, seaborn or  matplotlib.  For business settings, exporting to Excel for graphing is always an option.  If the end goal is an actual product that uses machine learning, [embeddable objects](https://s3.amazonaws.com/h2o-release/h2o/rel-markov/1/docs-website/userguide/scorePOJO.html) or [variables](https://www.tensorflow.org/versions/master/how_tos/variables/index.html) are great containers for holding your final results.

###The Winners

For getting started, I would recommend pulling data from Kaggle or Data Driven, importing Pandas and SK-Learn into Sublime, and just aim to submit a CSV result.  At this point, more so than anyone on the Leaderboard, your greatest competition is getting yourself motivated enough to take the first step.  After a couple months, you might end up with an [end to end flow](https://github.com/derekchen14/e2eflow) similar to mine which utilizes Keras for training and Pandas for everything else.

Why Keras over Lasange or Blocks?  The latter two are geared towards [academic use](https://news.ycombinator.com/item?id=9284251), while the former is geared towards real-world applications.  Given that I am a product manager and not a post-doc, the decision is pretty simple.  Why Pandas?  When you can use just *one* tool for analyzing, processing, munging and visualizing data, there's no reason to complicate matters further by adding other pieces to the puzzle.

**Parting Thoughts**

Overall, I hope you now have a good starting point with a number of decisions you will encounter when performing machine learning.  More importantly, I hope to have given you a set of pragmatic criteria to consider when deciding what tools to use because any recommendation quickly grows outdated as the ecosystem evolves.  Agree or disagree with the winners chosen?  Let me know in the comments below.