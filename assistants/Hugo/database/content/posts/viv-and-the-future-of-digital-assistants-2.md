---
layout: post
title: VIV and the Future of Digital Assistants
date: '2016-05-15 19:04:58'
---

Recently VIV debuted its flagship product at TechCrunch Disrupt to great fanfare, but unfortunately the results didn't quite match up to the hype.  Let's first talk about what they did right.  The founders at VIV have spent a lot of time thinking about what the ideal experience for a digital personal assistant might look like and have come up with four main criteria:

  - One assistant
  - Personalized for you
  - Available on any device
  - Powered by any service

This framework is absolutely correct - that's a win.  However, as my friend put it the other day, these items are "interesting and accurate, yet not insightful."   More so than coming up with the right vision, a company's success is determined by its ability to execute on that vision.

### One Assistant
This criteria just seems silly because no one else in the industry is suggesting multiple assistants.  It seems pretty clear that there *will* be multiple assistants (Siri, Cortana, M, etc.) coming from multiple companies, but every single one of those companies are pushing to position themselves as the de facto solitary winner in the space.  VIV executes on this point flawlessly, but it's strictly easier to make one assistant before making many assistants, so I'm not sure that's an accomplishment.

### Personalized For You
This rule is right on the money, but VIV falls short in execution.  Despite connecting to multiple third-party providers that have access to a wealth of user data, VIV only puts a small amount of that data to good use.  For example, ordering a cab takes into account the number of people in my group, but not the type of driver I like (outgoing vs. quiet, drives safer vs. drives faster).  In other words, VIV saves the user steps in the processing of a task, but provides an experience that can hardly be called personalized.

Furthermore, the demo included delivering flowers with the system automatically making the connection that "Mom" was a certain person listed in the address book.  However, if this works like Clara or other current AI systems, the personalization is still done through an explicit Settings stage where I must tell the system who these people are, rather than inferring from context.  This isn't a real dealbreaker if that information is easy to input, but all existing tools still require an onboarding process that feel like filling out a form rather than talking to a person.

This is not too surprising because even advanced deep learning techniques are not yet up to the task, so companies using techniques from a couple years past certainly won't have the most cutting edge results.  But I foresee a near future where each user and their preferences can be represented as a "personalization profile" vector embedding that can then be optimized and updated as new data sources flow in.  Then to find out what a given user wants for a particular task, a dot product combined with some non-linearities can be used to recommend the right experience.  This would represent a big step up from collaborative filtering, which can generate recommendations, but is non-differentiable, making it invalid for use with deep neural networks.  Consequently, I believe some more innovation around better personalization techniques are required before the ecosystem takes off.

### Available On Any Device
The big takeaway from the mobile era is that computing should work anywhere.  All devices are connected to the cloud with APIs making data ubiquitous.  To that end, the best assistants are already available on desktop and mobile, but very few of them work on embedded devices.  Amazon Echo can be seen as an exception, but the device itself is reasonably large – not something you can wear on your wrist and carry around with you all day.   Google has made commendable progress here by releasing [TensorFlow Serving](https://tensorflow.github.io/serving/) for deploying trained models into mobile devices.  Comparatively, VIV seemingly hasn't done anything noteworthy to make their AI available on more devices than just desktop and mobile.

### Powered By Any Service
In order to scale into the future, any successful chatbot or digital assistant must be able to plug into an arbitrary number of services and data sources.  Just connecting to different services though seems inadequate because this fails to take advantage of the wealth of information created when combining data from different areas.  As an example:

  - Service Provider A sells milkshakes, and they know you like strawberry milkshakes rather than vanilla or chocolate
  - Service Provider B sells ice cream sandwiches, but they know you usually just buy the ice cream and skip the cookie.
  - Then, Service Provider C is a restaurant and based on past meals, they know you like steak and fajitas, but they have no information about your dessert preferences.  As part of weekly special, they are offering chocolate lava cake or strawberry ice cream.

Given the combined data, the system should be able to recommend the strawberry ice cream despite the fact that no single provider has all the information needed to see the pattern.  In other words, a linear increase in added services should provide a exponential growth in added value.

In order for this to happen, we need a scalable algorithm that can take in any number of data types and use all of them to add value to the final recommendation.  While this might sound like a pie-in-the-sky idea, I believe the deep learning community has made definite progress in this direction.  Specifically, advances in Neural Turing Machines seem promising because they should (theoretically) be able to ingest data from any number of sources, and use an infinite number of reads and writes to make that data useful. After outputting a certain set of recommendations, a user can give feedback to the machine.  The system can now make predictions across a wide range of use cases, and combined with reinforcement learning, the system should also be able to take the user feedback to make the system better over time.  And if each prediction > state > reward leads to more data, a virtuous cycle appears where better recommendations lead to more users, which leads to better recommendations.

Ultimately, VIV has the right idea for the future and has made meaningful contributions to entire AI ecosystem by providing a vision for what the interactions might look like.  When a nascent industry is just starting, one must appreciate all the little shifts in the public's mind because the main impediment to technological innovation is invariably social rather than technical.  So for that, VIV deserves all the approbation.