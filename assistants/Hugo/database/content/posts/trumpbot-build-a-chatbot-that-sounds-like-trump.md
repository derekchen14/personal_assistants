---
layout: post
title: 'TrumpBot: a Chatbot that Sounds like Trump'
featured: true
date: '2017-05-03 16:18:00'
tags:
- nlp
- modeling
- research
---

Trained a Seq2Seq model with attention and incorporated a Pointer Sentinel mechanism for handling OOV. Data was collected by manually scraping and cleaning presidential debates, interviews, related speeches, and Twitter. Results seemed promising since the model output was reflective of Trump's speech, however current evaluation methods are insufficient since target labels themselves are semantically incoherent.

![trumpbot_group](/content/images/2017/12/trumpbot_group.JPG)

![trumpbot_poster](/content/images/2017/12/trumpbot_poster.JPG)

[Link to Research Paper](https://www.dropbox.com/s/igjulgf0fna5ziu/trumpbot-seq2seq-pointer.pdf?dl=0)
